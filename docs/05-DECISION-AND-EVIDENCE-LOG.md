# SplashMX decision and evidence log

This is a compact durable register. Detailed research belongs in issue-specific documents; this file records what the project currently believes, why, and where to retrieve the evidence.

## Status vocabulary

- **FACT** — current primary-source fact, version/date sensitive where applicable.
- **HYPOTHESIS** — proposition awaiting or undergoing falsification.
- **DECISION** — accepted project choice with current evidence; pre-Architecture-v1 decisions remain falsifiable by later destructive work.
- **OPEN** — unresolved question/blocker.
- **REJECTED** — considered direction that should not be silently reintroduced without new evidence.

## Project decisions

### D-001 — Research before production editor

**Status:** DECISION.

Research object/execution/document/security/lifecycle semantics before building the production Flash-style editor so familiar UI metaphors do not hard-code Flash/Godot assumptions.

### D-002 — Godot is substrate, not canonical public contract

**Status:** DECISION.

Godot is the intended runtime/rendering substrate; SplashMX owns durable author-facing object/document/package semantics.

### D-003 — Runtime multiplayer and collaborative editing are distinct consistency problems

**Status:** DECISION.

They may share infrastructure but are researched and specified separately.

### D-004 — No arbitrary GDScript as default community execution model

**Status:** DECISION.

Community/user-authored executable intent crosses a constrained, inspectable, budgetable boundary rather than receiving arbitrary engine code access.

### D-005 — Generic runtime/player is the preferred publishing hypothesis

**Status:** HYPOTHESIS / PROVISIONAL DIRECTION.

Ordinary creations should ideally be data + constrained logic consumed by versioned generic web/native/server players rather than independently compiled Godot projects.

**Tested by:** SMX-009/014/017/019.

### D-006 — Destructive prototypes precede Architecture v1.0

**Status:** DECISION.

Architecture freeze is gated by integrated object-fabric, sandbox, network, collaboration, and browser vertical-slice falsification.

### D-007 — Stable evaluation IDs and explicit not-evaluated state

**Status:** DECISION.

Use `C-###`, `A-###`, and `S-##`; omitted applicable cases remain `N/E`, never implicit pass.

### D-008 — Scorecards do not waive constitutional hard gates

**Status:** DECISION.

Per-criterion scores are evidence aids; a hard-gate failure cannot be averaged away.

### D-009 — Research harness results require reproducibility metadata

**Status:** DECISION.

Executable research records question, hypothesis/corpus IDs, source commit, versions, commands, fixtures/seeds, expected invariant, result, and environmental caveats.

### D-010 — Durable Thing identity is independent of hierarchy/engine handle

**Status:** DECISION at semantic-requirement level; final concrete ID encoding remains open by design.

Thing identity survives rename/reparent/control/authority transfer and is distinct from labels, paths, Godot handles, process identity, peer IDs, storage location, and content digest.

**Source:** SMX-002 K-001/K-002/K-010; SMX-005 DOC-001/DOC-002/DOC-004; T-001/T-007/DT-001/DT-002.

### D-011 — Containment, control, authority, observation, persistence, and replication are separate semantics

**Status:** DECISION at object-fabric semantic level.

One overloaded `owner`/parent field must not stand for these dimensions.

**Source:** SMX-002 K-003/K-004; T-001/T-002.

### D-012 — Intrinsic declaration and runtime/editor context are separate planes

**Status:** DECISION at semantic level.

Thing state/facets may declare requirements/policy; current capability grants, controller/authority, sessions/services, selection, residency, diagnostics, and engine handles remain context unless explicitly projected/persisted.

**Source:** SMX-002 K-005/K-006/K-010; refined by SMX-005 DOC-003.

### D-013 — Command/event/value is the current port vocabulary; synchronous cross-Thing query is excluded

**Status:** DECISION at current pre-architecture semantic level; later network/destructive work may refine it.

Discrete intent uses commands, occurrences use events, and observable continuous/snapshot data uses directional values. Cross-Thing request/response is asynchronous command + correlated event (or a mediated service request); a synchronous query/method-call stack is not part of the current contract.

**Source:** SMX-002 port candidate; SMX-004 EXE-004/EXE-005/EXE-014.

### D-014 — Current kernel candidate is faceted Thing + explicit relation graph

**Status:** HYPOTHESIS / PROVISIONAL DIRECTION.

Stable Thing identity, intrinsic state namespaces, optional facets, explicit ports, typed relationships, and explicit context bindings form the current kernel candidate.

### D-015 — Local definitions use stable definition/element provenance distinct from concrete Thing identity

**Status:** DECISION at semantic-requirement level.

Reusable definitions have durable definition/element identity; concrete instances have their own Thing IDs plus explicit provenance. `instance-of` is provenance, not runtime ownership/control/authority.

**Source:** SMX-003 CMP-002–CMP-005; SMX-005 DOC-005; CT-001/CT-002/DT-003.

### D-016 — Instance variation is sparse explicit overlay over an immutable base revision

**Status:** DECISION at semantic level.

Instances record intentional departures/local additions/suppressions. Compatible base changes propagate to unoverridden loci; valid explicit overrides remain authoritative.

**Source:** SMX-003 CMP-006/CMP-007/CMP-011; SMX-005 DOC-005; CT-003/CT-004/CT-007/DT-003.

### D-017 — Definition updates reconcile transactionally and fail explicitly on invalidated targets

**Status:** DECISION at semantic level; persisted concurrent-conflict representation remains SMX-011 work.

Definition revision updates are planned before commit. Invalidated overrides/exposures/local attachments/protected destructive changes produce explicit conflicts and cannot leave half-migrated instances.

**Source:** SMX-003 CMP-008/CMP-009; SMX-005 DOC-011; CT-005/CT-006/CT-009/DT-007.

### D-018 — Public group/component interfaces are stable indirections over internal element ports

**Status:** DECISION at semantic level.

External connections target stable public port IDs; compatible internal reparent/replacement may rebind the implementation endpoint without external path repair.

**Source:** SMX-003 CMP-010; SMX-005 DOC-007; CT-008/CT-009/DT-004.

### D-019 — Behaviour executes as bounded transactional run-to-completion turns

**Status:** DECISION at candidate execution-semantic level; subject to SMX-015 destructive integration.

A behaviour activation reads committed state, makes provisional internal writes, stages follow-on work, and either atomically commits or rolls back. Events/commands/timers/service requests become observable only after successful state commit.

**Source:** SMX-004 EXE-001–EXE-003; ET-001/ET-002.

### D-020 — Long-lived work is explicit continuation/service state, not durable stackful coroutine state

**Status:** DECISION at candidate execution-semantic level.

`wait`/`await`-like author syntax lowers to explicit timers/continuations or asynchronous runtime-service requests. A suspended user stack is not the durable compatibility contract.

**Source:** SMX-004 EXE-005/EXE-007/EXE-013; ET-003/ET-005/ET-008.

### D-021 — Deterministic core execution is separated from explicit external nondeterminism

**Status:** DECISION at candidate execution-semantic level.

Given the same initial state, validated IR, ordered external inputs, logical time, and deterministic seed, core activation ordering/results must be reproducible. Wall clock, entropy, network/service/sensor/host results enter as explicit ordered external inputs.

**Source:** SMX-004 EXE-003/EXE-007/EXE-008/EXE-015; ET-003/ET-004/ET-005.

### D-022 — Behaviour-private state belongs to stable attachment identity; hot swap is quiescent and transactional

**Status:** DECISION at candidate execution-semantic level.

Private execution state belongs to the behaviour attachment, not the current code version. Replacement occurs between activations, preflights interfaces/state/capabilities/pending work, retains compatible state or uses explicit bounded pure migration, and maps/cancels/rejects pending continuations explicitly.

**Source:** SMX-004 EXE-010–EXE-013; ET-007–ET-009.

### D-023 — Execution/resource budgets are part of behaviour semantics

**Status:** DECISION at execution-boundary level; exact quotas/policies remain SMX-006/016 work.

The runtime must hard-cap activation instruction/cost units, emitted work, bounded iteration/allocation, timers/continuations/service requests, per-tick totals, and queued/private state. Ordinary user content cannot disable the hard caps.

**Source:** SMX-004 EXE-001/EXE-009; ET-002/ET-006.

### D-024 — Privileged/host work crosses explicit asynchronous capability-mediated services

**Status:** DECISION at execution-boundary level; capability delegation/grant model remains SMX-006 work.

Ordinary behaviour IR has no ambient filesystem/network/browser/Godot/native operation. A named service request is capability-checked, issued after internal activation commit, and returns success/error as a later activation.

**Source:** SMX-004 EXE-005/EXE-006/EXE-015; ET-005.

### D-025 — Canonical authored semantics are a typed logical record graph above physical encoding/store

**Status:** DECISION at pre-architecture semantic level; subject to SMX-015/020 destructive/final reconciliation.

SplashMX authored state is represented in terms of stable typed logical records/IDs, immutable revision lineage, explicit references/relations/ports/overlays/behaviour definitions, semantic transactions, and extension/feature declarations. JSON, CBOR, Protocol Buffers, SQLite, Godot Resources, or another technology may encode/store those semantics but may not redefine them.

**Reason:** the same semantic requirements span human-readable editing, partial loading, transactions, migration, collaboration, headless execution, and packaging; no single compared physical encoding solves those by itself.

**Source:** `docs/research/SMX-005-CANONICAL-DOCUMENT.md` DOC-001–DOC-016.

### D-026 — Logical semantic identity, immutable content identity, and storage location are distinct

**Status:** DECISION.

Things/definitions/elements/ports/connections/behaviour lineages/attachments/assets keep stable semantic IDs while content changes. Immutable blobs/revision payloads may use content digests. Chunk/database/file location is non-semantic.

**Source:** SMX-005 DOC-001/DOC-002/DOC-008/DOC-009; DT-001/DT-011.

### D-027 — Authored document, live runtime state, persistent save/world state, and transient context are separate canonical planes

**Status:** DECISION at semantic level; exact lifecycle projection remains SMX-007 work.

The editable project does not silently absorb live behaviour-private state, PRNG state, timers/continuations, active peer/capability/engine handles, or save-game progress. Explicit snapshots/saves may project selected runtime state into separate artefacts.

**Source:** SMX-005 DOC-003/DOC-006; DT-005.

### D-028 — Canonical edits are atomic semantic transactions targeting IDs/loci, not physical paths/rows

**Status:** DECISION at sequential edit-semantic level; concurrent merge remains SMX-011.

Transactions carry base revision/preconditions and ordered semantic operations. They plan/validate before commit and apply all-or-nothing. JSON Pointer paths, hierarchy paths, array indexes, file offsets, and DB row IDs are not the durable edit contract.

**Source:** SMX-005 DOC-011; DT-007; carries SMX-003 D-017 into the document layer.

### D-029 — Partial loading and reference absence states are first-class

**Status:** DECISION at document/reference semantic level; streaming scheduling remains SMX-008.

A catalog/index can identify records without loading them. References distinguish at least loaded, known-unloaded, tombstoned, unknown, incompatible, and external-dependency-unavailable states. `known_unloaded` is valid rather than dangling.

**Source:** SMX-005 DOC-014/DOC-015; DT-002/DT-009.

### D-030 — Schema/IR migration is deterministic, staged, validated, rollback-safe, and capability-free by default

**Status:** DECISION at migration-semantic level; concrete migration registry/signature/distribution remains later work.

Migrations declare source/target versions, transform a copy/staging representation, preserve semantic IDs/references unless an explicit atomic remap is required, preserve compatible optional extensions, reject unsupported required features, validate the entire target, and only then advance/replace the source revision.

**Source:** SMX-005 DOC-012/DOC-013/DOC-016; DT-006/DT-008.

### D-031 — Logical asset identity is separate from immutable blob identity

**Status:** DECISION.

Authored records reference `AssetId`; an asset record points to a verified immutable content digest/metadata. Updating imported media can retain `AssetId` while swapping the blob digest transactionally.

**Source:** SMX-005 DOC-002/DOC-008/DOC-011; DT-011.

### D-032 — Final production encoding/store remains deliberately open

**Status:** DECISION to defer a premature implementation lock-in.

SMX-005 does not choose JSON, deterministic CBOR, Protocol Buffers, SQLite, or another single technology as the public format. Candidate implementations must preserve D-025–D-031; SMX-009/014/019/020 can select concrete browser/native/package/store encodings using performance and compatibility evidence.

**Source:** SMX-005 representation-family comparison and DOC-009/DOC-010.



### D-033 — Ordinary content has no ambient host authority

**Status:** DECISION at security-boundary semantic level; subject to SMX-016 hostile proof.

Ordinary creations/components receive no implicit filesystem, network, clipboard, camera/microphone, geolocation, browser JavaScript, native-code, process, engine-reflection, or unrestricted resource-loading authority. Privileged effects cross named runtime services.

**Source:** `docs/research/SMX-006-CAPABILITY-SANDBOX.md` SEC-001/SEC-007/SEC-013; ST-001.

### D-034 — Host authority is a principal-scoped, narrowed, revocable lease rather than hierarchy inheritance

**Status:** DECISION at security semantic level.

Capability grants bind to explicit security principals with typed scopes/lifetimes. Containment/definition ancestry does not transfer privilege. Delegation requires an active delegable source grant and can only narrow scope/lifetime; source revocation invalidates delegated descendants.

**Source:** SMX-006 SEC-002–SEC-005/SEC-011; ST-003–ST-005.

### D-035 — Signatures/provenance do not grant ordinary runtime capability

**Status:** DECISION.

A valid signature may establish publisher identity, integrity, or update lineage, but does not by itself grant host services, larger resource budgets, or delegation rights.

**Source:** SMX-006 SEC-006/SEC-017; ST-009.

### D-036 — Browser/OS permission is a second independent gate beneath SplashMX capability policy

**Status:** DECISION.

A SplashMX grant is necessary before a runtime adapter requests a privileged browser/OS feature. Browser/OS permission is independently necessary and may expire/revoke. Neither layer implicitly grants the other.

**Source:** SMX-006 SEC-018; current W3C Permissions/Permissions Policy/Media Capture/Geolocation/Clipboard/Notifications specifications.

### D-037 — Ordinary community packages cannot enter Godot through executable host-code paths

**Status:** DECISION at ordinary-content boundary.

Untrusted SplashMX packages do not load arbitrary GDScript/C#, GDExtension/native libraries, JavaScriptBridge/eval, or executable Godot PCK/mod projects. Godot assets/facilities may be used only through validated SplashMX adapters and package/document contracts.

**Source:** SMX-006 SEC-013; Godot PCK, GDExtension, and web-compilation primary docs checked 2026-09-17.

### D-038 — Parser, canonical migration, IR execution, runtime services, and network ingress are independent security boundaries

**Status:** DECISION.

Each layer validates and budgets its own input. Passing an earlier layer does not make later input trusted, and browser/WASM/Godot sandboxing does not replace SplashMX validation/capability enforcement.

**Source:** SMX-006 SEC-007/SEC-008/SEC-014/SEC-015; ST-007/ST-008/ST-010/ST-012.

### D-039 — Hard resource limits extend across package parsing, dependencies, migrations, services, and network ingress

**Status:** DECISION at category level; exact quota values/policy remain downstream.

SMX-004 executor budgets are extended with package compressed/expanded bytes and ratio, entry/path counts, canonical record/depth/fanout limits, dependency depth/bytes, migration steps/cost/output, service request/response quotas, and network message/rate/queue ceilings.

**Source:** SMX-006 SEC-008; ST-007/ST-008/ST-011.

### D-040 — Capability grants/handles are runtime policy, not authored/save/network authority tokens

**Status:** DECISION at security semantic level.

Canonical authored documents, save-state records, package signatures, and ordinary network messages cannot mint or serialize live capability authority. Stable declarations may request capabilities; live grants remain host/user policy state.

**Source:** SMX-006 SEC-003/SEC-012/SEC-017; ST-009/ST-010.



### D-041 — Lifecycle uses orthogonal existence, residency, and activity axes

**Status:** DECISION at lifecycle semantic level; subject to SMX-015 integrated falsification.

A Thing's existence, residency, and activity are distinct. Save/snapshot is an atomic operation over runtime state, not a mutually exclusive lifecycle state. This permits present+resident+active, present+resident+dormant, present+unloaded, and tombstoned semantics without conflation.

**Source:** `docs/research/SMX-007-LIFECYCLE-RESTORE.md` LIF-001/LIF-002/LIF-010; LT-003/LT-004.

### D-042 — Persistent snapshots are quiescent simulation-state projections, not serialized process objects

**Status:** DECISION at runtime/save semantic level.

Snapshots are captured at bounded-turn quiescent boundaries and contain selected persistable runtime state addressed by stable IDs: mutable public/private state, deterministic PRNG state, durable timers/continuations/queued work, selected physics/timeline state, provenance, and tombstones as applicable. Restore must work in a fresh runtime without a surviving Godot/process object.

**Source:** SMX-007 LIF-003–LIF-006/LIF-013/LIF-016; LT-001/LT-009.

### D-043 — Pending work is classified; already-issued external side effects are never implicitly replayed on restore

**Status:** DECISION.

Pending work is classified as durable internal, session-ephemeral, reconstructible, or external wait. A prior HTTP/file/notification/etc. service call is not automatically reissued by restore. External waits require explicit cancel, host-resume, session-only, or author-reissue policy and never serialize host authority/handles.

**Source:** SMX-007 LIF-006–LIF-008; LT-005–LT-007.

### D-044 — Timer semantics name their clock domain; semantic dormancy differs from hidden implementation sleep

**Status:** DECISION.

`thing_active` timers pause during semantic dormancy/unload, `world_logical` deadlines continue with the authoritative world and may create wake/pending-delivery obligations for unloaded targets, while wall-clock time enters as explicit external input/service policy. Engine sleeping/LOD is allowed only when observationally equivalent.

**Source:** SMX-007 LIF-009/LIF-010; LT-004/LT-005.

### D-045 — Restore rebinds transient authority/context from current policy rather than restoring it from save data

**Status:** DECISION.

Godot/physics/audio handles, current peer/session IDs, controller/authority bindings, transport state, live capability grants, browser/OS permission objects, sockets/files/devices and other host handles are not save authority. Restore reconstructs simulation state first, then rebinds current context under the current runtime/network/security policy.

**Source:** SMX-007 LIF-004/LIF-008/LIF-017; SMX-006 D-040; LT-007.

### D-046 — Destruction produces tombstone semantics and ordinary respawn does not reuse the destroyed ThingId

**Status:** DECISION at lifecycle/reference semantic level; tombstone retention/compaction remains downstream.

A destroyed Thing becomes explicitly tombstoned for reference resolution. Ordinary respawn creates a new ThingId. Recreating the same historical ID is allowed only by selecting/restoring an earlier world revision/branch, not by silent identifier reuse in the current lineage.

**Source:** SMX-007 LIF-012/LIF-018; LT-011.

### D-047 — Deterministic restore is required; deterministic future replay requires the same external input stream

**Status:** DECISION at lifecycle determinism level.

Given the same compatible authored basis and snapshot, restore must reconstruct the same declared simulation state, durable scheduler state, logical clocks and PRNG positions before new external inputs are admitted. Future execution can diverge when user/network/service/wall-clock/sensor/entropy inputs differ; a save file is not automatically a replay log.

**Source:** SMX-007 LIF-015; LT-012.

## Primary-source and comparative evidence

### E-001 through E-014 — Godot/web/runtime baseline

**Status:** FACT, time-sensitive; checked/refreshed by SMX-001 as E-006–E-014.

Authoritative anchors remain in `docs/03-RAG-INDEX.md`: Godot release archive, web editor/export, runtime I/O/PCK, JavaScriptBridge build options, networking/WebRTC, and headless/dedicated-server documentation.

### E-015 — Godot core composition is scene/node-tree oriented

**Status:** FACT / conceptual comparison input.

Sources: Godot 4.7 key concepts and node/scene-instance documentation.

### E-016 — ECS precedent separates unique entities, optional components, and explicit relationships

**Status:** FACT / conceptual comparison input.

Sources: Bevy ECS guide and relationship example.

### E-017 — Actor precedent separates stable reference from encapsulated state/behaviour

**Status:** FACT / conceptual comparison input.

Sources: Akka actor-model documentation.

### E-018 — Prototype delegation is flexible but makes inherited lookup implicit

**Status:** FACT / conceptual comparison input.

Source: MDN prototype-chain guide.

### E-019 — Godot scene inheritance demonstrates base/local-modification trade-offs

**Status:** FACT / conceptual comparison input, checked 2026-09-17.

Source: https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/importing_3d_scenes/import_configuration.html

### E-020 — Unity prefab precedent supports linked instances, nesting, and explicit overrides

**Status:** FACT / conceptual comparison input, checked 2026-09-17.

Sources: Unity prefab introduction/overrides and Unity 6 prefab variants documentation.

### E-021 — Self prototype/delegation precedent shows seamless reuse and implicit-role costs

**Status:** FACT / conceptual comparison input, checked 2026-09-17.

Sources: Self Handbook 2024.1 world organization/programming guide/glossary.

### E-022 — W3C SCXML specifies run-to-completion event processing

**Status:** FACT / conceptual comparison input, checked 2026-09-17.

Source: https://www.w3.org/TR/scxml/

### E-023 — WebAssembly separates validated core modules from host embedding/imports

**Status:** FACT / conceptual comparison input, checked 2026-09-17.

Sources: https://webassembly.github.io/spec/ and current validation/execution sections.

### E-024 — Scratch separates visual authoring from VM program representation

**Status:** FACT / conceptual comparison input, checked 2026-09-17.

Source: https://github.com/scratchfoundation/scratch-editor/blob/develop/packages/scratch-vm/README.md

### E-025 — CEL specifies deterministic expression evaluation and cost concerns for untrusted expressions

**Status:** FACT / conceptual comparison input, checked 2026-09-17.

Sources: https://cel.dev/ and CEL language definition.

### E-026 — Starlark demonstrates deterministic/hermetic embedded-language restrictions

**Status:** FACT / conceptual comparison input, checked 2026-09-17.

Source: https://github.com/bazelbuild/starlark/blob/master/spec.md

### E-027 — JSON Schema separates generic JSON representation from explicit schema validation

**Status:** FACT / representation comparison input, checked 2026-09-17.

The JSON Schema specification site identifies Draft 2020-12 as the current published family and separates Core and Validation semantics.

Source: https://json-schema.org/specification

**Implication:** a readable JSON projection plus explicit schema metadata is viable, but JSON syntax alone is not SplashMX's canonical semantic contract.

### E-028 — Protocol Buffers preserves unknown binary fields but does not promise stable default serialized byte order

**Status:** FACT / representation comparison input, checked 2026-09-17.

Current protobuf documentation says unknown fields are retained in ordinary binary message workflows, while encoding documentation warns field serialization order/default bytes are an implementation detail and default serialization is not a portable stable-byte contract.

Sources:
- https://protobuf.dev/programming-guides/editions/
- https://protobuf.dev/programming-guides/encoding/

**Implication:** protobuf remains a candidate record encoding but must not define logical IDs/revisions by unspecified serializer bytes.

### E-029 — SQLite provides a durable application-file precedent with atomic transactions

**Status:** FACT / storage comparison input, checked 2026-09-17.

SQLite documents its cross-platform application-file use, long-lived database file format, rollback/WAL recovery, and atomic transactional writes.

Sources:
- https://sqlite.org/appfileformat.html
- https://sqlite.org/fileformat.html

**Implication:** SQLite is a credible editor working store/index, while SQL table/row layout remains below SplashMX public semantics.

### E-030 — RFC 8949 CBOR defines a generic extensible model and deterministic encoding requirements

**Status:** FACT / encoding comparison input, checked 2026-09-17.

RFC 8949 separates its generic data model from serialization details, includes validity/evolution/streaming considerations, and defines deterministic encoding requirements.

Source: https://www.rfc-editor.org/rfc/rfc8949.html

**Implication:** a constrained deterministic CBOR profile is a credible future chunk/package encoding candidate without being selected by SMX-005.



### E-031 — Godot web builds can omit JavaScriptBridge/eval support

**Status:** FACT, time-sensitive; checked 2026-09-17.

Current Godot web compilation docs state JavaScriptBridge is included by default/official templates and can be omitted using `javascript_eval=no`.

Source: https://docs.godotengine.org/en/latest/engine_details/development/compiling/compiling_for_web.html

**Implication:** SMX-009/016 should evaluate a hardened custom web player rather than exposing this bridge to ordinary content.

### E-032 — Godot warns that runtime-loaded PCK/mod content may contain malicious code

**Status:** FACT, time-sensitive; checked 2026-09-17.

Current Godot PCK/ZIP docs state packs may contain scripts/scenes/shaders and explicitly describe malicious/replaced pack scenarios as security vulnerabilities.

Source: https://docs.godotengine.org/en/latest/tutorials/export/exporting_pcks.html

**Implication:** untrusted SplashMX content must not be treated as an executable Godot mod/PCK project.

### E-033 — GDExtension is native shared-library execution

**Status:** FACT, time-sensitive; checked 2026-09-17.

Godot describes GDExtension as runtime interaction with native shared libraries.

Source: https://docs.godotengine.org/en/latest/engine_details/engine_api/gdextension/what_is_gdextension.html

**Implication:** GDExtension/native libraries stay outside ordinary community-package authority.

### E-034 — Web powerful-feature permission is user-controlled and revocable

**Status:** FACT, time-sensitive; checked 2026-09-17.

The W3C Permissions specification models powerful-feature states including granted/denied/prompt, permission lifetime/revocation, and the relationship with Permissions Policy.

Sources:
- https://www.w3.org/TR/permissions/
- https://www.w3.org/TR/permissions-policy/

**Implication:** browser permission is an independent lower-layer gate, not the SplashMX capability system itself.

### E-035 — Camera/microphone, geolocation, clipboard, and notifications have distinct host permission semantics

**Status:** FACT, time-sensitive; checked 2026-09-17.

Sources:
- https://www.w3.org/TR/mediacapture-streams/
- https://www.w3.org/TR/2026/REC-geolocation-20260324/
- https://www.w3.org/TR/clipboard-apis/
- https://notifications.spec.whatwg.org/

**Implication:** SplashMX should expose stable semantic capabilities while adapters handle browser-specific permission/gesture/lifetime rules.

## Hypothesis review snapshots

### SMX-001

H-001–H-018: **unresolved**; baseline added corpus/scorecard only.

### SMX-002

- H-001: **strengthened**.
- H-002: **strengthened**.
- H-003: **strengthened, still provisional**.
- H-008: **strengthened**.

### SMX-003

- H-002: **strengthened further**.
- H-003: **strengthened**.
- H-004: **strengthened**; portable packaging still pending SMX-013.
- H-005: **unresolved / no direct status change**.

### SMX-004

- H-005: **strengthened**.
- H-006: **strengthened**.
- H-009: **strengthened narrowly at execution boundary, still unresolved end-to-end**.

### SMX-005

- H-007: **strengthened** — engine-independent canonical record semantics now cover the tested object/definition/execution/document requirements.
- H-008: **strengthened further** — rename/reparent/chunk relocation/partial loading/public interfaces/assets use stable semantic IDs without path repair.
- H-018: **strengthened at schema/document layer, unresolved end-to-end** — staged deterministic migration is executable; future engine-semantic migrations remain untested.
- Others: no status change.

Detailed evidence: `docs/research/SMX-005-CANONICAL-DOCUMENT.md` and companion fixture/harness artifacts.\n\n### SMX-006

- H-006: **strengthened indirectly** — one constrained IR can share one capability/service enforcement boundary.
- H-009: **strengthened substantially at model level, unresolved end-to-end** — principal grants, narrowed delegation, revocation, nested isolation, parser/service/network limits, and signature-without-privilege are exercised; real host escape remains SMX-016.
- H-014: **strengthened narrowly** — current Godot host powers can remain behind adapters; JavaScriptBridge can be omitted and PCK/GDExtension paths excluded from ordinary content.
- H-015: **strengthened narrowly from security architecture** — generic players centralize validation/capability mediation/hardening; performance/publishing proof remains later work.


### SMX-007

- H-008: **strengthened further** — identity survives dormancy, unload, fresh-runtime snapshot restore, and tombstone resolution without hierarchy/engine pointers.
- H-010: **strengthened substantially at model level** — unloaded Things retain meaningful IDs/references/pending state and can be reconstructed without surviving process objects; full streaming remains SMX-008/015.
- H-018: **strengthened further at runtime-snapshot layer, unresolved end-to-end** — authored/behaviour/private-state compatibility is migration/rejection-driven rather than engine-object deserialization.

## Open architectural questions

### O-001 — Minimal universal port vocabulary

**Status:** RESOLVED PROVISIONALLY by SMX-004.

Command/event/directional-value; no first-class synchronous cross-Thing query. Revisit only with contrary network/destructive evidence.

### O-002 — Where behaviour state lives

**Status:** RESOLVED at execution and lifecycle semantic level.

Private runtime state belongs to stable attachment identity. SMX-007 permits persistable private-state projection into save/snapshot records together with explicit behaviour/private-schema compatibility metadata; it remains separate from authored document state and transient engine/context handles.

### O-003 — Definition/instance model

**Status:** RESOLVED PROVISIONALLY by SMX-003 and represented canonically by SMX-005.

Stable local-definition graph + concrete instance graph + sparse explicit overlay across immutable base revisions.

### O-004 — Canonical encoding

**Status:** RESOLVED at semantic-contract level; physical encoding remains intentionally open.

Current semantic contract is D-025–D-032. JSON/CBOR/Protobuf/SQLite/hybrid implementation selection belongs to SMX-009/014/019/020 using runtime/package/performance evidence.

### O-005 — Runtime IR shape

**Status:** RESOLVED PROVISIONALLY by SMX-004 at semantic level.

Validated bounded-turn handler IR; production encoding/compiler/Godot mapping/performance remain later work.

### O-006 — Multiplayer replication boundary

State/event/input/snapshot/hybrid replication must align with Thing authority and browser/server topology.

Owner: SMX-010/017.

### O-007 — Collaboration substrate

SMX-005 supplies stable semantic transaction loci/base revisions/preconditions, not a convergence algorithm. Desired concurrent-edit/CRDT/OT/rebase/conflict semantics remain open.

Owner: SMX-011/018.

### O-008 — Durable identity namespace and tombstones

**Status:** NARROWED FURTHER by SMX-007.

Required semantic identity domains and non-path/non-content-hash invariants are explicit. Runtime destruction now produces an explicit tombstone, ordinary respawn does not reuse the ID, and historical rewind is distinguished from respawn. Concrete ID encoding, cross-package namespace syntax, and tombstone retention/compaction policy remain open.

Owner: SMX-013/014/020 with lifecycle/streaming evidence from SMX-008/015.

### O-009 — Canonical reconciliation/conflict transaction model

**Status:** RESOLVED for sequential semantic transactions; concurrent conflicts remain open.

Transactions are ID/locus-addressed, preconditioned, planned/validated, and atomic. SMX-011 defines concurrent merge/rebase/convergence and persisted conflict UX.

### O-010 — Executor-state serialization and restore semantics

**Status:** RESOLVED PROVISIONALLY by SMX-007 at semantic level.

Snapshots are quiescent projections of selected runtime state: private/public state, deterministic PRNG position, durable timers/continuations/queued work, selected physics/timeline state, provenance and tombstones. External waits carry only non-authoritative descriptors and are never blindly reissued. Production encoding, crash consistency and Godot mapping remain downstream.

### O-011 — Hard-budget quota values and quarantine/throttling policy

SMX-004 requires enforceable hard limits but does not choose product/runtime quota values or broader package/tick overuse response.

Owner: SMX-006/016 with performance evidence from SMX-009/019 where relevant.

### O-012 — Production byte/package/store encoding

JSON-shaped fixtures are research-only. Deterministic CBOR, protobuf-like records, SQLite/editor store, package container, indexes, and compression choices need browser/native/headless performance and publishing evidence.

Owner: SMX-009/014/019/020.

### O-013 — Cross-document/package dependency namespace

SMX-005 requires typed qualification for references outside the current document and distinguishes unavailable dependencies, but final package IDs, dependency resolution, version constraints, vendoring/remix rules, and signatures remain open.

Owner: SMX-013/014/016.



### O-014 — Capability grant persistence and permission UX

**Status:** NARROWED by SMX-007.

Live capability grants/host handles are explicitly excluded from authored/save authority. On restore, authored capability requests are re-evaluated against the current host/user policy and browser/OS permission state. The final persistent user-policy store, prompt cadence, editor/project grant inheritance, and UX remain open.

Owner: SMX-012/014/016.

### O-015 — Hardened custom Godot runtime requirement

SMX-006 identifies concrete value in a custom web template with `javascript_eval=no`, but does not decide whether custom builds are mandatory for all targets or how their maintenance/performance cost compares with stock templates plus mediation.

Owner: SMX-009/016/019.



### O-016 — Production snapshot/store crash-consistency and performance

SMX-007 defines semantic snapshot cuts and staged atomic restore but not the final on-disk journal/transaction implementation, incremental snapshot algorithm, compression, crash recovery, snapshot compaction, or performance envelope.

Owner: SMX-008/009/014/019/020.

## Maintenance rule

When an issue resolves or materially changes an entry here, update this file in the same PR or explicitly supersede it with an ADR referenced here. Do not allow stale early assumptions to remain indistinguishable from current decisions.
