# SMX-037 Godot binding selection spike

This experiment is a bounded Phase-6 mechanism-selection spike. It is not the production Godot adapter owned by SMX-038.

The workload is exported from the real SMX-031 production-core fixture by `tools/export_smx037_fixture.py`. Godot receives stable SplashMX `ThingId` values, requested private target facets, deterministic scheduler inputs and exact protected-Asset revision references. It does not receive canonical ownership of Node/NodePath/RID/ResourceUID or protected-media fields.

Three private realization layouts are measured:

- `node_per_thing`: one private `Node2D` owner per Thing plus facet objects;
- `scene_subtree`: one private `Node` owner per Thing plus facet objects;
- `facet_sparse`: no mandatory per-Thing Node; create only the private engine objects required by render/input/physics/audio facets.

All candidates use the same centralized scheduler bridge. Semantic work is ordered by explicit SplashMX logical tick, author order and sequence before adapter effects are applied. SceneTree callback order is never semantic ordering authority.

The real campaign also destroys/recreates the worker binding repeatedly, verifies stable Thing identity and the exact protected Asset revision reference survive, injects forbidden engine-handle fields, reverses event insertion order, tests required/optional target-feature outcomes, and checks that semantic-only Things have zero Godot objects in the sparse layout.

Run inside a Godot 4.7.2 environment from the repository root:

```sh
PYTHONPATH=src:tests/production:tools python3 tools/measure_smx037.py \
  --godot godot --samples 7 \
  --output artifacts/smx037-godot-binding-evidence.json
```

CI additionally exports the same project source to Web and Linux profiles. The emitted timing, memory and object-count evidence is scoped to the named CI runtime/hardware. It is selection evidence, not a universal supported-target performance SLO.
