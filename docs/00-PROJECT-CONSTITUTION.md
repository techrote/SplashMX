# SplashMX project constitution

## Purpose

SplashMX aims to be a modern creative-computing environment for building, animating, programming, sharing, remixing, collaborating on, and playing interactive media with extremely low technical friction.

Original Flash is a **minimum capability/approachability floor**, not the product definition. The intended philosophical target is the platform that could plausibly have been received as a major generational successor to Flash, while taking advantage of modern rendering, networking, collaboration, sandboxing, component systems, persistence, accessibility, responsive layouts, and distribution.

SplashMX is not a Flash clone and should not preserve historical Flash limitations merely for familiarity.

## Product invariants

### P1 — Blank canvas to delight must be short

A non-programmer must be able to create something animated and interactive without learning a package manager, compiler, scene graph, build system, deployment pipeline, or programming language.

### P2 — Complexity is optional, not absent

The simple model must scale into serious work. Advanced authors should be able to reveal progressively deeper control without abandoning the objects and concepts learned as beginners.

### P3 — One conceptual system

Beginner behaviours, rules, reusable components, text logic, networking, persistence, and advanced control should be projections of one coherent underlying object system rather than separate incompatible authoring modes.

### P4 — Intent lives with the thing

An object, group, or local class should embody or explicitly declare its own intent, state, behaviours, ports, capabilities, persistence semantics, and network semantics.

External managers may coordinate context; they should not become the hidden place where an object's meaning lives.

### P5 — Composition/locality is not behavioural ownership

Hierarchy may express containment, transform locality, grouping, or structure. Reparenting an object must not silently redefine who owns its behaviour, persistence, authority, or identity.

### P6 — Control is a relationship

Rendering, containment, simulation authority, input control, persistence ownership, replication, observation, and editor selection are separate relationships. A thing should survive changes in those relationships without being reconstructed merely because its controller changed.

### P7 — Multiplayer is architectural, not decorative

Objects should be designed so offline, peer-room, and authoritative-server execution can be supported without rewriting creations around a separate multiplayer object taxonomy.

Gameplay networking need not ship in the first usable release, but the foundational model must not preclude it.

### P8 — Collaborative authoring is first-class

Multiple people editing a creation is a distinct problem from multiplayer simulation and should be architected deliberately rather than confused with runtime replication.

### P9 — User content is untrusted

Community creations and components must not receive ambient authority over Godot, browser JavaScript, native code, the filesystem, arbitrary network destinations, or other host capabilities.

Power should be granted through explicit, inspectable capabilities.

### P10 — Godot is a substrate

Godot may provide rendering, audio, physics, input, platform abstraction, and useful networking transports. SplashMX should own the durable creation model and compatibility boundary.

### P11 — Publishing is not compilation to the author

The normal path should be create -> play -> publish/share. Build/export/runtime machinery should be hidden behind platform services or generic players wherever practical.

### P12 — Creations should outlive engine revisions

A creation's canonical semantics should not depend on undocumented Godot internals or ephemeral engine serialization details. Versioned schemas, migrations, validation, and explicit compatibility policy are required.

### P13 — Portable things

Reusable objects/components should be capable of moving between groups, scenes, projects, peers, packages, and streaming boundaries while retaining identity and declared semantics.

### P14 — Offline is a meaningful mode

Core authoring and playback should remain useful without continuous network access. Cloud collaboration, hosting, discovery, and services should extend the system rather than define the only storage model.

### P15 — Research must be falsifiable

Before architecture freeze, preferred designs must face destructive prototypes and adversarial examples. Familiarity, elegance, or resemblance to Godot/Flash is not evidence.

## Desired author-facing primitives

The exact terminology remains researchable, but the preferred conceptual vocabulary is deliberately small:

- **Things** — objects/groups/local reusable definitions with identity and state.
- **Behaviours** — modular intent/control that can be composed and, where safe, replaced dynamically.
- **Connections** — declared ways things communicate or affect one another.

Timeline, stage, rules, components, scenes, multiplayer, and scripting should be authoring views over those semantics rather than independent architectural islands.

## Historical pre-architecture non-goals — completed phase

This section records constraints that governed the completed pre-Architecture-v1 research campaign. It remains historical evidence; current implementation work is governed by Architecture v1.0 and the production implementation roadmap.

During that research phase, the project was instructed not to prematurely:

- clone the Flash UI pixel-for-pixel;
- make Godot scenes/resources canonical SplashMX documents;
- expose arbitrary GDScript as the community scripting model;
- select CRDT structures before defining desired conflict semantics;
- treat Godot high-level multiplayer protocol as SplashMX's public network contract;
- optimise for massive worlds before object identity/lifecycle is coherent;
- implement a production editor before the object fabric survives destructive prototypes;
- choose a final textual language before execution semantics/IR are understood.

## Historical research-programme success criterion — met

The pre-architecture campaign defined success as publishing an evidence-backed Architecture v1.0 that:

1. explains the canonical object/document/runtime model;
2. survives the defined destructive prototypes;
3. has a credible sandbox and compatibility model;
4. supports a coherent path to streaming, runtime multiplayer, and collaborative editing;
5. maps efficiently onto Godot without exposing Godot as the author-facing contract; and
6. can still be projected into an editor simpler to approach than a conventional game engine.


That criterion was met by the Architecture v1.0 freeze on 2026-09-19. These historical criteria remain provenance for the freeze rather than the active production roadmap.
