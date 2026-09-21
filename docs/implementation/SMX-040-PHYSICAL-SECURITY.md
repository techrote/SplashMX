# SMX-040 — production physical security boundary

**Status:** production implementation for Phase 7; SMX-041 remains the end-to-end security gate  
**Issue:** SMX-040 / #65  
**Authority:** Architecture v1.0, SMX-016 corrections, SMX-027 capability boundary, SMX-035 package system, SMX-038 target runtime, SMX-039 mechanism selection

## Production contract

SMX-040 turns the selected Phase-7 mechanisms into production code without changing Architecture-v1 semantics. The physical ingress order is fail-closed:

```text
configured repository trust
  -> threshold/freshness/coherence verification
  -> exact PackageRevisionId + length + SHA-256 target binding
  -> bounded pathless SPB1 parse
  -> canonical/package semantic validation
  -> capability preparation
  -> media descriptor preflight
  -> selected target isolation
  -> bounded decoder result validation
  -> target-private derivative cache publication
```

No later stage is allowed to run because an earlier stage merely began. Failed trust cannot reach SPB1 activation; failed decoder preflight cannot invoke a worker; invalid worker output cannot reach the derivative cache. Signatures, provenance and licence metadata never mint capability.

## R-016 corrections on production code

**R-016-01 — path normalization/collision.** Ordinary packages remain SPB1 and therefore have no extraction pathname at all. The production boundary rejects foreign archive framing and entry kinds representing paths, links, devices, executable/native/script/install semantics. A future path-bearing importer still requires whole-namespace normalization/collision proof before filesystem use; it is not silently routed through this parser.

**R-016-02 — recursive authority rejection.** Repository metadata, decoder requests and decoder results independently reject recursive capability/grant, Godot/browser/native, transport/session/socket/process and loader-authority fields under bounded depth/node/string/IPC limits. Existing canonical/IR/service checks remain retained rather than being replaced by this layer.

**R-016-03 — bounded delegation before allocation.** Physical workers receive immutable data descriptors, not delegated grants. Delegation remains owned by `CapabilityBroker`, which enforces depth/count limits before new grant allocation. SMX-040 does not introduce a second grant format.

**R-016-04 — final authorization at host use.** Behaviour-originated media decode uses `DecoderBroker.host_adapter()` with the existing `TrustedHostServiceBoundary`. Admission resolves only a bounded semantic target. The exact source provider and isolated decoder are touched only by adapter invocation, after `TrustedHostServiceBoundary.execute()` performs its final revocation/expiry/scope recheck. Revoking after admission therefore keeps worker invocation count at zero.

## Repository trust

`RepositoryTrust` implements the selected TUF-compatible four-role profile with root, targets, snapshot and timestamp roles. Ed25519 verification is verification-only and delegates to a fixed-argv OpenSSL adapter; SplashMX runtime has no private-key operation.

The client retains trusted root and the highest accepted metadata versions. Root rotation is sequential and requires both old-root and candidate-root thresholds. Root candidate version, expiry and complete signed body must agree. Targets, snapshot and timestamp all require live threshold signatures. Snapshot binds the exact encoded targets metadata by version and SHA-256; timestamp similarly binds the exact snapshot metadata. Rollback, expiry/freeze and same-version mix-and-match therefore fail closed. Only the exact refreshed targets metadata may authorize a package, and its target record binds exact `PackageRevisionId`, byte length and SHA-256 before SPB1 parsing.

Repository/publisher authenticity remains orthogonal to runtime authority. `trust_signature_grants_capability()` is deliberately always false.

## Decoder isolation and target release gates

Decoder admission independently bounds source bytes, predicted decoded bytes, image pixels, audio frames, IPC bytes and metadata structure. Result dimensions are checked again before immutable derivative publication. The derivative cache key binds exact `AssetId + revision_digest + target profile + derivative kind/version`; failed decode/result validation cannot replace a coherent cached derivative.

The web boundary is a dedicated module worker with a fixed-maximum WebAssembly memory and a closed import surface. `src/splashmx/security/web/hardened-web-profile.json` requires `connect-src 'none'`, same-origin worker/script policy and a custom Godot build attesting the browser bridge is disabled. The worker contains no network/eval/import-script path. The repository intentionally does not claim that a Worker is an OS-process boundary. The shipped profile remains **release-blocked for arbitrary public-untrusted decoding until a concrete pinned decoder module and the custom Godot build attestation are supplied**; tests may inject a trusted transport only to exercise the production broker seam.

Linux native/headless uses a forked worker process and probes every selected primitive. Before decoder code runs, the child installs finite address-space/CPU/file-descriptor/output/process limits, `PR_SET_NO_NEW_PRIVS`, a seccomp default-deny syscall allowlist and Landlock deny-all filesystem confinement. If any primitive is unavailable, `public_untrusted_ready` is false and no in-process fallback exists. Other native platforms remain release-blocked for arbitrary public-untrusted decode until equivalent target-specific isolation is implemented and tested.

## Calibrated finite limits

SMX-040 retains the SMX-039 bounded package/media baseline and makes OS-worker/cache dimensions explicit. These are environment-specific production ceilings, not universal performance SLOs:

| Dimension | Current ceiling |
| --- | ---: |
| SPB1 total / index | 512 MiB / 8 MiB |
| SPB1 entries / single entry | 4,096 / 256 MiB |
| source / decoded media | 64 MiB / 256 MiB |
| image pixels | 67,108,864 |
| audio frames | 57,600,000 |
| IPC message | 16 MiB |
| decoder metadata depth / nodes | 32 / 4,096 |
| derivative cache entries / bytes | 4,096 / 512 MiB |
| Linux worker address space | 768 MiB |
| Linux worker CPU | 5 seconds |
| Linux worker FDs / file output / child processes | 16 / 16 MiB / 0 |

`tools/measure_smx040.py` records the exact OS/architecture/Python/OpenSSL context, preflight cost and—when the host actually provides every Linux primitive—sandboxed worker round-trip evidence. A missing primitive is reported as a release blocker rather than counted as a successful sandbox test.

## Protected Asset source/audio/provenance boundary

A stable `AssetId` still selects one indivisible immutable canonical protected Asset revision containing revision/content digest, source digest and source identity, exact source metadata, audio/media semantic metadata, provenance, licence/attribution and derivation lineage. Trust authenticates bytes; decoder output is target-private. Neither may synthesize canonical meaning by field-mixing competing revisions. Complete-revision validation remains explicit and derivative cache placement/eviction is non-semantic.

## Adversarial and residual evidence

`spec/production/smx040-security-fixtures.json` freezes PSH-001..PSH-032. Production tests cover container framing/kinds, exact and max+1 resource limits, recursive authority injection before worker invocation, source/result tamper, derivative-cache atomicity, live SMX-027 revoke-after-admission behavior, Linux release gating and hostile syscall probes when the runner supports the full sandbox, bounded trust parsing, threshold/freshness/rollback/mix-and-match/root-rotation behavior, exact target binding, real Ed25519 verification/tamper rejection, malformed-metadata mutation, safe failures and protected Asset completeness. The hardened web worker contract is independently exercised under Node.

SMX-040 does not claim browser-engine/kernel/decoder exploit impossibility, Windows/macOS/mobile sandbox parity, availability under an active network attacker, operational root-key ceremony, or final product-wide security certification. Those residuals stay explicit for SMX-041 and later target-specific work. No Architecture-v1 semantic amendment is required.
