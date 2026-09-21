"""SMX-044 browser People workflow over production collaboration.

People is the collaboration plane. It coordinates the production collaboration store,
transient presence and explicit semantic conflict resolution without introducing a
browser-side canonical model or any Together/runtime-network identity.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable

from splashmx.canonical.core import ProjectRevisionId
from splashmx.canonical.serialization import CanonicalProjectRevision, validate_project_revision
from splashmx.collaboration.core import (
    CollaborationError,
    CollaborationTransaction,
    IngestResult,
    RelayAuthenticator,
    RelayPacket,
    SQLiteCollaborationStore,
    TransactionId,
    create_transaction,
)

MAX_RELAY_QUEUE = 64


class PeopleError(RuntimeError):
    def __init__(self, code: str, message: str, *, cause: BaseException | None = None):
        super().__init__(message)
        self.code = code
        self.cause = cause


def _key_for(mapping: Any, token: str):
    for key in mapping:
        if str(key) == token:
            return key
    return None


def _copy_locus(current: CanonicalProjectRevision, selected: CanonicalProjectRevision, locus: str) -> CanonicalProjectRevision:
    """Copy exactly one semantic conflict locus from a complete alternative.

    Protected assets are copied as a complete ProtectedAssetRevision object. No field
    from one competing revision is combined with another.
    """
    document = deepcopy(current.document)
    assets = deepcopy(dict(current.assets))
    if ":" not in locus:
        raise PeopleError(
            "people.unsupported_conflict_locus",
            "This conflict requires an authored edit before it can be acknowledged.",
        )
    prefix, token = locus.split(":", 1)
    maps = {
        "thing": "things",
        "relationship": "relationships",
        "connection": "connections",
        "definition": "definitions",
        "instance": "instances",
    }
    if prefix in maps:
        name = maps[prefix]
        target = getattr(document, name)
        source = getattr(selected.document, name)
        target_key = _key_for(target, token)
        source_key = _key_for(source, token)
        if source_key is None:
            if target_key is not None:
                del target[target_key]
        else:
            if target_key is not None and target_key != source_key:
                del target[target_key]
            target[source_key] = deepcopy(source[source_key])
    elif prefix == "known-unloaded":
        matching = next((key for key in selected.document.known_unloaded_things if str(key) == token), None)
        existing = next((key for key in document.known_unloaded_things if str(key) == token), None)
        if existing is not None:
            document.known_unloaded_things.discard(existing)
        if matching is not None:
            document.known_unloaded_things.add(matching)
    elif prefix == "asset":
        target_key = _key_for(assets, token)
        source_key = _key_for(selected.assets, token)
        if source_key is None:
            if target_key is not None:
                del assets[target_key]
        else:
            if target_key is not None and target_key != source_key:
                del assets[target_key]
            # This assignment is deliberately whole-object: source/audio/provenance/
            # licence/lineage remain one immutable protected revision.
            assets[source_key] = deepcopy(selected.assets[source_key])
    else:
        raise PeopleError(
            "people.unsupported_conflict_locus",
            "This conflict requires an authored edit before it can be acknowledged.",
        )
    return CanonicalProjectRevision(document, assets)


class PeopleSession:
    """Local-first coordinator for the browser collaboration/People plane."""

    def __init__(
        self,
        initial_project: CanonicalProjectRevision,
        store_path: str | Path,
        *,
        principal_id: str = "local-author",
        store_factory: Callable[[str | Path, CanonicalProjectRevision], SQLiteCollaborationStore] = SQLiteCollaborationStore,
    ):
        validate_project_revision(initial_project)
        self.principal_id = principal_id
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.store = store_factory(self.store_path, initial_project)

        # Actor sequence is history metadata, never semantic identity. Resume after
        # every locally known sequence so a process restart cannot reuse TransactionId.
        row = self.store._db.execute(
            "SELECT COALESCE(MAX(actor_seq),0) FROM receipts WHERE actor_id=?",
            (principal_id,),
        ).fetchone()
        pending = self.store._db.execute(
            "SELECT COALESCE(MAX(actor_seq),0) FROM pending WHERE actor_id=?",
            (principal_id,),
        ).fetchone()
        self._actor_seq = max(int(row[0]), int(pending[0]))
        self._relay_queue: list[CollaborationTransaction] = []
        self._relay_online = True
        self._unsynced_project: CanonicalProjectRevision | None = None
        self._unsynced_base: CanonicalProjectRevision | None = None
        self._unsynced_parents: tuple[TransactionId, ...] | None = None
        self._last_error: str | None = None

    def close(self) -> None:
        self.store.close()

    def head_project(self) -> CanonicalProjectRevision:
        return self.store.head_project()

    def _head_transaction(self) -> TransactionId | None:
        value = self.store._head_row()[1]
        return None if value is None else TransactionId(str(value))

    def _parents_for_base(self, base: CanonicalProjectRevision) -> tuple[TransactionId, ...]:
        """Return every causal edge required to name an exact known base revision.

        A later semantic transaction may deliberately make an older, already-known
        ProjectRevisionId the active head (for example browser Reload followed by a
        new edit). The SMX-043 store requires the original producer of that exact base
        revision to remain a parent as well as the current head transaction. Retaining
        both edges prevents a rollback/reload from either losing causality or making a
        valid subsequent local edit look like forged history.
        """
        parents: list[TransactionId] = []
        head = self._head_transaction()
        if head is not None:
            parents.append(head)
        row = self.store._db.execute(
            "SELECT origin_tx FROM revisions WHERE revision_id=?",
            (str(base.document.project_revision_id),),
        ).fetchone()
        if row is not None and row[0] is not None:
            origin = TransactionId(str(row[0]))
            if origin not in parents:
                parents.append(origin)
        return tuple(parents)

    def author_revision_counter(self) -> int:
        values: list[int] = []
        for (value,) in self.store._db.execute(
            "SELECT revision_id FROM revisions WHERE revision_id LIKE 'author-%'"
        ):
            text = str(value)
            if text.startswith("author-") and text[7:].isdigit():
                values.append(int(text[7:]))
        return max(values, default=0)

    def set_relay_online(self, online: bool) -> None:
        self._relay_online = bool(online)
        if online and self._last_error == "people.relay_offline":
            self._last_error = None

    def record_local(self, candidate: CanonicalProjectRevision, *, fault_hook=None) -> IngestResult | None:
        validate_project_revision(candidate)
        current = self.head_project()
        if candidate == current:
            self._unsynced_project = None
            self._unsynced_base = None
            self._unsynced_parents = None
            return None

        base = self._unsynced_base or current
        parents = self._unsynced_parents if self._unsynced_base is not None else self._parents_for_base(base)
        self._actor_seq += 1
        transaction = create_transaction(
            actor_id=self.principal_id,
            actor_seq=self._actor_seq,
            parents=parents,
            permission_epoch=self.store.permission_epoch,
            base=base,
            candidate=candidate,
        )
        try:
            result = self.store.ingest(transaction, fault_hook=fault_hook)
        except Exception as exc:
            # The authored local project remains in memory and is never replaced by a
            # remote copy merely because collaboration persistence is unavailable.
            self._unsynced_project = candidate
            self._unsynced_base = base
            self._unsynced_parents = parents
            self._last_error = getattr(exc, "code", "people.local_history_unavailable")
            return None
        if result.status not in {"applied", "applied-conflict", "resolution", "duplicate"}:
            self._unsynced_project = candidate
            self._unsynced_base = base
            self._unsynced_parents = parents
            self._last_error = "people.local_history_not_materialized"
            return result

        self._unsynced_project = None
        self._unsynced_base = None
        self._unsynced_parents = None
        self._last_error = None
        return result

    def retry_local(self) -> IngestResult | None:
        if self._unsynced_project is None:
            return None
        return self.record_local(self._unsynced_project)

    def enqueue_relay(self, packet: RelayPacket, authenticator: RelayAuthenticator) -> int:
        if not self._relay_online:
            self._last_error = "people.relay_offline"
            raise PeopleError(
                "people.relay_offline",
                "Collaboration relay is offline; local authored work remains available.",
            )

        # Authenticate before consuming bounded queue capacity. Relay authentication
        # proves sender-envelope integrity only; permission epoch is checked again by
        # the production store immediately before semantic materialization.
        transaction = authenticator.verify(packet)
        if len(self._relay_queue) >= MAX_RELAY_QUEUE:
            self._last_error = "people.relay_backpressure"
            raise PeopleError(
                "people.relay_backpressure",
                "Collaboration input is busy; retry without discarding local work.",
            )
        self._relay_queue.append(transaction)
        return len(self._relay_queue)

    def drain_relay(self, *, limit: int = MAX_RELAY_QUEUE) -> tuple[IngestResult, ...]:
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1 or limit > MAX_RELAY_QUEUE:
            raise PeopleError(
                "people.invalid_drain_limit",
                "Relay drain limit is outside the bounded collaboration profile.",
            )

        # Never let remote delivery replace unsynced local state. Hold authenticated
        # remote work until local history has been recovered or explicitly reconciled.
        if self._unsynced_project is not None:
            return ()
        results: list[IngestResult] = []
        while self._relay_queue and len(results) < limit:
            transaction = self._relay_queue.pop(0)
            results.append(self.store.ingest(transaction))
        results.extend(self.store.retry_pending())
        self._last_error = None
        return tuple(results)

    def set_presence(self, *, cursor: str | None = None, selections=()) -> None:
        self.store.set_presence(self.principal_id, cursor=cursor, selections=selections)

    def resolve_conflict(self, conflict_id: str, choice: str) -> IngestResult:
        conflict = self.store.conflict(conflict_id)
        if conflict is None or conflict.resolved_by is not None:
            raise PeopleError(
                "people.unknown_conflict",
                "That collaboration conflict is no longer unresolved.",
            )
        current = self.head_project()
        if choice == "current":
            document = deepcopy(current.document)
            assets = deepcopy(dict(current.assets))
            candidate = CanonicalProjectRevision(document, assets)
        elif choice == "alternative-a":
            candidate = _copy_locus(current, conflict.alternative_a, conflict.locus)
        elif choice == "alternative-b":
            candidate = _copy_locus(current, conflict.alternative_b, conflict.locus)
        else:
            raise PeopleError(
                "people.invalid_resolution",
                "Choose current, alternative A or alternative B.",
            )

        self._actor_seq += 1
        document = deepcopy(candidate.document)
        document.project_revision_id = ProjectRevisionId(
            "people-resolve-"
            + sha256(
                f"{conflict_id}\0{choice}\0{current.document.project_revision_id}\0{self._actor_seq}".encode()
            ).hexdigest()
        )
        candidate = CanonicalProjectRevision(document, deepcopy(dict(candidate.assets)))
        validate_project_revision(candidate)
        transaction = create_transaction(
            actor_id=self.principal_id,
            actor_seq=self._actor_seq,
            parents=self._parents_for_base(current),
            permission_epoch=self.store.permission_epoch,
            base=current,
            candidate=candidate,
            resolves=(conflict_id,),
        )
        result = self.store.ingest(transaction)
        if result.status != "resolution":
            raise PeopleError(
                "people.resolution_not_materialized",
                "Conflict resolution was retained but not published as canonical state.",
            )
        return result

    def snapshot(self) -> dict[str, Any]:
        conflicts = []
        for conflict in self.store.unresolved_conflicts():
            choices = ["current"] if conflict.locus == "document" else ["current", "alternative-a", "alternative-b"]
            conflicts.append(
                {
                    "conflict_id": conflict.conflict_id,
                    "transaction_id": str(conflict.tx_id),
                    "locus": conflict.locus,
                    "kind": conflict.kind,
                    "choices": choices,
                    "alternatives": [
                        {
                            "choice": "alternative-a",
                            "project_revision_id": str(conflict.alternative_a.document.project_revision_id),
                        },
                        {
                            "choice": "alternative-b",
                            "project_revision_id": str(conflict.alternative_b.document.project_revision_id),
                        },
                    ],
                }
            )
        return {
            "plane": "collaboration",
            "local_first": True,
            "canonical_authority": "validated-local-head",
            "head_revision_id": str(self.head_project().document.project_revision_id),
            "permission_epoch": self.store.permission_epoch,
            "unsynced_local_work": self._unsynced_project is not None,
            "relay_online": self._relay_online,
            "relay_queue_depth": len(self._relay_queue),
            "last_error": self._last_error,
            "presence": [
                {
                    "principal_id": row.principal_id,
                    "cursor": row.cursor,
                    "selections": list(row.selections),
                }
                for row in self.store.presence()
            ],
            "conflicts": conflicts,
        }
