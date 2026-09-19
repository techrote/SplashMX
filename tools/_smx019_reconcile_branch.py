#!/usr/bin/env python3
"""One-shot branch helper. Appends SMX-019 reconciliation to large durable registers.
Removed before merge; it exists only because API-only editing cannot apply textual patches.
"""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

sections={
'03-RAG-INDEX.md': r'''

## SMX-019 browser vertical-slice retrieval rules

For any Architecture v1.0 or implementation work involving browser authoring, progressive disclosure, generic-player publication, offline playback, author-facing diagnostics, runtime-multiplayer controls, collaboration projection, or browser performance, retrieve **all** of:

- `docs/research/SMX-019-BROWSER-VERTICAL-SLICE.md` — executed browser synthesis and UXG-001–UXG-012 outcomes;
- `docs/research/SMX-019-BROWSER-VERTICAL-SLICE-FIXTURES.json` — machine-addressable UXG and BV gates plus R-019-01;
- `docs/research/SMX-019-DECISION-EVIDENCE.md` — D-111–D-116, E-083–E-087 and O-028;
- `experiments/smx-019-browser-vertical-slice/` — trusted disposable editor/player/server/browser harness and 34 adversarial/boundary tests;
- upstream `SMX-012-AUTHORING-MODEL.md` and `SMX-014-PUBLISHING-RUNTIME.md` — source contracts that SMX-019 executes rather than replacing;
- `SMX-017-NETWORK-HARNESS.md` and `SMX-018-COLLABORATION-HARNESS.md` when multiplayer/collaboration claims are involved.

Retrieval constraints:

1. **UXG-001 through UXG-012 are hard gates.** Friendly copy does not excuse an underlying requirement to understand engine, transport, schema, package-manager or build concepts.
2. **BV-001 through BV-020 are evidence fixtures, not a second architecture.** Their browser implementation is disposable; accepted Thing/Behaviour/Connection/Definition/Timeline/publication semantics remain authoritative.
3. **R-019-01 is a semantic-name boundary repair.** Canonical SplashMX ConnectionId is durable; transient transport connection identity is runtime context. Do not ban canonical Connections while attempting to exclude transport identity.
4. **Generic-player proof is data publication, not per-creation compilation.** Hosted and offline copies must resolve the same immutable `CreationRevisionId`.
5. **Together and People remain separate.** Runtime multiplayer projects control/authority/replication/relevance; collaboration presence/conflicts remain edit-plane semantics.
6. **Protected source/audio/provenance is indivisible.** Stable `AssetId` selects one complete immutable digest + source identity/metadata + audio/media semantics + provenance + licence + derivation revision across save, Publish, cache, offline and peer runtime paths.
7. **Do not overread automated usability evidence.** The browser campaign proves executable workflow/projectability and measurable interaction seams, not novice comprehension, accessibility certification, final terminology, production persistence or broad performance budgets; those are O-028/product obligations.
''',
'02-ARCHITECTURE-HYPOTHESES.md': r'''

## SMX-019 review record — 2026-09-19

Evidence: `docs/research/SMX-019-BROWSER-VERTICAL-SLICE.md`, `docs/research/SMX-019-BROWSER-VERTICAL-SLICE-FIXTURES.json`, `docs/research/SMX-019-DECISION-EVIDENCE.md`, and `experiments/smx-019-browser-vertical-slice/`.

- **H-014 strengthened narrowly at real-browser projection boundary; final generic-player substrate binding remains implementation work.** Canonical author content and published revisions remain free of host/engine/transport identity while trusted browser storage, service-worker, relay and player mechanisms stay replaceable context. SMX-017 independently supplies the exported Godot 4.7.2 browser/headless evidence; SMX-019 does not make its disposable JavaScript host language canonical.
- **H-015 strengthened substantially at real-browser vertical-slice level.** The ordinary author path publishes an immutable data revision, a separately deployed generic web player validates/activates that exact revision, and the exact same revision reloads from an offline cache without per-creation build/export. Real distribution scale/final player implementation remain O-028/product work.
- **H-016 strengthened substantially at executable browser-interaction level, but not human-study proven.** UXG-001–UXG-012 execute end to end: blank-canvas Things; optional Timeline; common Rule/Behaviour IR; stable-port Connections; group→Definition identity preservation; Play/Stop plane separation; transient-free save/reload; generic-player Publish/load/offline; Together preset/Advanced equivalence; People separation; author-language failures; and atomic protected media. Automated evidence does not establish novice comprehension, accessibility or final terminology.
- **H-013/H-017 receive no semantic rewrite.** One peer-hosted runtime path reaches the accepted network declaration while People presence/conflicts remain a separate edit-plane projection; offline authoring remains possible without turning browser storage/cloud state into canonical authority.

**R-019-01** records one implementation-boundary defect found by the campaign: a first host-identity filter conflated canonical `ConnectionId` with transient transport connection identity. The repaired boundary preserves semantic Connections and forbids explicit transport identity instead.

No accepted source/audio/provenance, object-fabric, lifecycle, migration, capability, package, multiplayer or collaboration semantic is weakened. **O-028** retains production browser editor/player implementation, final store/player binding, accessibility/localization, broad performance and human-usability evidence for post-freeze product work.
''',
'05-DECISION-AND-EVIDENCE-LOG.md': r'''

## SMX-019 decision/evidence register — 2026-09-19

This section is authoritative for the browser vertical-slice gate. Detailed evidence is in `docs/research/SMX-019-BROWSER-VERTICAL-SLICE.md` and its fixture/decision files.

### D-111 — Progressive disclosure remains one semantic system in the real browser slice

**Status:** DECISION strengthened by executable browser evidence.

The browser editor directly manipulates accepted Thing/Behaviour/Connection/Definition/Timeline records. Stage, Rules, Together, People, Publish and Inspect are projections; none introduces a second beginner document or runtime taxonomy.

### D-112 — Ordinary browser Publish is immutable data projection, not per-creation build

**Status:** DECISION strengthened by real browser generic-player/offline evidence.

Publish validates the editable semantic revision, computes an immutable `CreationRevisionId`, and hands data to a separately deployed generic web player. The author path contains no build/export operation, and hosted/offline playback uses the same exact revision.

### D-113 — Editable save, preview runtime, presence and published runtime are separate planes

**Status:** DECISION strengthened by browser round-trip evidence.

Play mutates a transient runtime copy; Stop discards it. Selection, People presence, current peer/transport identity and play session are not canonical creation state. Durable collaboration conflict alternatives may remain editable-project history but are excluded from the published runtime package.

### D-114 — Browser multiplayer controls project the existing topology-independent declaration

**Status:** DECISION strengthened narrowly by one peer-hosted browser integration path.

Shared and detailed Together views edit the same `spawn_scope/control/authority/replication/relevance` fields. Two generic-player pages can execute one shared-Thing input/state path over the same published revision while connection identity and current authority remain runtime context. SMX-017 remains the destructive reconnect/host-loss/topology evidence.

### D-115 — Browser persistence/offline mechanisms remain non-semantic and fail typed

**Status:** DECISION at browser projection boundary.

LocalStorage, CacheStorage and service workers are implementation choices in the harness. Storage denial and incomplete offline closure produce typed author-language outcomes. Cache/storage keys never become Thing/Creation/Asset identity and offline playback does not float dependency/content versions.

### D-116 — Protected source/audio/provenance remains an indivisible revision across browser authoring and playback

**Status:** DECISION; carry-forward strengthened by end-to-end browser equality checks.

Stable `AssetId` selects one complete immutable digest + source identity/metadata + audio/media semantics + provenance + licence + derivation revision. Save/reload, Publish, generic-player activation, service-worker cache and peer runtime paths cannot synthesize field-mixed revisions or replace canonical source meaning with derived/cache/runtime state.

### E-083 — Thirty-four deterministic SMX-019 boundary tests execute the author/publish model

**Status:** REPRODUCIBLE RESEARCH EVIDENCE, non-production; 2026-09-19.

`experiments/smx-019-browser-vertical-slice/test_model.mjs` exercises UXG-001–UXG-012 plus invalid ports/reuse shortcuts, dangling references, transient-state leakage, host/transport identity smuggling, required/optional capability denial, schema/feature incompatibility, deterministic publication and protected-media atomicity.

### E-084 — Real Playwright campaign executes author → generic player → exact offline reload

**Status:** REPRODUCIBLE REAL-BROWSER EVIDENCE; pinned CI environment.

`browser_harness.mjs` drives blank canvas → Things → group/reuse → Behaviour/Rule/Connection/Timeline → Play/Stop → save/hard reload → Publish → generic player → offline reload. It records concrete startup/publish/package/frame/storage observations and fails on substrate vocabulary leakage, revision substitution, preview leakage or protected-media mutation.

### E-085 — Same published revision reaches a bounded peer-hosted browser runtime path

**Status:** REPRODUCIBLE INTEGRATION EVIDENCE, deliberately smaller than SMX-017.

Two player pages load the identical `CreationRevisionId`; the relay assigns distinct transient connection identities; a non-authority principal sends input intent to the current peer authority; both pages converge on replicated shared-Thing state. Canonical content contains only the accepted topology-independent declaration.

### E-086 — Browser storage/capability/compatibility failures are executable typed paths

**Status:** REPRODUCIBLE BOUNDARY EVIDENCE.

The campaign forces editable browser-storage denial and required capability denial with author-language diagnostics. Runtime schema/feature incompatibility fails before activation; exact offline closure is reused rather than substituted.

### E-087 — Protected media equality is checked through publication and browser player input

**Status:** REPRODUCIBLE BOUNDARY EVIDENCE.

The research asset's stable AssetId and complete immutable digest/source/audio-media/provenance/licence/derivation record are compared before/after publication. Incomplete replacement is rejected atomically and leaves the prior revision unchanged.

### R-019-01 — Semantic ConnectionId is distinct from transient transport connection identity

The first recursive host-identity filter rejected canonical `connection_id` while attempting to ban transport context. The repaired boundary forbids explicit transport identity (`transport_id` / `transport_connection_id`) while retaining canonical SplashMX Connection identity, with regression coverage.

### O-028 — Production browser editor/player implementation and human-usability envelope

**Status:** OPEN after SMX-019; architectural destructive gate passed, implementation/product evidence remains.

SMX-019 does not choose the production editor framework, durable working store, cache/quota/eviction recovery, final generic-player Godot binding, accessibility/localization system, large-project navigation, broad performance budgets or novice terminology. SMX-020 should freeze the semantic architecture without misclassifying these implementation/product obligations as unresolved object-model questions.

Owner: SMX-020 for final Architecture v1.0 classification; subsequent implementation programme for product evidence.
'''
}

for name,section in sections.items():
    path=ROOT/'docs'/name
    text=path.read_text(encoding='utf-8')
    marker=section.strip().splitlines()[0]
    if marker not in text:
        path.write_text(text.rstrip()+section+'\n',encoding='utf-8')

ci=ROOT/'.github/workflows/ci.yml'
text=ci.read_text(encoding='utf-8')
step="""      - name: Validate SMX-019 browser vertical-slice artifacts\n        run: python tools/validate_smx019.py\n"""
if 'python tools/validate_smx019.py' not in text:
    ci.write_text(text.rstrip()+"\n"+step,encoding='utf-8')
