from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Callable


class LifecycleError(Exception):
    pass


class CompatibilityError(LifecycleError):
    pass


class IdentityReuseError(LifecycleError):
    pass


class SnapshotBoundaryError(LifecycleError):
    pass


@dataclass
class BehaviorRuntime:
    attachment_id: str
    definition_id: str
    revision: int
    private_schema: int
    private_state: dict[str, Any] = field(default_factory=dict)
    prng_state: int = 1

    def draw_u32(self) -> int:
        # Tiny deterministic research PRNG. Not a production recommendation.
        self.prng_state = (1664525 * self.prng_state + 1013904223) & 0xFFFFFFFF
        return self.prng_state


@dataclass
class TimerRecord:
    timer_id: str
    attachment_id: str
    continuation_id: str
    clock_domain: str  # "thing_active" | "world_logical"
    remaining_active_ticks: int | None = None
    due_world_tick: int | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    durable: bool = True


@dataclass
class QueuedWork:
    work_id: str
    target_id: str
    attachment_id: str
    kind: str
    payload: dict[str, Any]
    order: int
    durable: bool = True


@dataclass
class ExternalWait:
    wait_id: str
    attachment_id: str
    service_name: str
    correlation_id: str
    restore_policy: str  # cancel_on_restore | host_resume | session_only | author_reissue
    requested_logical_tick: int


@dataclass
class RuntimeThing:
    thing_id: str
    authored_basis: dict[str, Any]
    public_state: dict[str, Any] = field(default_factory=dict)
    behaviors: dict[str, BehaviorRuntime] = field(default_factory=dict)
    timers: list[TimerRecord] = field(default_factory=list)
    refs: dict[str, str] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    residency: str = "resident"  # resident | unloaded
    activity: str | None = "active"  # active | dormant | None when unloaded
    active_ticks: int = 0
    selected_physics_state: dict[str, Any] = field(default_factory=dict)


@dataclass
class Tombstone:
    thing_id: str
    destroyed_world_tick: int
    reason: str | None = None


BehaviorMigration = Callable[[dict[str, Any]], dict[str, Any]]


class World:
    def __init__(self, *, authored_revision: str, world_tick: int = 0):
        self.authored_revision = authored_revision
        self.world_tick = world_tick
        self.things: dict[str, RuntimeThing] = {}
        self.tombstones: dict[str, Tombstone] = {}
        self.queue: list[QueuedWork] = []
        self.pending_deliveries: list[QueuedWork] = []
        self.external_waits: list[ExternalWait] = []
        self.context: dict[str, dict[str, Any]] = {}
        self.creation_events: list[str] = []
        self.restore_events: list[str] = []
        self.host_service_calls: list[dict[str, Any]] = []
        self._next_order = 0
        self._activation_in_progress = False

    def create_thing(
        self,
        *,
        thing_id: str,
        authored_basis: dict[str, Any],
        public_state: dict[str, Any] | None = None,
        provenance: dict[str, Any] | None = None,
    ) -> RuntimeThing:
        if thing_id in self.tombstones or thing_id in self.things:
            raise IdentityReuseError(f"ThingId is already known in this world lineage: {thing_id}")
        thing = RuntimeThing(
            thing_id=thing_id,
            authored_basis=deepcopy(authored_basis),
            public_state=deepcopy(public_state or {}),
            provenance=deepcopy(provenance or {}),
        )
        self.things[thing_id] = thing
        self.creation_events.append(thing_id)
        return thing

    def attach_behavior(self, thing_id: str, behavior: BehaviorRuntime) -> None:
        thing = self.things[thing_id]
        if behavior.attachment_id in thing.behaviors:
            raise LifecycleError("duplicate attachment id")
        thing.behaviors[behavior.attachment_id] = deepcopy(behavior)

    def set_context(self, thing_id: str, **values: Any) -> None:
        self.context.setdefault(thing_id, {}).update(deepcopy(values))

    def add_timer(self, thing_id: str, timer: TimerRecord) -> None:
        if timer.clock_domain not in {"thing_active", "world_logical"}:
            raise LifecycleError("unsupported timer clock domain")
        if timer.clock_domain == "thing_active":
            if timer.remaining_active_ticks is None or timer.remaining_active_ticks < 0:
                raise LifecycleError("active timer requires nonnegative remaining ticks")
        if timer.clock_domain == "world_logical":
            if timer.due_world_tick is None:
                raise LifecycleError("world timer requires due_world_tick")
        self.things[thing_id].timers.append(deepcopy(timer))

    def queue_work(
        self,
        *,
        work_id: str,
        target_id: str,
        attachment_id: str,
        kind: str,
        payload: dict[str, Any],
        durable: bool = True,
    ) -> QueuedWork:
        work = QueuedWork(
            work_id=work_id,
            target_id=target_id,
            attachment_id=attachment_id,
            kind=kind,
            payload=deepcopy(payload),
            order=self._next_order,
            durable=durable,
        )
        self._next_order += 1
        self.queue.append(work)
        return work

    def issue_external_service(
        self,
        *,
        thing_id: str,
        attachment_id: str,
        wait_id: str,
        service_name: str,
        correlation_id: str,
        restore_policy: str = "cancel_on_restore",
    ) -> None:
        if restore_policy not in {"cancel_on_restore", "host_resume", "session_only", "author_reissue"}:
            raise LifecycleError("unsupported restore policy")
        self.host_service_calls.append(
            {
                "thing_id": thing_id,
                "attachment_id": attachment_id,
                "service_name": service_name,
                "correlation_id": correlation_id,
            }
        )
        self.external_waits.append(
            ExternalWait(
                wait_id=wait_id,
                attachment_id=attachment_id,
                service_name=service_name,
                correlation_id=correlation_id,
                restore_policy=restore_policy,
                requested_logical_tick=self.world_tick,
            )
        )

    def set_dormant(self, thing_id: str, dormant: bool) -> None:
        thing = self.things[thing_id]
        if thing.residency != "resident":
            raise LifecycleError("unloaded Thing has no activity state")
        thing.activity = "dormant" if dormant else "active"

    def unload(self, thing_id: str) -> None:
        thing = self.things[thing_id]
        thing.residency = "unloaded"
        thing.activity = None
        self.context.pop(thing_id, None)

    def make_resident(self, thing_id: str, *, active: bool = True) -> None:
        thing = self.things[thing_id]
        thing.residency = "resident"
        thing.activity = "active" if active else "dormant"

    def resolve_ref(self, target_id: str) -> str:
        if target_id in self.tombstones:
            return "tombstoned"
        thing = self.things.get(target_id)
        if thing is None:
            return "unknown"
        if thing.residency == "unloaded":
            return "known_unloaded"
        return "loaded"

    def destroy(self, thing_id: str, *, reason: str | None = None) -> None:
        if thing_id not in self.things:
            raise LifecycleError("cannot destroy unknown Thing")
        del self.things[thing_id]
        self.context.pop(thing_id, None)
        self.queue = [w for w in self.queue if w.target_id != thing_id]
        self.pending_deliveries = [w for w in self.pending_deliveries if w.target_id != thing_id]
        self.external_waits = [
            w for w in self.external_waits
            if w.attachment_id not in {b.attachment_id for t in self.things.values() for b in t.behaviors.values()}
            or True
        ]
        self.tombstones[thing_id] = Tombstone(
            thing_id=thing_id,
            destroyed_world_tick=self.world_tick,
            reason=reason,
        )

    def advance(self, ticks: int = 1) -> None:
        for _ in range(ticks):
            self.world_tick += 1
            for thing in list(self.things.values()):
                if thing.residency == "resident" and thing.activity == "active":
                    thing.active_ticks += 1
                    for timer in thing.timers:
                        if (
                            timer.clock_domain == "thing_active"
                            and timer.remaining_active_ticks is not None
                            and timer.remaining_active_ticks > 0
                        ):
                            timer.remaining_active_ticks -= 1

                matured: list[TimerRecord] = []
                for timer in thing.timers:
                    if timer.clock_domain == "thing_active":
                        if timer.remaining_active_ticks == 0:
                            matured.append(timer)
                    elif timer.clock_domain == "world_logical":
                        if timer.due_world_tick is not None and timer.due_world_tick <= self.world_tick:
                            matured.append(timer)

                for timer in matured:
                    work = QueuedWork(
                        work_id=f"timer:{timer.timer_id}",
                        target_id=thing.thing_id,
                        attachment_id=timer.attachment_id,
                        kind="continuation",
                        payload={
                            "continuation_id": timer.continuation_id,
                            **deepcopy(timer.payload),
                        },
                        order=self._next_order,
                        durable=timer.durable,
                    )
                    self._next_order += 1
                    if thing.residency == "unloaded":
                        self.pending_deliveries.append(work)
                    else:
                        self.queue.append(work)
                    thing.timers.remove(timer)

    def snapshot(self, *, snapshot_id: str) -> dict[str, Any]:
        if self._activation_in_progress:
            raise SnapshotBoundaryError("snapshot requested during an activation")

        things: list[dict[str, Any]] = []
        for thing_id in sorted(self.things):
            thing = self.things[thing_id]
            things.append(
                {
                    "thing_id": thing.thing_id,
                    "authored_basis": deepcopy(thing.authored_basis),
                    "public_state": deepcopy(thing.public_state),
                    "provenance": deepcopy(thing.provenance),
                    "residency": thing.residency,
                    "activity": thing.activity,
                    "active_ticks": thing.active_ticks,
                    "selected_physics_state": deepcopy(thing.selected_physics_state),
                    "refs": deepcopy(thing.refs),
                    "behaviors": [
                        {
                            "attachment_id": b.attachment_id,
                            "definition_id": b.definition_id,
                            "revision": b.revision,
                            "private_schema": b.private_schema,
                            "private_state": deepcopy(b.private_state),
                            "prng_state": b.prng_state,
                        }
                        for b in sorted(thing.behaviors.values(), key=lambda x: x.attachment_id)
                    ],
                    "timers": [
                        {
                            "timer_id": t.timer_id,
                            "attachment_id": t.attachment_id,
                            "continuation_id": t.continuation_id,
                            "clock_domain": t.clock_domain,
                            "remaining_active_ticks": t.remaining_active_ticks,
                            "due_world_tick": t.due_world_tick,
                            "payload": deepcopy(t.payload),
                            "durable": t.durable,
                        }
                        for t in thing.timers
                        if t.durable
                    ],
                }
            )

        return {
            "schema": "smx007-snapshot-research-v1",
            "snapshot_id": snapshot_id,
            "authored_revision": self.authored_revision,
            "world_tick": self.world_tick,
            "next_order": self._next_order,
            "things": things,
            "tombstones": [
                {
                    "thing_id": t.thing_id,
                    "destroyed_world_tick": t.destroyed_world_tick,
                    "reason": t.reason,
                }
                for t in sorted(self.tombstones.values(), key=lambda x: x.thing_id)
            ],
            "queue": [
                {
                    "work_id": w.work_id,
                    "target_id": w.target_id,
                    "attachment_id": w.attachment_id,
                    "kind": w.kind,
                    "payload": deepcopy(w.payload),
                    "order": w.order,
                    "durable": w.durable,
                }
                for w in self.queue
                if w.durable
            ],
            "pending_deliveries": [
                {
                    "work_id": w.work_id,
                    "target_id": w.target_id,
                    "attachment_id": w.attachment_id,
                    "kind": w.kind,
                    "payload": deepcopy(w.payload),
                    "order": w.order,
                    "durable": w.durable,
                }
                for w in self.pending_deliveries
                if w.durable
            ],
            "external_waits": [
                {
                    "wait_id": w.wait_id,
                    "attachment_id": w.attachment_id,
                    "service_name": w.service_name,
                    "correlation_id": w.correlation_id,
                    "restore_policy": w.restore_policy,
                    "requested_logical_tick": w.requested_logical_tick,
                }
                for w in self.external_waits
                if w.restore_policy != "session_only"
            ],
        }

    @classmethod
    def restore(
        cls,
        snapshot: dict[str, Any],
        *,
        current_authored_revision: str,
        behavior_catalog: dict[str, dict[str, int]],
        behavior_migrations: dict[tuple[str, int, int, int, int], BehaviorMigration] | None = None,
        emit_restore_event: bool = False,
    ) -> "World":
        behavior_migrations = behavior_migrations or {}
        if snapshot.get("schema") != "smx007-snapshot-research-v1":
            raise CompatibilityError("unsupported snapshot schema")
        if snapshot.get("authored_revision") != current_authored_revision:
            raise CompatibilityError("authored revision mismatch requires explicit world migration")

        staged = cls(
            authored_revision=current_authored_revision,
            world_tick=int(snapshot["world_tick"]),
        )
        staged._next_order = int(snapshot.get("next_order", 0))

        for record in snapshot.get("things", []):
            thing = RuntimeThing(
                thing_id=record["thing_id"],
                authored_basis=deepcopy(record["authored_basis"]),
                public_state=deepcopy(record.get("public_state", {})),
                provenance=deepcopy(record.get("provenance", {})),
                residency=record["residency"],
                activity=record.get("activity"),
                active_ticks=int(record.get("active_ticks", 0)),
                selected_physics_state=deepcopy(record.get("selected_physics_state", {})),
                refs=deepcopy(record.get("refs", {})),
            )

            for b in record.get("behaviors", []):
                definition_id = b["definition_id"]
                current = behavior_catalog.get(definition_id)
                if current is None:
                    raise CompatibilityError(f"missing behavior definition: {definition_id}")
                old_revision = int(b["revision"])
                old_schema = int(b["private_schema"])
                new_revision = int(current["revision"])
                new_schema = int(current["private_schema"])
                private_state = deepcopy(b.get("private_state", {}))

                if (old_revision, old_schema) != (new_revision, new_schema):
                    key = (definition_id, old_revision, new_revision, old_schema, new_schema)
                    migration = behavior_migrations.get(key)
                    if migration is None:
                        raise CompatibilityError(
                            f"behavior/private-state mismatch for {definition_id}: "
                            f"{old_revision}/{old_schema} -> {new_revision}/{new_schema}"
                        )
                    private_state = migration(private_state)

                thing.behaviors[b["attachment_id"]] = BehaviorRuntime(
                    attachment_id=b["attachment_id"],
                    definition_id=definition_id,
                    revision=new_revision,
                    private_schema=new_schema,
                    private_state=private_state,
                    prng_state=int(b["prng_state"]),
                )

            for t in record.get("timers", []):
                thing.timers.append(
                    TimerRecord(
                        timer_id=t["timer_id"],
                        attachment_id=t["attachment_id"],
                        continuation_id=t["continuation_id"],
                        clock_domain=t["clock_domain"],
                        remaining_active_ticks=t.get("remaining_active_ticks"),
                        due_world_tick=t.get("due_world_tick"),
                        payload=deepcopy(t.get("payload", {})),
                        durable=bool(t.get("durable", True)),
                    )
                )

            staged.things[thing.thing_id] = thing

        for t in snapshot.get("tombstones", []):
            staged.tombstones[t["thing_id"]] = Tombstone(
                thing_id=t["thing_id"],
                destroyed_world_tick=int(t["destroyed_world_tick"]),
                reason=t.get("reason"),
            )

        def restore_work(records: list[dict[str, Any]]) -> list[QueuedWork]:
            return [
                QueuedWork(
                    work_id=w["work_id"],
                    target_id=w["target_id"],
                    attachment_id=w["attachment_id"],
                    kind=w["kind"],
                    payload=deepcopy(w.get("payload", {})),
                    order=int(w["order"]),
                    durable=bool(w.get("durable", True)),
                )
                for w in records
            ]

        staged.queue = restore_work(snapshot.get("queue", []))
        staged.pending_deliveries = restore_work(snapshot.get("pending_deliveries", []))
        staged.external_waits = [
            ExternalWait(
                wait_id=w["wait_id"],
                attachment_id=w["attachment_id"],
                service_name=w["service_name"],
                correlation_id=w["correlation_id"],
                restore_policy=w["restore_policy"],
                requested_logical_tick=int(w["requested_logical_tick"]),
            )
            for w in snapshot.get("external_waits", [])
        ]

        # Crucially: no creation events, no host service calls, no restored context.
        if emit_restore_event:
            staged.restore_events.extend(sorted(staged.things))

        return staged

    def deterministic_state(self) -> dict[str, Any]:
        """Canonical research projection used to compare pre/post restore state."""
        snap = self.snapshot(snapshot_id="<comparison>")
        snap.pop("snapshot_id", None)
        return snap

    def deterministic_digest(self) -> str:
        payload = json.dumps(
            self.deterministic_state(),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def apply_external_input(self, thing_id: str, key: str, value: Any) -> None:
        self.things[thing_id].public_state[key] = deepcopy(value)
