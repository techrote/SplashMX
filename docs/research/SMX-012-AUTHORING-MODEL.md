# SMX-012 — Authoring projection and progressive-disclosure model

**Status:** pre-Architecture-v1 research result; authoring contract candidate, not production UI design  
**Issue:** SMX-012 / #12  
**Date:** 2026-09-19  
**Evidence:** `SMX-012-AUTHORING-FIXTURES.json` and `experiments/smx-012-authoring-model/`

## Question and conclusion

Can SplashMX's object, execution, document, lifecycle, security, multiplayer, and collaboration semantics still project to a creative tool rather than an engine front-end?

At spec/model level: **yes, provided progressive disclosure reveals more of the same semantics rather than creating a beginner model that later converts to a different “real” system.** The durable core vocabulary remains **Things, Behaviours, and Connections**. Stage, Timeline, Rules, Components, Together, People, Publish, and Inspect are views over those semantics, not new ownership domains.

The fixtures walk all `C-001` through `C-028` representative cases, and the experiment adds adversarial/boundary tests for identity, grouping, reuse, stable ports, Timeline optionality, authored/runtime separation, multiplayer/collaboration separation, diagnostics, and protected media revisions. This strengthens H-016 at model level. SMX-019 must still falsify usability in a real browser slice.

Flash is a floor, not the ceiling. Direct manipulation, Timeline and reusable-symbol lessons are retained where they fit the object fabric; historical object categories and toolchain coupling are not made canonical for familiarity.

## Author-facing vocabulary

| Term/view | Responsibility | Canonical projection | Must not become |
|---|---|---|---|
| **Thing** | Something with stable identity/state; groups are Things too. | `ThingId`, state, facets, relations. | Engine object, hierarchy-path identity, network subclass. |
| **Behaviour** | Reusable intent attached to a Thing. | Stable attachment + common constrained IR. | Arbitrary host code or hidden manager. |
| **Connection** | Explicit communication between Things. | Stable command/event/value ports + connection record. | Direct foreign-state mutation or tree path. |
| **Stage** | Direct manipulation, presentation and structural grouping. | Thing presentation/containment. | Behavioural/control/authority ownership. |
| **Timeline** | Authored values and cues over time. | Tracks/cues targeting stable semantic loci. | Universal program flow. |
| **Rules** | Readable trigger/condition/action projection. | Same Behaviour/Connection semantics as advanced logic. | Second interpreter. |
| **Components** | Reuse ordinary authored structure. | Definition + instance + sparse overlay. | Separate prefab/class language. |
| **Together** | Configure runtime multiplayer intent. | Control/authority/replication/relevance declaration. | Collaboration, peer IDs, transports or RPCs. |
| **People** | Presence, edit history and conflicts. | Collaboration awareness/history/conflict state. | Runtime replication/authority. |
| **Publish** | Validate creation for a generic player/share target. | Canonical revision + target/capability contract. | Author-operated build/export pipeline. |
| **Inspect** | Reveal precise SplashMX semantic details. | IDs, ports, relationships, capabilities, diagnostics. | Substrate/toolchain contract. |

## Progressive disclosure

Disclosure levels are UI defaults, **not document modes**. Opening or hiding an advanced view cannot rewrite canonical meaning.

1. **Canvas** — Stage, direct properties, Play, Save and Publish. Draw/import, move, group and preview without learning a programming language or build system.
2. **Interactive** — adds Behaviours, Rules and Timeline when needed. “When clicked → toggle lamp” targets the same accepted execution semantics used later.
3. **Reuse** — adds Connections and Components. “Make reusable” promotes an ordinary group to a local definition while preserving the concrete first instance identities.
4. **Together** — adds runtime multiplayer presets and the deliberately separate People/collaboration surface. Presets include **Local only**, **One per player**, **Shared**, and **Authority controlled**.
5. **Advanced** — adds Inspect, explicit stable ports/IDs, detailed Behaviour/Connection views, definition/instance overlays, capabilities, and the real control/authority/replication/relevance axes. It still does not switch to engine/network-transport semantics.

## Authoring invariants

- **AUTH-001 — Small core vocabulary.** Ordinary workflows remain centered on Things, Behaviours and Connections; views do not create new base object categories.
- **AUTH-002 — One semantic system.** Beginner and advanced views operate on the same canonical identities/state/relations; no easy→real conversion.
- **AUTH-003 — Stage is a projection.** Stage grouping/presentation does not imply behavioural, persistence, control or authority ownership.
- **AUTH-004 — Timeline is optional.** Timeline owns authored time-based values/cues, not general interactivity. Non-timeline projects are first-class.
- **AUTH-005 — Intent stays with the Thing.** Behaviours attach to Things/definitions; a global manager does not silently own their meaning.
- **AUTH-006 — Connections use stable interfaces.** They target stable ports/IDs, not labels, tree positions or engine paths.
- **AUTH-007 — Grouping is semantic-safe.** Reparent/regroup changes containment/locality only unless another relationship is explicitly edited.
- **AUTH-008 — Reuse grows from ordinary structure.** “Make reusable” promotes a normal group while preserving the first concrete instance Thing identities.
- **AUTH-009 — Components continue the same model.** Definition + instance + sparse overlay remains the model; there is no second prefab/class architecture.
- **AUTH-010 — Rules are a projection.** Beginner trigger/condition/action rules lower to accepted Behaviour/Connection semantics.
- **AUTH-011 — Advanced logic shares execution semantics.** Graph/text/advanced Behaviour authoring targets the same constrained IR/capability boundary.
- **AUTH-012 — Edit and Play planes stay distinct.** Preview runtime state does not silently become authored project state.
- **AUTH-013 — Publish is not compilation to the author.** Normal Publish hands a validated revision to a generic player; ordinary authors do not operate per-creation builds.
- **AUTH-014 — Multiplayer is authored in SplashMX terms.** Simple choices express local/per-player/shared/authority-controlled intent without transport/session jargon.
- **AUTH-015 — Multiplayer presets are projections.** Presets populate the same authored network declaration Advanced view exposes.
- **AUTH-016 — Advanced networking preserves relationship separation.** Control, simulation authority, replication and relevance remain distinct; containment is not a substitute.
- **AUTH-017 — Runtime multiplayer and collaborative editing are visibly distinct.** Together configures runtime play; People handles authoring presence/history/conflicts.
- **AUTH-018 — Presence is transient awareness.** Cursor, selection, typing/viewport and live-session handles do not become canonical creation state or durable edits.
- **AUTH-019 — Human-visible conflict semantics survive the UI.** Ambiguous edits retain/show alternatives rather than hiding a substrate winner. Convergence is not enough.
- **AUTH-020 — Diagnostics use author language.** Ordinary errors speak about Things, reusable parts, permissions, unloaded content, competing edits and unsupported features rather than substrate jargon.
- **AUTH-021 — Capability denial is understandable and fail-closed.** UI explanation/request cannot turn denial into ambient authority or bypass mediation.
- **AUTH-022 — Media identity/provenance stays protected.** Stable `AssetId` is preserved while each immutable digest plus **source/audio/provenance** metadata remains one atomic revision bundle; UI operations cannot synthesize mixed provenance.
- **AUTH-023 — Partial loading has an author concept.** A `known-unloaded` Thing/reference is “not loaded yet”, not a broken hierarchy link; destroyed/unknown/incompatible remain distinguishable.
- **AUTH-024 — Dependency/compatibility failure is actionable without package-manager literacy.** Exact IDs/versions may be in Inspect, not mandatory beginner vocabulary.
- **AUTH-025 — Object count does not multiply conceptual tax.** Many Things may cost runtime resources but do not require more managers/modes.
- **AUTH-026 — Materially different media use the same conceptual fabric.** UI, audio, gameplay, physics, procedural, streaming, networking, persistence and collaboration do not gain category-specific ownership systems.
- **AUTH-027 — Disclosure is non-semantic.** Showing Advanced/Inspect cannot mutate content, privilege, multiplayer policy or collaboration history.
- **AUTH-028 — Beginner simplicity is a tested contract.** SMX-019 must fail the architecture if create→behave/connect→play→save/reload→publish/load requires engine, schema, transport or build concepts despite friendly labels.

## Stage, Timeline, Behaviours, Rules and Connections

**Stage** answers “what is here and how is it arranged?” **Timeline** answers “what authored values/cues change over time?” Timeline is central to C-001/C-002/C-008 but may be absent for C-003/C-005/C-009/C-013. **Behaviours** answer “what can this Thing do or respond to?” **Rules** are a compact readable projection of those semantics. **Connections** answer “how do Things communicate through stable interfaces?”

This prevents whichever view is historically familiar from becoming a hidden semantic owner. Timeline is optional; a button, physics interaction, procedural system or multiplayer object can be interactive with no authored timeline.

## Ordinary group → reusable component

Select normal Things → Group → **Make reusable**. The group remains a Thing. Promotion records a local definition with stable element/public-port provenance while the selected concrete structure remains the first instance. Further instances use sparse overlays. Compatible definition edits propagate to unoverridden loci; target-invalidating edits surface reconciliation conflicts instead of silently discarding local work. SMX-013 must extend this exact path into portable packages rather than introduce another component object type.

## Runtime multiplayer authoring

SMX-010 requires containment, control, simulation authority, replication and relevance to stay distinct. Simple authoring projects them as presets:

- **Local only** — one local runtime, no replication.
- **One per player** — one instance/association per authenticated participant; that principal supplies control intent; topology policy determines simulation authority.
- **Shared** — one shared logical Thing with declared controllers and replicated state/events.
- **Authority controlled** — participants provide intent while authoritative runtime policy decides simulation state.

Advanced Together reveals the same declaration fields. Current peer IDs, authority epochs, WebRTC/WebSocket/ENet choice, RPC annotations and reconnect tokens remain runtime/adapter context, never durable author content. SMX-017 must test this projection against real topologies.

## Collaborative editing is a different surface

People shows collaborators, transient presence, history and explicit conflicts. It does not reuse runtime replication. Delete/edit, same-property, reparent, definition/instance, timeline, grouping, component-update and connection races follow SMX-011's human-visible policies. Presence remains transient; offline edit history remains causal semantic transactions; stale permissions are revalidated on reunion. A creation can be single-author multiplayer, collaboratively authored single-player, both or neither.

## Protected source/audio/provenance semantics

SMX-012 preserves the existing media boundary without relaxation. `AssetId` remains the stable logical reference. Import/replacement changes an immutable revision only as a complete bundle: digest, source identity/metadata, audio identity/metadata, and provenance/licensing/derivation metadata. Partial replacement is rejected. Concurrent alternatives cannot be field-merged into a synthetic revision no author produced. Derived/import cache state cannot replace canonical source identity.

The experiment tests both complete replacement and failed partial replacement with no mutation of the prior revision.

## Diagnostics

Ordinary wording is stable SplashMX vocabulary; Inspect may reveal exact semantic IDs and compatibility/capability details. Examples:

- known-unloaded Door → “Door is not loaded yet. Load it to edit or inspect it.”
- denied Camera behaviour → “Camera behaviour is not allowed to use that device or service.”
- missing component → “A required reusable part is unavailable or incompatible.”
- collaboration conflict → “Button has competing edits. Choose or combine the retained alternatives.”

Current engine object/resource/script terminology, transport names, package-manager concepts and build/export machinery are not required ordinary workflow knowledge. Leakage is an architecture-boundary failure, not merely copy to polish later.

## Existing-tool lessons, not architecture imports

Adobe Animate documents a Stage/Timeline model and reusable symbols/instances, including nested movie-clip timelines. Those remain useful immediacy/reuse precedents, while fixed symbol categories and runtime coupling are not copied. Primary references checked 2026-09-19: https://helpx.adobe.com/animate/desktop/using/time.html and https://helpx.adobe.com/animate/desktop/multimedia-and-video/symbols.html .

Construct 3 demonstrates readable condition/action event authoring and reusable Behaviors/Families. SplashMX takes the readability lesson but does not make a global event sheet the canonical hidden owner of object intent. Primary references checked 2026-09-19: https://www.construct.net/en/make-games/manuals/construct-3/project-primitives/events/how-events-work and https://www.construct.net/en/make-games/manuals/construct-3/project-primitives/objects/families .

GameMaker's object events show the accessibility of “this object responds when…” and coexistence of visual/text logic. SplashMX keeps that readability without adopting a fixed engine event list or room/object runtime identity as its compatibility boundary. Primary reference checked 2026-09-19: https://manual.gamemaker.io/lts/en/GameMaker_Language/GML_Reference/Asset_Management/Objects/Object_Events/Generating_Object_Events.htm .

Rejected direct imitations: separate easy/advanced project types; scene-tree ownership as primary author model; global event sheet as sole truth; Timeline as universal program; a “network object” subclass; collaboration as a multiplayer mode; component wizard producing a separate class language; default package-manager UI; raw engine error passthrough; loose media metadata replacement.

## Corpus and executable evidence

`SMX-012-AUTHORING-FIXTURES.json` maps `UX-001` through `UX-028` across all 28 representative C-cases and selected A-cases. The non-production Python model verifies one canonical projection through disclosure levels; group/reparent/reuse; common Rule/Behaviour IR target; stable port connections; optional Timeline; transient Play; generic-player Publish; preset/advanced network equivalence; collaboration/presence separation; author-language diagnostics; and protected asset replacement.

The adversarial suite includes duplicate identity, invalid connection endpoints, leaf→component shortcut rejection, advanced network fields outside the accepted declaration, transient state persistence checks, explicit conflict alternatives, invalid publish target, and partial protected-media revision rejection.

Passing means the contracts are **projectable**, not that a production editor is usable or performant.

## SMX-019 gates

`UXG-001` through `UXG-012` are acceptance gates, not suggestions:

1. blank-canvas Thing creation without engine/build vocabulary;
2. Timeline animation plus equally valid non-Timeline interaction;
3. beginner Rule and advanced Behaviour use the same accepted IR semantics;
4. Connections target stable ports, not hierarchy paths;
5. ordinary group→reusable definition preserves first-instance Thing identities;
6. Play/stop/edit/play keeps authored and runtime state separate;
7. save/reload excludes selection/presence/peer/play-session context;
8. Publish/load exercises the generic player without author-operated build/export;
9. simple multiplayer presets and Advanced edit the same declaration with no transport/session IDs;
10. People/history/conflicts remain visibly separate from Together and presence stays transient;
11. ordinary failures use author vocabulary; substrate/toolchain leakage fails acceptance;
12. media import/replacement preserves stable AssetId and complete digest/source/audio/provenance bundle atomically.

SMX-019 should additionally measure discoverability, click/gesture count, author vocabulary encountered, browser constraints, error recovery and preview/publish latency.

## H-016 and handoff

**H-016 strengthened at authoring-projection/model level; real browser usability remains unproven.** Every C-case can be expressed without a new base object category; beginner and advanced execution share semantics; ordinary grouping grows into reuse; multiplayer presets project the same relationship axes; collaboration stays separate; and protected media semantics survive authoring. No user study establishes final terminology, and no browser editor yet measures cognitive or interaction friction.

Downstream requirements:

- **SMX-013:** package/component UX starts from AUTH-008/009 and preserves AUTH-021/022/024.
- **SMX-014:** publishing implements AUTH-013 and compatible author-language failures.
- **SMX-017:** real topology tests preserve AUTH-014–016.
- **SMX-018:** convergence is not enough; conflict harness results must remain expressible through AUTH-017–019.
- **SMX-019:** execute all UXG gates; do not disguise architecture leakage with friendly labels.

Residual risks are terminology comprehension, large-rule readability, nested Timeline locality, component-update conflict UX, capability-prompt fatigue, advanced authority wording, accessibility/localization, and navigation at large object counts. None currently requires a second object/execution model.
