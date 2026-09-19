# SMX-016 decision / evidence handoff

Issue: SMX-016 / #16  
Date: 2026-09-19  
Status: destructive model evidence; production sandbox assurance remains explicitly open

This compact handoff exists so later agents can retrieve the SMX-016 deltas without reconstructing the full attack transcript. Detailed reasoning is in `SMX-016-SECURITY-HARNESS.md`; executable evidence is in `experiments/smx-016-security-harness/`.

## Decisions

### D-091 — Package/container normalization is host-independent and collision-rejecting

Ordinary untrusted package entries are validated before extraction. Separator normalization, Unicode NFC, case-folded collision detection, traversal/absolute/drive/device/control/trailing-dot-space rejection, and special-entry policy are security checks, not host-filesystem cleanup after extraction.

This refines the enforcement detail of SEC-008/B1/D-039 without changing semantic ID case rules.

### D-092 — Forbidden durable/network authority fields are rejected recursively

Capability grants/IDs, host/native/browser/Godot handles, peer IDs, sockets, authority tokens and raw loader/code authority are not merely forbidden at a top-level envelope. Every bounded structured canonical/network payload is recursively checked before migration/delivery.

This strengthens the executable interpretation of SEC-012, D-040 and D-065.

### D-093 — Delegation bounds and cycle checks are pre-allocation security invariants

Delegation depth and total grant count are enforced before creation of a child grant. Grant ancestry traversal is cycle-safe; missing/cyclic/corrupt ancestry is non-live and cannot authorize. Scope/lifetime monotonic narrowing and ancestor revocation/expiry remain unchanged.

This makes the existing SEC-004/SEC-005/SEC-008 and D-034/D-039 requirements operationally testable.

### D-094 — Capability authorization is rechecked at host-use time

A staged asynchronous service request may pass an admission check but must be re-authorized immediately before invoking the target adapter. Revocation/expiry/policy change between those points fails before the host call.

This clarifies SEC-005/B4 and preserves the principle that live grants are runtime policy rather than serialized authority.

### D-095 — Exact lock/dependency/canonical validation precedes migration and activation

`PackageId + revision + digest + byte size`, bounded acyclic dependency closure, and bounded canonical structural/security validation all succeed before a migration is invoked. Migration remains capability-free and separately bounded.

This carries D-030/D-049/D-050 and PKG/PUB contracts into hostile execution ordering.

### D-096 — Raw host denial is target-independent; physical isolation strength is not

Ordinary content receives the same semantic service vocabulary on web/native/headless and cannot name JavaScriptBridge/eval, GDScript/PCK loaders, GDExtension, process/shell, raw filesystem or raw sockets. A target may nevertheless physically contain these facilities for trusted host code.

Hardened web omitting JavaScriptBridge/eval is defence in depth. Native/headless require separate process/OS hardening. Target profiles must record these differences rather than claim equivalent isolation.

### D-097 — Resource limits are independent semantic counters checked before expensive work

Archive, structured-input, dependency, grant/delegation, IR instruction/allocation/emission/timer/queue/service, migration, network and media-decode classes have explicit independent ceilings. Exact numeric values remain product/runtime policy and require real implementation calibration.

### D-098 — Protected source/audio/provenance remains indivisible under hostile paths

Security rejection, dependency resolution, migration, network transport, target projection and decoder preflight cannot synthesize a new asset revision by mixing fields. Stable `AssetId` selects one complete immutable digest + source identity/metadata + audio/media semantics + provenance + licence + derivation bundle.

No SMX-016 repair weakens D-031/D-058/D-067/D-071/D-075 or SMX-013/014/015 protected-media semantics.

## Evidence

### E-070 — 38 deterministic hostile boundary tests pass

`experiments/smx-016-security-harness/test_harness.py` exercises package normalization/bombs, canonical structure, exact-lock/dependency substitution, capability escalation/delegation/revocation/confused deputy, IR/allocation/event/timer/service amplification, migration ordering, hostile network ingress, target host surfaces, decoder preflight and protected-media atomicity.

The harness checks host/decoder/migration invocation counters where “fail before boundary” matters; raising after the privileged operation would not satisfy the test.

### E-071 — Four earlier positive-model enforcement ambiguities were made explicit

R-016-01 through R-016-04 cover host-independent path collision handling, recursive authority-field rejection, delegation depth/cycle enforcement, and use-time revocation. The upstream semantic direction was already fail-closed; the repair tightens enforcement rather than introducing exceptions.

### E-072 — Godot security-sensitive baseline remains 4.7.2 stable on 2026-09-19

The official release archive lists Godot 4.7.2-stable (2026-08-18) as current stable Godot 4 and 4.8-dev6 (2026-09-15) as newest development snapshot. No stable-version drift invalidates SMX-009/014’s 4.7.2 baseline.

Source: https://godotengine.org/download/archive/

### E-073 — JavaScriptBridge omission and PCK warning remain current

Godot’s current web compilation documentation still exposes `javascript_eval=no` to omit JavaScriptBridge/eval from a custom web build; official/default templates include the bridge. Current PCK/mod docs still warn about malicious/replaced executable packs.

Sources:
- https://docs.godotengine.org/en/latest/engine_details/development/compiling/compiling_for_web.html
- https://docs.godotengine.org/en/latest/tutorials/export/exporting_pcks.html

## Open residual risks

### O-021 — Real runtime sandbox and decoder assurance

SMX-016 does **not** prove:

- real Godot/browser/native process or origin escape resistance;
- production ZIP/archive library edge cases;
- third-party image/audio/font/mesh/video decoder safety;
- production cryptographic signature/key/revocation implementation;
- cross-browser permission/lifecycle behavior;
- actual engine/GPU/audio memory accounting;
- production-safe quota values.

SMX-019 owns the real browser/generic-player vertical slice and should exercise the host boundary. Final Architecture v1.0 reconciliation remains SMX-020. Native/server process hardening remains an implementation/deployment requirement even if the semantic contract is stable.

## Hypothesis handoff

- **H-006 strengthened at hostile model level.**
- **H-009 strengthened substantially but remains unresolved end-to-end.**
- **H-011 strengthened narrowly at hostile exact-acquisition/dependency boundary.**
- **H-014 strengthened at semantic host-boundary level; physical target isolation remains target-specific.**
- **H-015 strengthened from generic-player security centralization.**

No other hypothesis status changes are justified by SMX-016.
