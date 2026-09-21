# SMX-041 — production untrusted-content security gate

**Status:** Phase-7 production security gate  
**Issue:** SMX-041 / #66  
**Authority:** Architecture v1.0 GATE-03; SMX-016 hostile corpus; SMX-027 capability boundary; SMX-035 package system; SMX-036 generic publishing; SMX-038 target runtime; SMX-040 physical security boundary

## Gate result and scope

SMX-041 ports the complete historical **AT-001..AT-028 / ADV-001..ADV-028** security corpus to the production boundaries that exist today. The result is a pass for every applicable current production attack class, without converting residual target isolation limits into unsupported security claims.

The two historical runtime-network ingress rows, **AT-023 / AT-024**, are explicitly *not* marked passed here. There is no production runtime-network ingress implementation before SMX-046, so there is no real adapter surface on which sender/epoch/replay/rate semantics can yet be certified. They are recorded as `deferred-no-runtime-network-surface` and are mandatory input to SMX-046/047. This is a surface-absence classification, not a weakened regression or a claim that future networking is already secure.

The production gate executes real canonical CBOR, SPB1, Behaviour IR, capability/host-service, package/update, publication/generic-player, Godot adapter and decoder-isolation code. It retains the real SMX-036 tampered-closure/protected-media campaign and the SMX-040 hardened browser-worker/Linux-isolation tests. Model-only SMX-016 evidence remains historical input, not certification.

## Destructive campaign and activation ordering

`spec/production/smx041-security-gate-fixtures.json` is the durable mapping from every SMX-016 attack row to production evidence. `tests/production/test_smx041.py` adds cross-boundary destructive checks that were not already frozen elsewhere:

- bounded mutation campaigns for deterministic canonical CBOR and pathless SPB1, requiring typed failure rather than raw parser escape;
- a Behaviour-IR hostile-opcode and recursively embedded host-authority campaign, proving JavaScript/GDScript/native/filesystem/raw-network/process operations do not become ordinary content instructions;
- recursively embedded capability/engine/session/process authority mutations in media requests, proving denial occurs before decoder-worker invocation;
- a real `TrustedHostServiceBoundary` expiry-after-admission race, proving authorization is checked again immediately before the physical decoder/source-provider crossing;
- exact production attack-matrix and target-decision assertions so future CI cannot silently drop a historical class.

The gate workflow additionally reruns the existing production canonical, execution, capability, package, generic-publishing, Godot and physical-security adversarial suites. Tampered creation manifests/blobs, floating dependency substitution, exact-offline closure failures and protected-media conflicts therefore continue to fail during `GenericPlayer.prepare()` before activation.

No malformed/fuzz campaign found an unresolved activation-before-validation route in the exercised current surfaces. A parser mutation that remains structurally valid is still only parsed data; activation stays behind the existing semantic, exact-lock, capability and target-isolation preparation stages.

## Target release eligibility and residual risk

The gate distinguishes semantic/runtime support from permission to process arbitrary public-untrusted decoder input:

| Target profile | Public-untrusted decoder decision | Reason / residual risk |
| --- | --- | --- |
| Web | **release-blocked** | The physical profile still requires a pinned production decoder module and attestation for the custom Godot build with the JavaScript bridge disabled. Worker/WASM isolation is not represented as an OS-process sandbox and there is no weaker fallback. |
| Linux native | **conditionally eligible** | Eligible only on hosts where the production probe confirms `fork`, `no_new_privs`, seccomp, Landlock and all selected rlimits. Missing any primitive makes the profile release-blocked. Kernel/libseccomp/decoder defects remain residual platform risk. |
| Linux headless | **conditionally eligible** | Same production probe and fail-closed rule as Linux native. |
| Windows native | **release-blocked** | No equivalent production decoder isolator is implemented/tested. |
| macOS native | **release-blocked** | No equivalent production decoder isolator is implemented/tested. |
| Mobile | **release-blocked** | No equivalent production decoder isolator is implemented/tested. |

These decisions deliberately do not claim sandbox or decoder exploit impossibility. Browser-engine, kernel, third-party codec, cryptographic operational/key-ceremony, side-channel and denial-of-service assurance remains target/operations work. Signature/provenance trust still cannot mint runtime capability.

## Downstream gate routing

SMX-041 remains a hard production prerequisite for work that introduces new remote/untrusted surfaces. The existing programme dependency graph already binds **SMX-043** production collaboration, **SMX-045** network-deployment selection, **SMX-046** production networking and **SMX-050** distribution/hosting to #66. The machine-readable SMX-041 fixture repeats those edges so repository validation detects accidental gate drift.

Future collaboration/network/distribution implementations must port the relevant security rows to their newly real boundaries rather than citing this gate as blanket certification. In particular, SMX-046/047 must execute AT-023/024 against production authenticated transport/session/authority-epoch ingress and preserve transient transport identity outside canonical/WorldSave state.

The complete protected Asset invariant remains unchanged: a stable `AssetId` selects one indivisible immutable revision containing content/revision digest, source digest and identity, exact source metadata, audio/media semantics, provenance, licence/attribution and derivation lineage. Parser, resolver, migration, IR, capability, decoder, runtime, network, cache and publication paths may authenticate or derive from that revision but may not field-mix competing revisions or let target-private derivatives redefine canonical meaning.

**Architecture disposition:** No Architecture-v1 amendment is required. SMX-041 certifies and narrows release eligibility beneath the frozen semantic/security boundary; it does not weaken that boundary or hide a contradiction in an adapter.
