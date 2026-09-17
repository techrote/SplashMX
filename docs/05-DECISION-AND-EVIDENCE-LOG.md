# SplashMX decision and evidence log

This is a compact durable register. Detailed research belongs in issue-specific documents; this file records what the project currently believes, why, and where to retrieve the evidence.

## Status vocabulary

- **FACT** — current primary-source fact, version/date sensitive where applicable.
- **HYPOTHESIS** — proposition awaiting or undergoing falsification.
- **DECISION** — accepted project choice supported by available evidence.
- **OPEN** — unresolved question/blocker.
- **REJECTED** — considered direction that should not be silently reintroduced without new evidence.

## Initial planning review — 2026-09-17

### D-001 — Research before production editor

**Status:** DECISION

The project will not begin by reproducing a Flash-style editor UI. The object/execution/document/security/lifecycle model must be investigated first, then projected upward into authoring UX.

**Reason:** beginning with familiar editor metaphors risks hard-coding Flash or Godot assumptions before the platform semantics are understood.

**Source:** `docs/00-PROJECT-CONSTITUTION.md`, `docs/01-RESEARCH-ROADMAP.md`.

### D-002 — Godot is substrate, not canonical public contract

**Status:** DECISION

SplashMX will initially target Godot as runtime/rendering substrate while owning its durable author-facing object/document/package semantics.

**Reason:** long-lived creations, sandboxed user logic, collaboration, partial streaming, migrations, and topology-independent networking should not be coupled unnecessarily to Godot internal serialization or scene semantics.

**Source:** Constitution P10/P12; Hypotheses H-007/H-014/H-018.

### D-003 — Runtime multiplayer and collaborative editing are distinct consistency problems

**Status:** DECISION

They may share infrastructure but must be researched and specified separately.

**Reason:** runtime simulation asks for timely authority/replication of live state; collaborative editing asks for durable reconciliation of concurrent document changes, including offline edits.

**Source:** Constitution P7/P8; H-013; SMX-010/011 roadmap entries.

### D-004 — No arbitrary GDScript as the default community execution model

**Status:** DECISION

Community/user-authored executable intent must pass through a constrained, inspectable, budgetable execution boundary unless later evidence justifies a strictly controlled exception.

**Reason:** arbitrary engine-level code defeats the intended capability sandbox and long-term portable execution contract.

**Source:** Constitution P9; H-006/H-009.

### D-005 — Generic runtime/player is the preferred publishing hypothesis

**Status:** HYPOTHESIS/PROVISIONAL DIRECTION

Ordinary published creations should ideally be packages consumed by versioned generic web/native/server players rather than independently compiled Godot projects.

**Must be tested by:** SMX-009, SMX-014, SMX-017, SMX-019.

### D-006 — Destructive prototypes precede Architecture v1.0

**Status:** DECISION

Architecture freeze is gated on integrated object-fabric, sandbox, network, collaboration, and browser vertical-slice falsification work.

**Source:** Constitution P15; SMX-015 through SMX-020.

## Initial primary-source snapshot — 2026-09-17

These observations are planning inputs only. Relevant research issues must refresh them before making durable decisions.

### E-001 — Godot web editor export limitation

**Status:** FACT, time-sensitive.

Current Godot `latest` documentation states that the web editor cannot perform project exporting; source can be downloaded and exported with a native editor.

Primary source: https://docs.godotengine.org/en/latest/tutorials/editor/using_the_web_editor.html

Implication: a SplashMX browser editor should not assume it can invoke the ordinary native Godot export pipeline. This supports investigating generic precompiled players/packages.

### E-002 — Godot web renderer/platform constraints

**Status:** FACT, time-sensitive.

Current Godot documentation describes web export using WebAssembly/WebGL and the Compatibility renderer. Single-threaded web export is documented as the preferred/default approach for broad hosting compatibility; threaded web builds impose additional cross-origin-isolation constraints.

Primary source: https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html

Implication: web-first architectural experiments should explicitly record whether they require threading and avoid assuming native rendering/runtime features exist in browser builds.

### E-003 — Custom Godot web build can reduce JavaScript exposure

**Status:** FACT, time-sensitive.

Current Godot compiling-for-web documentation exposes build options including disabling JavaScript `eval`/bridge support.

Primary source: https://docs.godotengine.org/en/latest/engine_details/development/compiling/compiling_for_web.html

Implication: SMX-006/016 should evaluate hardened custom runtime builds instead of assuming stock export templates are the final security boundary.

### E-004 — Godot runtime/package facilities are useful but not automatically safe for untrusted executable content

**Status:** FACT/DESIGN INPUT, time-sensitive.

Godot documents runtime file loading and PCK/ZIP/mod mechanisms. Relevant Godot packaging documentation warns against treating untrusted executable pack content as safe.

Primary sources:

- https://docs.godotengine.org/en/stable/tutorials/io/runtime_file_loading_and_saving.html
- https://docs.godotengine.org/en/stable/tutorials/export/exporting_pcks.html
- https://docs.godotengine.org/en/stable/tutorials/export/exporting_projects.html

Implication: use Godot I/O facilities where useful, but do not equate a Godot PCK containing scripts with a SplashMX-safe community package.

### E-005 — Godot networking is candidate substrate, not settled SplashMX protocol

**Status:** FACT/DESIGN INPUT, time-sensitive.

Godot provides high-level multiplayer facilities and browser-appropriate networking options including WebSocket/WebRTC, plus dedicated/headless server paths. Its abstractions are closely integrated with Godot runtime concepts.

Primary sources:

- https://docs.godotengine.org/en/stable/tutorials/networking/high_level_multiplayer.html
- https://docs.godotengine.org/en/stable/classes/class_websocketmultiplayerpeer.html
- https://docs.godotengine.org/en/stable/classes/class_webrtcmultiplayerpeer.html
- https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_dedicated_servers.html

Implication: SMX-009/010/017 must compare direct adoption, lower-level use, and hybrid mapping instead of inheriting Godot networking semantics by default.

## Open architectural questions at repository creation

### O-001 — Minimal universal port vocabulary

Is the durable communication model best expressed as inputs/outputs, commands/events/queries, generic messages, reactive state links, or a smaller primitive set?

Owner: SMX-002/004.

### O-002 — Where behaviour state lives

Can behaviours retain private state while Things expose a coherent durable state model? What is the state-transfer contract on hot swap?

Owner: SMX-002/004/007.

### O-003 — Definition/instance model

Prototype inheritance, structural definitions, patches/overrides, or a hybrid may best fit local classes and collaboration.

Owner: SMX-003/005/011.

### O-004 — Canonical encoding

Human-readable, binary, database-like, or hybrid representations need comparison against diffability, partial loading, deterministic encoding, package size, validation, and migration.

Owner: SMX-005.

### O-005 — Runtime IR shape

Event rules, bytecode, dataflow, state machines, or a hybrid need empirical comparison against determinism, sandboxing, inspectability, hot replacement, authoring projection, and performance.

Owner: SMX-004.

### O-006 — Multiplayer replication boundary

State replication, event replication, simulation inputs, snapshots, or hybrid strategies must align with Thing authority and browser/server topology.

Owner: SMX-010/017.

### O-007 — Collaboration substrate

Desired user-visible conflict semantics must be specified before choosing CRDT/OT/operation-log technology.

Owner: SMX-011/018.

## Maintenance rule

When an issue resolves or materially changes an entry here, update this file in the same PR or explicitly supersede it with an ADR referenced here. Do not allow stale early assumptions to remain indistinguishable from current decisions.
