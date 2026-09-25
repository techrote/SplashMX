# SMX-051F — Visual compatible-endpoint Connection authoring

**Issue:** #119  
**Parent:** #76 / SMX-051  
**Dependency:** #117 / SMX-051D and PR #122 on authoritative `main`  
**Architecture:** v1 unchanged

## Product workflow

The ordinary Connection path is now:

1. create a visible source Thing;
2. choose its named **Clicked** event;
3. create/select a visible target Thing and give it the SMX-051D **Change its colour** Rule;
4. choose that target Thing and its named **Change colour** action;
5. create the Connection;
6. inspect the persistent author-facing card, for example **Button — Clicked → Lamp — Change colour**;
7. reopen/edit or delete the Connection from that card;
8. Play through the qualified exported Godot Web runtime;
9. physically click the source Thing;
10. observe the target Rule execute;
11. Stop and return to unchanged authored state.

The ordinary form contains no editable ThingId, PortId or ConnectionId fields. Internal port tools remain available only behind an explicit advanced disclosure, and stable IDs remain visible through Inspect for diagnostics.

## Mapping to canonical Port/Connection semantics

No second Connection model is introduced.

A visible Thing created through the ordinary Stage already has a real production input opportunity: the Godot adapter can report a primary pointer click against that stable ThingId. SMX-051F therefore exposes that capability canonically as:

- `PortId("clicked")`
- author label **Clicked**
- `PortKind.EVENT`
- `PortDirection.OUT`

SMX-051D's existing beginner colour Rule remains the implementation of the target action. Attaching or updating that Rule atomically ensures the same Thing exposes:

- `PortId("change-colour")`
- author label **Change colour**
- `PortKind.COMMAND`
- `PortDirection.IN`

The browser receives a read-only endpoint projection derived from those actual canonical ports and the attached SMX-051D Rule. Selecting names in the form still publishes an ordinary canonical `ConnectionRecord` with stable `ThingId + PortId` endpoints and an allocated stable `ConnectionId`.

Connection edits use the canonical `ReplaceConnection` transaction operation. It retains the existing `ConnectionId`, validates replacement endpoints through the same canonical Connection validator, and publishes only after the complete candidate document validates. Delete uses the existing `TombstoneConnection` operation.

The legacy raw `connect` bridge action remains available for retained conformance tests and deliberate advanced integrations. It is no longer the ordinary browser authoring path.

## Compatibility filtering and validation

The ordinary browser only offers source Things whose real canonical `clicked` port is EVENT/OUT.

It only offers target Things whose real canonical `change-colour` port is COMMAND/IN **and** whose existing SMX-051D visual-fill Rule is present. This keeps the first Connection slice on the exact event/action vocabulary already proven by #117.

Filtering is convenience, not semantic authority. `connect_named` validates that the selected endpoints still correspond to the bounded named capability immediately before publication, then the canonical `AddConnection` / `ReplaceConnection` operation validates the full Port kinds/directions again. Invalid pairing therefore cannot leave a partial Connection or partially advanced project revision.

If a target Rule is removed after a Connection was authored, the canonical Connection remains stable rather than being silently rewritten. The author-facing card marks it unavailable and tells the author to add the Rule again, edit the Connection or delete it. Play also rejects that stale route explicitly before dispatching target behaviour.

## Production runtime dispatch

Godot remains target-private.

During Play, the editor projection marks a visible source interactive if it has either:

- its own SMX-051D click Rule; or
- a live outgoing canonical Connection from its `Clicked` port.

A physical Godot pointer event crosses the existing bounded editor-live event endpoint with the source stable ThingId. `BrowserRuntimeSession.dispatch_pointer_event` then:

1. verifies Play is active;
2. verifies the source event is still the canonical EVENT/OUT capability;
3. resolves live outgoing canonical Connections;
4. verifies each target still exposes the canonical COMMAND/IN action and the SMX-051D visual-fill Rule;
5. dispatches the target's existing `pointer_click` constrained IR handler;
6. runs the current semantic tick;
7. returns bounded target visual updates to the generic Godot runtime.

The target behaviour is therefore still the SMX-051D Rule program containing the established `set_public visual.fill` instruction. The Connection does not create a second scripting or action engine.

The editor-live response may contain more than one target update. Godot applies each update to the private presentation binding identified by stable ThingId; Godot node/object identity never enters canonical Connection semantics.

## Evidence

`tests/production/test_smx051f.py` covers:

- named endpoint labels derived from real canonical Port records;
- compatibility filtering based on real target Rule capability;
- ordinary named creation producing stable canonical Thing/Port/Connection identity;
- canonical and author-level invalid pairing rollback with no partial mutation;
- stable ConnectionId across endpoint edit;
- canonical tombstone delete;
- Save/Reload preservation;
- semantic Play routing from source click to the target's existing Rule;
- stale-action recovery with authored state unchanged;
- Godot projection exposing connected source input without requiring a source Rule.

`tests/production/smx051f_editor_godot_harness.mjs` drives pinned Playwright Chromium against the production editor serving the exact exported Godot 4.7.2 Web runtime. It proves:

- the ordinary form uses named selects and no typed internal identity;
- incompatible targets are absent until their real Rule/action capability exists;
- a visible Connection card appears;
- the Connection can be reopened and materially retargeted while its ConnectionId remains stable;
- Save/Reload preserves it;
- the exported Godot runtime materializes source and target;
- a physical click on the source routes through the canonical Connection and changes the target through the #117 Rule;
- authored visual state and project revision remain unchanged during Play and after Stop;
- delete removes the ordinary visible Connection.

The retained SMX-051D direct Rule unit and real-Godot/Chromium campaigns remain in the same workflow and are required to stay green.

## Residual limitations

This slice deliberately supports the single proven beginner vocabulary **Clicked → Change colour**. It does not introduce a graph editor, arbitrary scripting, exhaustive event/action vocabulary, Library/Definition/grouping UI, final accessibility/localization/recovery hardening or final human verification.

A Change colour target currently derives its configured colour from the existing SMX-051D Rule. Broader reusable action configuration belongs to later vocabulary expansion rather than SMX-051F.

#118 may land before or after this work. SMX-051F does not modify its Library/Definition/grouping ownership.

## Architecture-v1 impact

None.

Canonical Thing, Port, Connection and Behaviour identities remain authoritative. The browser is still a disposable authoring projection; the new endpoint list is derived from canonical capabilities. The target action still executes through the existing constrained Rule IR. Godot remains a generic execution/rendering substrate with private engine identities, and runtime effects remain transient.
