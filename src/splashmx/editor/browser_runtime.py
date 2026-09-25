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

from splashmx.canonical.core import PortDirection, PortKind, ThingId
from splashmx.canonical.serialization import SerializationError, deserialize_project, serialize_project
from splashmx.distribution.runtime import DistributionError, export_recovery_archive, import_recovery_archive
from splashmx.editor.authoring import (
    AuthoringError,
    AuthoringSession,
    CHANGE_COLOUR_PORT_ID,
    CLICKED_PORT_ID,
    POINTER_CLICK_EVENT,
    VISUAL_FILL_RULE_KIND,
)
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
    if code.startswith("distribution."):
        if code in {"distribution.invalid_archive", "distribution.unsupported_archive", "distribution.resource_limit"}:
            return AuthorDiagnostic(code, "Backup could not be opened", "Your current project is unchanged. Choose a valid SplashMX backup and try again.")
        if code == "distribution.project_mismatch":
            return AuthorDiagnostic(code, "Backup belongs to another project", "Your current project is unchanged. Restore a backup created from this project.")
        return AuthorDiagnostic(code, "Backup recovery could not continue", "Your current project is unchanged. No partial recovery was published.")
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
        current_revision = str(self.authoring.document.project_revision_id)
        dirty = self.last_saved_revision_id != current_revision
        base["storage"] = {
            "saved_revision_id": self.last_saved_revision_id,
            "current_revision_id": current_revision,
            "dirty": dirty,
            "state": "never-saved" if self.last_saved_revision_id is None else "dirty" if dirty else "saved",
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

    def dispatch_pointer_event(
        self,
        thing_id: str | ThingId,
        payload: Any = None,
    ) -> list[ThingId]:
        """Route one real pointer event through local Rules and canonical Connections."""
        world = self.world
        if world is None:
            raise BrowserRuntimeError("browser.play_not_active", "Start Play before interacting with the creation.")
        tid = thing_id if isinstance(thing_id, ThingId) else ThingId(thing_id)
        source = self.authoring.document.things.get(tid)
        if source is None or source.tombstoned or tid not in world.runtime.states:
            raise BrowserRuntimeError("browser.interaction_thing_unavailable", "That interactive Thing is not active in Play.")

        local_rule = any(
            attachment.authored_config.get("projection") == "Rule"
            and attachment.authored_config.get("author_kind") == VISUAL_FILL_RULE_KIND
            and attachment.authored_config.get("event") == POINTER_CLICK_EVENT
            for attachment in source.behaviours.values()
        )

        routes: list[ThingId] = []
        for connection in sorted(
            self.authoring.document.connections.values(),
            key=lambda row: str(row.connection_id),
        ):
            if (
                connection.tombstoned
                or connection.source.thing_id != tid
                or connection.source.port_id != CLICKED_PORT_ID
            ):
                continue
            source_port = source.ports.get(connection.source.port_id)
            if (
                source_port is None
                or source_port.kind is not PortKind.EVENT
                or source_port.direction is not PortDirection.OUT
            ):
                raise BrowserRuntimeError(
                    "browser.connection_event_unavailable",
                    "This Connection's source event is no longer available. Edit or delete the Connection.",
                )
            target = self.authoring.document.things.get(connection.target.thing_id)
            target_port = None if target is None else target.ports.get(connection.target.port_id)
            target_rule = False if target is None else any(
                attachment.authored_config.get("projection") == "Rule"
                and attachment.authored_config.get("author_kind") == VISUAL_FILL_RULE_KIND
                and attachment.authored_config.get("event") == POINTER_CLICK_EVENT
                for attachment in target.behaviours.values()
            )
            if (
                target is None
                or target.tombstoned
                or connection.target.port_id != CHANGE_COLOUR_PORT_ID
                or target_port is None
                or target_port.kind is not PortKind.COMMAND
                or target_port.direction is not PortDirection.IN
                or not target_rule
                or connection.target.thing_id not in world.runtime.states
            ):
                raise BrowserRuntimeError(
                    "browser.connection_action_unavailable",
                    "This Connection's target action is no longer available. Add the target's Change colour Rule again, edit the Connection, or delete it.",
                )
            routes.append(connection.target.thing_id)

        if not local_rule and not routes:
            raise BrowserRuntimeError(
                "browser.no_matching_interaction",
                "This Thing has no matching Rule or supported outgoing Connection.",
            )

        before_faults = len(world.runtime.faults)
        affected: list[ThingId] = []
        if local_rule:
            if world.dispatch(tid, POINTER_CLICK_EVENT, payload) <= 0:
                raise BrowserRuntimeError(
                    "browser.no_matching_interaction",
                    "This Thing's click Rule could not be dispatched.",
                )
            affected.append(tid)
        for target_id in routes:
            if world.dispatch(target_id, POINTER_CLICK_EVENT, payload) <= 0:
                raise BrowserRuntimeError(
                    "browser.connection_action_unavailable",
                    "This Connection's target action could not be dispatched. Edit or delete the Connection.",
                )
            affected.append(target_id)

        world.runtime.run_current_tick()
        if len(world.runtime.faults) > before_faults:
            fault = world.runtime.faults[-1]
            raise BrowserRuntimeError(fault.code, fault.message)

        result: list[ThingId] = []
        seen: set[ThingId] = set()
        for affected_id in affected:
            if affected_id not in seen:
                result.append(affected_id)
                seen.add(affected_id)
        return result

    def refresh_saved_revision_marker(self) -> None:
        """Recover the durable local-head marker without changing active authored state."""
        if not self.store_path.exists():
            self.last_saved_revision_id = None
            return
        try:
            with self.store_factory(self.store_path) as store:
                saved = store.load(self.authoring.document.project_id)
        except StorageError as exc:
            if exc.code == "storage.not_found":
                self.last_saved_revision_id = None
                return
            # Status probing must never replace or damage current work. Surface the
            # failure only when the author explicitly saves/reloads/recovers.
            return
        self.last_saved_revision_id = str(saved.document.project_revision_id)

    def export_recovery(self) -> bytes:
        """Export the active canonical project through the existing SMX-050 archive."""
        try:
            serialized = serialize_project(self.authoring.project)
            return export_recovery_archive(project=serialized)
        except (SerializationError, DistributionError) as exc:
            raise self._remember_failure(exc) from exc

    def import_recovery(self, raw: bytes) -> dict[str, Any]:
        """Prepare a complete recovery candidate before replacing active unsaved state."""
        try:
            bundle = import_recovery_archive(raw)
            if bundle.project is None:
                raise DistributionError("distribution.invalid_archive", "backup does not contain a project")
            candidate = deserialize_project(bundle.project)
            if candidate.document.project_id != self.authoring.document.project_id:
                raise DistributionError("distribution.project_mismatch", "backup project identity differs")
            candidate_session = AuthoringSession(candidate, revision_counter=0)
            candidate_session.programs.update(rebuild_program_catalog(candidate_session))
            candidate_session._revision_counter = _revision_counter(candidate_session)
        except (SerializationError, DistributionError, BrowserRuntimeError) as exc:
            raise self._remember_failure(exc) from exc
        self.authoring = candidate_session
        self.world = None
        return {
            "recovered_revision_id": str(candidate.document.project_revision_id),
            "requires_save": self.last_saved_revision_id != str(candidate.document.project_revision_id),
        }

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
