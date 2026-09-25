# SMX-051E — grouping, reusable Definitions and visual Library

**Issue:** #118  
**Parent:** #76 / SMX-051  
**Architecture:** SplashMX Architecture v1.0 unchanged

## Author workflow delivered

The ordinary editor path is now:

`select visible Things → Group → move as a group → Make reusable → Library entry → Add instance → manipulate either instance → Save/Reload/Restart → Play`.

Groups remain canonical Things linked to their children by `RelationshipKind.CONTAINS`. The Stage renders group bounds and a movable author-facing caption from those canonical relationships; DOM hierarchy is not semantic ownership.

`Ungroup` dissolves an ordinary containment group while preserving each child `ThingId`. The group Thing is tombstoned and its containment relationships are removed or reparented transactionally. Reusable instance roots are not silently dissolved because that would invalidate the frozen Definition/instance lineage.

## Canonical reuse semantics

This slice reuses the existing SMX-023 operations rather than introducing a browser component model:

- `PromoteGroup` turns the existing containment subgraph into one local `DefinitionRecord` and first `InstanceRecord`.
- The first instance continues to use the exact pre-promotion concrete Things. No first-instance `ThingId` is destroyed or recreated.
- `InstantiateDefinition` allocates a fresh concrete `ThingId` for every Definition element and fresh containment relation identities for the new instance.
- Each Stage instance remains a concrete Thing subgraph associated with the same canonical `DefinitionId`.
- Independent visual edits on an instance concrete Thing also record an explicit `SetInstanceStateOverride`; the browser never substitutes DOM identity for this relationship.

The ordinary Library UI deliberately does not display `DefinitionId`, `ElementId` or `ThingId`. The Library card uses the group label, a small visual preview, visible-Thing count and instance count. Advanced Inspect retains the canonical identity projection.

## Group and instance transform behaviour

A group move is one semantic transaction over the visible descendants. It preserves child identities and containment while translating each descendant visual. For Timeline tracks targeting `visual.x` or `visual.y`, the authored keyframe values are translated by the same delta so the animation does not jump back to pre-group coordinates.

New Library instances are offset on creation so they are immediately distinguishable from the first instance. That placement is represented as instance-specific visual overrides, not by rewriting Definition identity.

When a Definition element contains authored Timeline tracks, instantiation remaps the concrete `target_thing_id` to the new element's concrete Thing and offsets position keyframes with the instance placement. This keeps the existing Timeline and Godot Play target validation valid for the new instance.

## Evidence

`tests/production/test_smx051e.py` pins:

- group/ungroup identity preservation;
- coherent group translation;
- first-instance identity preservation through `PromoteGroup`;
- distinct second-instance concrete identities with common Definition lineage;
- explicit instance visual overrides;
- Timeline target remapping;
- Godot Play projection of both instances;
- retained first-instance interactive Rule projection;
- Save/Reload and a fresh runtime reload from the durable store.

`tests/production/smx051e_editor_godot_harness.mjs` runs the product workflow in pinned real Chromium against the exact exported Godot 4.7.2 Web runtime used by SMX-051C/D. It performs visible multi-selection, Group, keyboard group movement, Ungroup, keyboard regrouping, Rule and Timeline authoring, Make reusable, visible Library instantiation, independent instance movement, Save/Reload, full editor-process restart, and real Godot Play projection.

## Rejected alternatives

- Browser DOM parentage as canonical grouping.
- Rebuilding the original group during Make reusable.
- Generating instance identities from hierarchy paths or labels.
- A browser-only component/Library registry parallel to `DefinitionRecord`.
- A second runtime or DOM Play implementation.
- Exposing canonical internal IDs as the ordinary authoring workflow.

## Residual limitations

This is deliberately the minimum SMX-051E reuse slice.

- Aggregate group direct manipulation currently provides translation; child resize/rotation remains available per concrete Thing. Nested component variants, aggregate scale/rotation and override-authoring UI are not added here.
- Architecture-v1 `DefinitionElementRecord` currently carries authored state and ports, not Behaviour attachments. Existing Rules on the promoted first instance are preserved and continue through real Godot input, but new instances do not invent or clone Behaviour attachments outside canonical Definition semantics. Broad Definition-owned Behaviour inheritance would require an explicit later semantic slice rather than a browser-side shadow model.
- Reusable instances are not Ungrouped in this slice; doing so would require an explicit canonical detach/break-instance semantic.
- Connections redesign remains #119.

## Architecture-v1 impact

None. Architecture v1 remains frozen. The implementation projects existing Thing, containment, Definition, instance, override, persistence and Godot boundaries into a comprehensible author surface and does not introduce a new compatibility boundary.
