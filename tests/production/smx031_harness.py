#!/usr/bin/env python3
"""SMX-031 durable integration harness over SplashMX production modules.

This is deliberately an integration fixture, not a second semantic model.  Every
operation delegates to the production canonical, serialization, storage, execution,
capability, hot-replacement, lifecycle and streaming modules introduced by
SMX-023..030.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sys
import tempfile
from typing import Mapping

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from splashmx.canonical.core import (  # noqa: E402
    AddBehaviourAttachment,
    AddConnection,
    AddThing,
    AssetId,
    BehaviourAttachmentId,
    BehaviourAttachmentRecord,
    ConnectionEndpoint,
    ConnectionId,
    ConnectionRecord,
    DefinitionId,
    ElementId,
    InstantiateDefinition,
    PortDirection,
    PortId,
    PortKind,
    PortRecord,
    ProjectId,
    ProjectRevisionId,
    PromoteGroup,
    ReferenceState,
    RelationId,
    SemanticTransaction,
    SetContainment,
    ThingId,
    ThingRecord,
    apply_transaction,
    empty_document,
)
from splashmx.canonical.serialization import (  # noqa: E402
    CanonicalProjectRevision,
    ProtectedAssetRevision,
)
from splashmx.execution.hotswap import (  # noqa: E402
    PrivateStateMigration,
    ReplacementContract,
    replace_behaviour,
)
from splashmx.execution.ir import (  # noqa: E402
    BudgetLimits,
    IRHandler,
    IRInstruction,
    IRProgram,
    compile_rule,
    literal,
)
from splashmx.runtime.lifecycle import (  # noqa: E402
    WorldRuntime,
    deserialize_world_save,
    restore_world_save,
    serialize_world_save,
)
from splashmx.runtime.streaming import (  # noqa: E402
    ArtifactKind,
    ImmutableArtifactCache,
    MappingArtifactSource,
    StreamingRuntime,
    ThingStreamSpec,
    descriptor_for,
    encode_ir_artifact,
    encode_project_artifact,
)
from splashmx.security.capabilities import (  # noqa: E402
    CapabilityBroker,
    CapabilityId,
    CapabilityRequirement,
    CapabilityScope,
    PrincipalId,
)
from splashmx.storage.local import SQLiteProjectStore  # noqa: E402

PROJECT = ProjectId("smx031-project")
GROUP = ThingId("group")
CHILD = ThingId("group-child")
COPY_GROUP = ThingId("group-copy")
COPY_CHILD = ThingId("group-copy-child")
BUTTON = ThingId("button")
WORKER = ThingId("worker")
INVENTORY = ThingId("inventory")
BOMB = ThingId("budget-bomb")
RULE_SLOT = BehaviourAttachmentId("rule")
WORKER_SLOT = BehaviourAttachmentId("worker")
BOMB_SLOT = BehaviourAttachmentId("bomb")
AUDIO = AssetId("protected-audio")
CONNECTION = ConnectionId("button-to-worker")

DEFAULT_BUDGETS = BudgetLimits(instruction_steps=64)


def _tx(revision: str, *operations) -> SemanticTransaction:
    return SemanticTransaction(ProjectRevisionId(revision), tuple(operations))


def rule_program() -> IRProgram:
    return compile_rule(
        "button-click-rule",
        "clicked",
        [
            {"action": "add_public", "key": "clicks", "value": 1},
            {"action": "emit", "event": "clicked-counted", "payload": {"public": "clicks"}},
        ],
        behaviour_revision="button-rule:1",
    )


def worker_program_v1() -> IRProgram:
    return IRProgram(
        "worker:1",
        (
            IRHandler(
                "step",
                "step",
                (
                    IRInstruction("add_public", {"key": "score", "value": literal(1)}),
                    IRInstruction("add_private", {"key": "count", "value": literal(1)}),
                ),
            ),
        ),
        private_defaults={"count": 0},
    )


def worker_program_v2() -> IRProgram:
    return IRProgram(
        "worker:2",
        (
            IRHandler(
                "step-v2",
                "step",
                (
                    IRInstruction("add_public", {"key": "score", "value": literal(2)}),
                    IRInstruction("add_private", {"key": "count", "value": literal(2)}),
                ),
            ),
        ),
        private_defaults={"count": 0},
    )


def budget_bomb_program() -> IRProgram:
    return IRProgram(
        "budget-bomb:1",
        (
            IRHandler(
                "explode",
                "explode",
                (
                    IRInstruction("set_public", {"key": "committed", "value": literal(True)}),
                    IRInstruction(
                        "repeat",
                        {
                            "count": 1000,
                            "body": (IRInstruction("noop", {}),),
                        },
                    ),
                ),
            ),
        ),
    )


def program_catalog() -> dict[str, IRProgram]:
    programs = (rule_program(), worker_program_v1(), budget_bomb_program())
    return {program.behaviour_revision: program for program in programs}


def protected_asset(label: str = "original") -> ProtectedAssetRevision:
    marker = "1" if label == "original" else "2"
    return ProtectedAssetRevision.create(
        AUDIO,
        source_digest="sha256:" + marker * 64,
        source_identity={"name": f"{label}.wav", "source": "author-import"},
        source_metadata={"channels": 2, "sample_rate": 48000, "frames": 96000},
        media_semantics={"kind": "audio", "loop": False, "gain_db": 0},
        provenance={"origin": label, "capture": "fixture"},
        licence_attribution={"licence": "CC0", "attribution": "fixture"},
        derivation_lineage=({"operation": "source", "parent": None},),
    )


def build_document():
    clicked = PortRecord(PortId("clicked"), "Clicked", PortKind.EVENT, PortDirection.OUT)
    activate = PortRecord(PortId("activate"), "Activate", PortKind.COMMAND, PortDirection.IN)
    doc = empty_document(PROJECT, ProjectRevisionId("p0"))
    doc = apply_transaction(
        doc,
        _tx(
            "p1",
            AddThing(ThingRecord(GROUP, "Reusable group", authored_state={"kind": "group"})),
            AddThing(ThingRecord(CHILD, "Grouped child", authored_state={"value": 1})),
            AddThing(ThingRecord(BUTTON, "Button", authored_state={"clicks": 0}, ports={clicked.port_id: clicked})),
            AddThing(ThingRecord(WORKER, "Worker", authored_state={"score": 0}, ports={activate.port_id: activate})),
            AddThing(ThingRecord(INVENTORY, "Inventory", authored_state={"durable_target": str(WORKER)})),
            AddThing(ThingRecord(BOMB, "Budget boundary", authored_state={"committed": False})),
            SetContainment(CHILD, GROUP, RelationId("group-contains-child")),
            AddBehaviourAttachment(BUTTON, BehaviourAttachmentRecord(RULE_SLOT, "button-rule:1")),
            AddBehaviourAttachment(WORKER, BehaviourAttachmentRecord(WORKER_SLOT, "worker:1")),
            AddBehaviourAttachment(BOMB, BehaviourAttachmentRecord(BOMB_SLOT, "budget-bomb:1")),
            AddConnection(
                ConnectionRecord(
                    CONNECTION,
                    ConnectionEndpoint(BUTTON, PortId("clicked")),
                    ConnectionEndpoint(WORKER, PortId("activate")),
                )
            ),
        ),
    )
    doc = apply_transaction(
        doc,
        _tx(
            "p2",
            PromoteGroup(
                GROUP,
                DefinitionId("local-widget"),
                {GROUP: ElementId("root"), CHILD: ElementId("child")},
                {},
            ),
        ),
    )
    doc = apply_transaction(
        doc,
        _tx(
            "p3",
            InstantiateDefinition(
                DefinitionId("local-widget"),
                {ElementId("root"): COPY_GROUP, ElementId("child"): COPY_CHILD},
                {ElementId("child"): RelationId("copy-contains-child")},
            ),
        ),
    )
    return doc


def build_project(asset: ProtectedAssetRevision | None = None) -> CanonicalProjectRevision:
    chosen = protected_asset() if asset is None else asset
    return CanonicalProjectRevision(build_document(), {chosen.asset_id: chosen})


@dataclass
class CoreFixture:
    project: CanonicalProjectRevision
    programs: Mapping[str, IRProgram]
    world: WorldRuntime

    @classmethod
    def create(cls, *, budgets: BudgetLimits | None = None) -> "CoreFixture":
        project = build_project()
        programs = program_catalog()
        world = WorldRuntime.create(
            project.document,
            programs,
            budgets=DEFAULT_BUDGETS if budgets is None else budgets,
            seed=31,
        )
        return cls(project, programs, world)

    def play(self) -> None:
        self.world.dispatch(BUTTON, "clicked")
        self.world.dispatch(WORKER, "step")
        self.world.runtime.run_current_tick()

    def stop_to_authored(self) -> WorldRuntime:
        """Stop by discarding transient Play state and rebuilding from authored state."""
        return WorldRuntime.create(
            self.project.document,
            self.programs,
            budgets=self.world.runtime.budgets,
            seed=self.world.runtime.seed,
        )

    def save_project(self, path: str | Path) -> CanonicalProjectRevision:
        with SQLiteProjectStore(path) as store:
            store.save(self.project)
            return store.load(PROJECT)

    def stream_worker(self) -> StreamingRuntime:
        basis = encode_project_artifact(self.project)
        worker_ir = encode_ir_artifact(worker_program_v1())
        descriptors = {
            "worker-ir": descriptor_for("worker-ir", ArtifactKind.BEHAVIOUR_IR, worker_ir),
            "worker-basis": descriptor_for(
                "worker-basis",
                ArtifactKind.CANONICAL_SUBGRAPH,
                basis,
                dependencies=("worker-ir",),
            ),
        }
        source = MappingArtifactSource({"worker-ir": worker_ir, "worker-basis": basis})
        return StreamingRuntime(
            self.world,
            protected_assets=dict(self.project.assets),
            catalog={WORKER: ThingStreamSpec(WORKER, ("worker-basis",))},
            descriptors=descriptors,
            fetcher=source,
            cache=ImmutableArtifactCache(),
        )

    def hot_replace_worker(self):
        return replace_behaviour(
            self.world.runtime,
            WORKER,
            WORKER_SLOT,
            worker_program_v2(),
            ReplacementContract(
                "worker-1-to-2",
                "worker:1",
                "worker:2",
                private_state=PrivateStateMigration("preserve"),
            ),
        )

    def required_network_capability(self) -> CapabilityRequirement:
        return CapabilityRequirement(
            CapabilityId("network.http"),
            CapabilityScope(
                frozenset({"https://api.example.com"}),
                frozenset({"GET"}),
                1024,
            ),
            required=True,
        )

    def deny_required_capability(self) -> None:
        broker = CapabilityBroker()
        broker.resolve_requirements(
            PrincipalId(f"behaviour:{WORKER}:{WORKER_SLOT}"),
            (self.required_network_capability(),),
            now=1,
        )


def restore_probe(project_db: str | Path, world_save_path: str | Path) -> dict[str, object]:
    """Load canonical + WorldSave state in this process and return semantic evidence."""
    with SQLiteProjectStore(project_db) as store:
        project = store.load(PROJECT)
    snapshot = deserialize_world_save(Path(world_save_path).read_bytes())
    result = restore_world_save(
        snapshot,
        project.document,
        program_catalog(),
        budgets=DEFAULT_BUDGETS,
    )
    world = result.world
    asset = project.assets[AUDIO]
    return {
        "project_revision_id": str(project.document.project_revision_id),
        "worker_reference_state": world.reference_state(WORKER).value,
        "worker_score": world.runtime.states[WORKER].public_state["score"],
        "worker_private_count": world.runtime.states[WORKER].private_by_attachment[WORKER_SLOT]["count"],
        "inventory_target": project.document.things[INVENTORY].authored_state["durable_target"],
        "connection_id": str(project.document.connections[CONNECTION].connection_id),
        "asset_revision_digest": asset.revision_digest,
        "asset_source_digest": asset.source_digest,
    }


def complete_vertical_flow(workdir: str | Path) -> dict[str, object]:
    """Exercise the production local/offline vertical in one reusable fixture."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    fixture = CoreFixture.create()
    fixture.play()
    before_stop = {
        "clicks": fixture.world.runtime.states[BUTTON].public_state["clicks"],
        "score": fixture.world.runtime.states[WORKER].public_state["score"],
        "count": fixture.world.runtime.states[WORKER].private_by_attachment[WORKER_SLOT]["count"],
    }
    snapshot = fixture.world.snapshot("vertical-save")
    world_path = workdir / "worldsave.json"
    world_path.write_bytes(serialize_world_save(snapshot))
    db_path = workdir / "project.sqlite3"
    reloaded = fixture.save_project(db_path)
    stopped = fixture.stop_to_authored()
    return {
        "fixture": fixture,
        "before_stop": before_stop,
        "reloaded": reloaded,
        "stopped": stopped,
        "project_db": db_path,
        "world_save": world_path,
    }


def _main(argv: list[str]) -> int:
    if len(argv) == 4 and argv[1] == "restore-probe":
        print(json.dumps(restore_probe(argv[2], argv[3]), sort_keys=True))
        return 0
    if len(argv) == 2 and argv[1] == "smoke":
        with tempfile.TemporaryDirectory() as tmp:
            result = complete_vertical_flow(tmp)
            print(json.dumps({"before_stop": result["before_stop"]}, sort_keys=True))
        return 0
    raise SystemExit("usage: smx031_harness.py restore-probe PROJECT_DB WORLDSAVE | smoke")


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
