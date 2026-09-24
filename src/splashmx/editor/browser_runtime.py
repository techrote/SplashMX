"""SMX-033 browser Play/Stop, local-save and author-diagnostic integration.

This module coordinates existing production boundaries; it does not define a second
canonical or execution model. Authored edits stay in :class:`AuthoringSession`, Play
uses :class:`WorldRuntime`, and durable project publication uses SMX-025 storage.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Callable

from splashmx.editor.authoring import AuthoringError, AuthoringSession
from splashmx.execution.ir import BudgetLimits, IRProgram, compile_rule
from splashmx.runtime.lifecycle import LifecycleError, WorldRuntime
from splashmx.storage.local import SQLiteProjectStore, StorageError


class BrowserRuntimeError(RuntimeError):
    """Typed author-facing failure for the browser runtime/save boundary."""

    def __init__(self, code: str, message: str, *, cause: BaseException | None = None):
        super().__init__(message)
        self.code = code
        self.cause = cause


@dataclass(frozen=True)
class AuthorDiagnostic:
    code: str
    title: str
    message: str
    severity: str = "error"
    recoverable: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "title": self.title,
            "message": self.message,
            "severity": self.severity,
            "recoverable": self.recoverable,
        }


_STORAGE_MESSAGES = {
    "storage.quota_exceeded": ("Storage is full", "Your project was not replaced. Free local storage and try Save again."),
    "storage.permission_denied": ("Storage access was denied", "Your current project is still open and unchanged. Allow local storage, then try Save again."),
    "storage.corrupt_store": ("Saved data could not be verified", "The current project was kept unchanged. Restore a known-good local revision or choose another local store."),
    "storage.unavailable": ("Local storage is unavailable", "The current project was kept unchanged. Check local storage access and try again."),
    "storage.io_failure": ("Local storage could not finish the save", "The current project was kept unchanged. Check the device and try again."),
    "storage.not_found": ("No saved project was found", "Save this project locally before reloading it."),
    "storage.revision_conflict": ("A saved revision conflicts with this project", "The current project was kept unchanged. Reload the known-good saved revision before continuing."),
    "storage.incompatible_revision": ("This saved project needs a newer compatible reader", "The current project was kept unchanged. Open it with a compatible SplashMX version."),
    "storage.migration_failed": ("The saved project could not be upgraded safely", "The current project was kept unchanged. No partial migration was published."),
}


def diagnostic_for(exc: BaseException) -> AuthorDiagnostic:
    code = str(getattr(exc, "code", "browser.unexpected_failure"))
    if code in _STORAGE_MESSAGES:
        title, message = _STORAGE_MESSAGES[code]
        return AuthorDiagnostic(code, title, message)
    if code.startswith("execution.") or code.startswith("lifecycle."):
        return AuthorDiagnostic(code, "Play could not continue", "Play stopped before unsafe or invalid runtime state could be published.")
    if code.startswith("authoring.") or code.startswith("semantic.") or code.startswith("serialization."):
        return AuthorDiagnostic(code, "That edit could not be applied", str(exc))
    return AuthorDiagnostic(code, "SplashMX could not complete that action", "The current project was kept unchanged.")


def _revision_counter(session: AuthoringSession) -> int:
    match = re.fullmatch(r"author-(\d+)", str(session.document.project_revision_id))
    return int(match.group(1)) if match else 0


def rebuild_program_catalog(session: AuthoringSession) -> dict[str, IRProgram]:
    """Rebuild exact authored Rule/Behaviour IR after a fresh local reload."""
    programs: dict[str, IRProgram] = {}
    for thing in session.document.things.values():
        if thing.tombstoned:
            continue
        for attachment in thing.behaviours.values():
            config = dict(attachment.authored_config)
            event = config.get("event")
            actions = config.get("actions")
            projection = config.get("projection", "Behaviour")
            if not isinstance(event, str) or not event or not isinstance(actions, list):
                raise BrowserRuntimeError(
                    "browser.behaviour_rebuild_failed",
                    "A saved Rule or Behaviour is missing its safe authored projection.",
                )
            try:
                program = compile_rule(
                    f"author-{str(projection).lower()}",
                    event,
                    [dict(row) for row in actions],
                    behaviour_revision=attachment.behaviour_revision,
                )
            except Exception as exc:  # compile_rule owns the detailed IR rejection
                raise BrowserRuntimeError(
                    "browser.behaviour_rebuild_failed",
                    "A saved Rule or Behaviour could not be rebuilt safely.",
                    cause=exc,
                ) from exc
            programs[attachment.behaviour_revision] = program
    return programs


StoreFactory = Callable[[str | Path], SQLiteProjectStore]


class BrowserRuntimeSession:
    """Coordinate browser authoring, transient Play and crash-safe local persistence."""

    def __init__(
        self,
        authoring: AuthoringSession,
        store_path: str | Path,
        *,
        store_factory: StoreFactory = SQLiteProjectStore,
        budgets: BudgetLimits | None = None,
        seed: int = 33,
    ):
        self.authoring = authoring
        self.store_path = Path(store_path)
        self.store_factory = store_factory
        self.budgets = budgets or BudgetLimits()
        self.seed = seed
        self.world: WorldRuntime | None = None
        self.diagnostics: list[AuthorDiagnostic] = []
        self.last_saved_revision_id: str | None = None

    @property
    def playing(self) -> bool:
        return self.world is not None

    def snapshot(self) -> dict[str, Any]:
        base = self.authoring.snapshot()
        base["runtime"] = {
            "mode": "play" if self.playing else "edit",
            "transient": True,
        }
        base["storage"] = {
            "saved_revision_id": self.last_saved_revision_id,
            "local_only": True,
        }
        base["diagnostics"] = [item.as_dict() for item in self.diagnostics[-12:]]
        return base

    def _remember_failure(self, exc: BaseException) -> BrowserRuntimeError:
        diagnostic = diagnostic_for(exc)
        self.diagnostics.append(diagnostic)
        return BrowserRuntimeError(diagnostic.code, diagnostic.message, cause=exc)

    def play(self) -> dict[str, Any]:
        if self.world is not None:
            return {"mode": "play", "already_playing": True}
        try:
            programs = dict(self.authoring.programs)
            programs.update(rebuild_program_catalog(self.authoring))
            candidate = WorldRuntime.create(
                self.authoring.document,
                programs,
                budgets=self.budgets,
                seed=self.seed,
            )
            # Only the semantic activation trigger fires at Play start. Input Rules
            # such as pointer_click are dispatched by the target input adapter when
            # the event actually occurs; pre-firing them here would create a second,
            # incorrect browser interpretation of authored interaction.
            for thing_id, thing in sorted(self.authoring.document.things.items(), key=lambda row: str(row[0])):
                if thing.tombstoned:
                    continue
                if any(
                    str(attachment.authored_config.get("event", "activate")) == "activate"
                    for attachment in thing.behaviours.values()
                ):
                    candidate.dispatch(thing_id, "activate")
            candidate.runtime.run_current_tick()
            self.world = candidate
            return {
                "mode": "play",
                "logical_tick": candidate.runtime.logical_tick,
                "resident_things": len(candidate.runtime.states),
            }
        except (AuthoringError, LifecycleError, ValueError) as exc:
            self.world = None
            raise self._remember_failure(exc) from exc

    def stop(self) -> dict[str, Any]:
        was_playing = self.world is not None
        self.world = None
        return {"mode": "edit", "discarded_transient_play_state": was_playing}

    def save(self) -> dict[str, Any]:
        project = self.authoring.project
        try:
            self.store_path.parent.mkdir(parents=True, exist_ok=True)
            with self.store_factory(self.store_path) as store:
                stored = store.save(project)
        except StorageError as exc:
            raise self._remember_failure(exc) from exc
        self.last_saved_revision_id = str(stored.document.project_revision_id)
        return {"saved_revision_id": self.last_saved_revision_id}

    def reload(self) -> dict[str, Any]:
        # Prepare and validate a complete candidate before replacing the active
        # authoring session. A failed/corrupt load therefore cannot destroy unsaved
        # in-memory work.
        try:
            with self.store_factory(self.store_path) as store:
                candidate = store.load(self.authoring.document.project_id)
            candidate_session = AuthoringSession(candidate, revision_counter=0)
            candidate_session.programs.update(rebuild_program_catalog(candidate_session))
            candidate_session._revision_counter = _revision_counter(candidate_session)
        except (StorageError, BrowserRuntimeError) as exc:
            raise self._remember_failure(exc) from exc
        self.authoring = candidate_session
        self.world = None
        self.last_saved_revision_id = str(candidate.document.project_revision_id)
        return {"reloaded_revision_id": self.last_saved_revision_id, "mode": "edit"}

    def clear_diagnostics(self) -> None:
        self.diagnostics.clear()
