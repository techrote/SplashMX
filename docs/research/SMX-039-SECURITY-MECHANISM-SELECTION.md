# SMX-039 — production sandbox, decoder and cryptographic-trust mechanism selection

**Status:** selected Phase-7 production handoff for SMX-040; bounded mechanism-selection spike, **not** end-to-end sandbox certification  
**Issue:** SMX-039 / #64  
**Date:** 2026-09-21  
**Authority:** Architecture v1.0 + SMX-016 + SMX-027 + SMX-034/035 + SMX-037/038  
**Executable evidence:** `experiments/smx-039-security-mechanism-spike/` and `SMX-039-SECURITY-MECHANISM-FIXTURES.json`

## Contents

| Section | Summary |
|---|---|
| 1. Result | Selects the physical package, decoder, repository-trust and target-isolation mechanisms. |
| 2. Inherited invariants | Freezes the semantic/security rules this spike may not redefine. |
| 3. Package/container boundary | Keeps ordinary packages on bounded pathless SPB1 and rejects extraction semantics. |
| 4. Decoder/import boundary | Selects preflight plus isolated decoder brokers and explicit public-content release gates. |
| 5. Cryptographic trust | Selects a TUF-compatible threshold/freshness/rotation state machine with Ed25519 profile. |
| 6. Target isolation | Defines browser and Linux native/headless hardening and honest weaker-target blockers. |
| 7. Limits and enforcement points | Records independently measurable candidate ceilings and where they apply. |
| 8. R-016 reconciliation | Maps all four SMX-016 corrections onto the physical boundary. |
| 9. Protected media | Preserves complete source/audio/provenance/licence/derivation revisions. |
| 10. Adversarial evidence | Maps SEC-001–024 to the disposable spike. |
| 11. Alternatives and residual risk | Rejects unsafe shortcuts and states what remains unproven. |
| 12. SMX-040 handoff | Defines the production implementation contract and release blockers. |
| 13. Primary sources | Records the current external facts used for selection. |

## 1. Result

SMX-039 selects a deliberately layered physical boundary beneath Architecture v1:

```text
remote/local package bytes
        |
        v
TUF-compatible repository metadata state
  threshold root/targets/snapshot/timestamp roles
  monotonic versions + expiry + rollback/freeze/mix-and-match defence
  SplashMX profile: Ed25519 signatures
        |
        v
exact PackageRevisionId + byte length + SHA-256 digest
        |
        v
bounded pathless SPB1 parser
  no paths / links / install scripts / compression / executable kinds
        |
        v
canonical/package semantic validation
        |
        +-----------------------+
        | protected media bytes |
        v                       |
pre-decode descriptor bounds    |
        |                       |
        v                       |
isolated decoder broker         |
  web: dedicated module Worker + fixed-max WASM linear memory
       + worker CSP/no network + hardened player build
  Linux native/headless: dedicated process + no_new_privs
       + seccomp allowlist + Landlock deny-by-default + rlimits
        |
        v
bounded typed derivative result
        |
        v
existing SMX-027 capability/host-service boundary
```

This selection **does not** make signatures into capabilities, decoder output into canonical source truth, a Worker into a guaranteed OS process, or a Linux sandbox into a cross-platform claim. Where the selected isolation cannot be supplied, public untrusted content is release-blocked rather than silently run with weaker protection.

No Architecture-v1 semantic amendment is required.

## 2. Inherited invariants

The following remain authoritative and are not reopened by this spike:

- ordinary user content cannot execute raw GDScript, JavaScript, native extensions, shell/process commands, arbitrary filesystem or socket operations;
- package/runtime/offline identity is exact and immutable; repository location, trust metadata and cache location are not `PackageId` or `PackageRevisionId`;
- a valid signature, known publisher, provenance statement or licence **never grants runtime capability**;
- SMX-027 owns principal capabilities, bounded delegation/revocation and the final authorization recheck immediately before trusted host use;
- production canonical/network/IR paths retain R-016-02 recursive serialized-authority rejection;
- target-private Node/RID/ResourceUID/process/worker/decoder handles remain non-canonical;
- protected Asset replacement is complete-revision atomicity, never field mixing;
- generic web/native/headless runtimes remain one canonical format with typed target capabilities rather than separate semantic object models.

## 3. Package/container boundary

### Selection: keep ordinary packages on SPB1

SMX-034/035 already removed the dominant archive-extraction attack class by selecting and implementing **SPB1**, a pathless fixed framing containing a deterministic-CBOR index and tightly packed immutable blobs. SMX-039 therefore rejects a regression to ZIP/TAR/7z as the ordinary package boundary.

The production parser already enforces:

- total bundle byte bound;
- exact header/index/payload framing with no trailing chaff;
- bounded deterministic-CBOR index;
- bounded entry count and per-entry bytes;
- tightly packed, non-overlapping entries in index order;
- unique artifact IDs/digests;
- exact SHA-256 verification;
- no unindexed payload bytes.

The selected physical policy adds an explicit ordinary-content rule: executable/native/script/package-loader entry kinds are rejected. `SPB1` itself has no paths, links, modes, devices, nested archive semantics, install hooks or v1 compression.

### R-016-01 treatment

R-016-01 remains authoritative for **any future external path-bearing import format**, but ordinary production packages avoid host path normalization entirely. A future ZIP/TAR importer must normalize/collision-check the whole archive namespace before touching a host filesystem, reject traversal/absolute/device/link/special-file ambiguity, and independently bound compressed/expanded work. It cannot feed generic extraction directly into the canonical package path.

This is stronger than saying “our ZIP library probably sanitizes names”: the ordinary path does not possess an extraction pathname at all.

## 4. Decoder/import boundary

Decoders remain dangerous after package integrity succeeds. A signed JPEG, audio stream, font or mesh can still exploit a decoder. SMX-039 therefore selects a **preflight + broker + isolated worker + bounded result** architecture.

### Before decoder invocation

Trusted host code must validate a closed descriptor and enforce independent ceilings for:

- compressed/source bytes;
- predicted/declared decoded bytes where available;
- image pixel count/dimensions;
- audio frame/channel/duration-derived work;
- metadata tree depth/node count/string/collection sizes;
- broker IPC request/response bytes;
- exact source digest/revision association;
- recursive transient-authority rejection.

A denial occurs before the decoder is called. The spike records decoder-call count to make ordering observable.

### Web selection

For public untrusted media on the browser target:

1. decoding/import runs in a **dedicated module Web Worker** owned by trusted runtime code;
2. decoder code is a pinned trusted WebAssembly module with a fixed maximum linear memory and a deliberately tiny import surface;
3. the worker response carries its own restrictive CSP; network egress is denied (`connect-src 'none'`) and worker/module sources are pinned to trusted same-origin assets;
4. messages use a bounded closed schema and transferable immutable byte buffers; no DOM, Godot object, capability grant, session/peer handle or host object is accepted;
5. the hardened public player build disables Godot `JavaScriptBridge` at build time;
6. decoded output is a target-private derivative and is revalidated for declared dimensions/size before cache publication.

A Web Worker is **not claimed to guarantee a separate OS process**. The security boundary relies on the browser sandbox plus a WebAssembly linear-memory containment boundary with no ambient host imports. If a required decoder cannot be supplied in this constrained WASM form, that format is disabled for public untrusted browser content until equivalent isolation exists.

COOP/COEP/cross-origin isolation may be required for particular Godot threaded exports and can improve browsing-context isolation, but it is not treated as a decoder sandbox or substitute for the worker/WASM boundary.

### Linux native/headless selection

For Linux native and headless public-untrusted paths, decoding/import runs in a **dedicated worker process**. After startup it must enter all of:

- `PR_SET_NO_NEW_PRIVS` (or equivalent kernel-enforced state);
- seccomp-BPF syscall allowlist denying process creation, raw networking and unrelated kernel surface;
- Landlock deny-by-default filesystem policy, with only explicitly required immutable descriptors accessible;
- explicit rlimits/resource-accounting ceilings for address space, CPU time, files/descriptors, file output and child processes;
- bounded framed IPC with no file path, socket, capability token, Godot object or semantic-authority transfer.

Headless does not get a privileged shortcut merely because rendering is absent.

### Other native targets

SMX-039 does **not** pretend the Linux stack is portable. Windows/macOS/mobile public-untrusted distribution remains release-blocked until SMX-040 or a later target-specific task provides and tests an equivalent process sandbox. Local/trusted author workflows may use a separately declared trust domain, but that is not permission to label weaker execution as safe for arbitrary public content.

## 5. Cryptographic trust

### Selection: TUF-compatible repository metadata state machine

Hosted/public package distribution adopts **The Update Framework (TUF) trust model** rather than inventing a single detached-signature convention. The SplashMX implementation profile must retain the four top-level trust roles and their distinct compromise properties:

- **root** — offline trust root and role/key thresholds;
- **targets** — signed exact target descriptors;
- **snapshot** — coherent metadata-version set preventing mix-and-match;
- **timestamp** — short-lived freshness statement preventing indefinite replay/freeze.

Client state persists trusted root and highest accepted metadata versions. Root updates are sequential and must satisfy both the currently trusted root threshold and the candidate root threshold. Expired metadata fails closed. Version rollback, stale/frozen metadata and mix-and-match fail closed. Revoked/removed keys cannot satisfy future thresholds after the corresponding trusted root update.

### SplashMX signing profile

The initial profile selects **Ed25519** for repository metadata signatures. The spike executes a real OpenSSL Ed25519 sign/verify cycle and tamper rejection; it does not implement private-key operations in SplashMX runtime code.

Target metadata binds at minimum:

- exact `PackageRevisionId`/distribution target identity;
- exact byte length;
- SHA-256 digest;
- metadata version/freshness context.

The existing exact `ResolutionLock` remains runtime package authority. TUF decides whether remote bytes are acceptable from a configured repository/trust domain; it does not replace SplashMX package identity or semantic compatibility checks.

### Trust is not capability

Cryptographic authenticity may answer “did a configured repository/publisher trust role authorize these exact bytes?” It does **not** answer “may this package access network/filesystem/input/process/native APIs?”. Capability policy remains independent and defaults to no ambient authority.

Likewise, licence/provenance/source availability remains evidence/policy metadata, not cryptographic execution authority.

## 6. Target isolation

The selected release posture is fail-closed and target-specific:

| Target/profile | Physical decoder boundary | Public untrusted content |
|---|---|---|
| Web hardened | dedicated module Worker + fixed-max WASM memory + restrictive worker CSP + hardened Godot build | allowed only for formats served by the constrained decoder profile |
| Linux native | dedicated process + no_new_privs + seccomp + Landlock + rlimits | allowed only when every required sandbox primitive is active |
| Linux headless | same process sandbox; presentation services omitted semantically | allowed only when every required sandbox primitive is active |
| Web unsafe decoder/native bridge | no selected containment equivalent | **release blocker** |
| Native platforms without equivalent tested worker sandbox | weaker/unselected physical boundary | **release blocker** for arbitrary public content |

The browser's same-origin policy, COOP/COEP and Worker separation are defence in depth, not proof of process separation. Linux Landlock confines filesystem access but is not a general syscall sandbox; seccomp and resource limits are independently required. `no_new_privs` alone is also insufficient.

## 7. Limits and enforcement points

The durable requirement is independent finite dimensions checked **before** the expensive/unsafe boundary. The spike uses concrete candidate ceilings so max/max+1 behavior is executable. These are initial production-calibration inputs, not universal performance SLOs:

| Boundary | Candidate ceiling in spike/production baseline | Enforcement point |
|---|---:|---|
| SPB1 total bytes | 512 MiB | before parser allocation |
| SPB1 index bytes | 8 MiB | fixed-header parse |
| SPB1 entries | 4,096 | deterministic-CBOR/index validation |
| SPB1 single entry | 256 MiB | before payload slice/publication |
| compressed media bytes | 64 MiB | decoder broker admission |
| decoded media bytes | 256 MiB | decoder broker admission + result verification |
| image pixels | 67,108,864 (8192²) | decoder broker admission/result |
| audio frames | 57,600,000 | decoder broker admission/result |
| broker message bytes | 16 MiB | IPC framing |
| decoder metadata depth | 32 | recursive ingress validation |
| decoder metadata nodes | 4,096 | recursive ingress validation |

SMX-040 must benchmark representative legitimate assets on named browser/native/headless environments and either retain or deliberately revise these values. A revision must remain finite, independently enforced and regression-tested. Do not replace structural limits with one wall-clock timeout.

OS worker limits (address-space/CPU/file descriptors/output/children) are additionally mandatory but must be calibrated against the chosen decoder corpus on the named target; this spike does not invent universal values without measurement.

## 8. R-016 reconciliation

All four accepted SMX-016 corrections remain enforceable at the physical boundary:

- **R-016-01 — host-independent path normalization/collision:** ordinary SPB1 removes path extraction. Any future path-bearing importer must normalize/collision-check before filesystem use and remains outside ordinary package parsing until it carries equivalent evidence.
- **R-016-02 — recursive authority-token rejection:** decoder broker messages recursively reject capability grants/tokens, host/native/browser/Godot handles, peer/session/socket/process identities and loader authority. Existing canonical/network/IR rejection remains unchanged.
- **R-016-03 — bounded delegation before allocation:** physical workers receive data descriptors, not delegated capability objects. Any host service used to acquire/start a worker still passes through the existing bounded SMX-027 principal/grant ancestry rules.
- **R-016-04 — final authorization immediately before host use:** staging a decode/acquisition request does not preserve authorization. Capability/revocation/expiry is rechecked at the trusted host adapter immediately before crossing into the worker/repository/host service.

Signature validity cannot bypass any of these corrections.

## 9. Protected media

A stable `AssetId` continues to select one indivisible immutable canonical revision containing:

- revision/content digest;
- source digest and source identity;
- exact source metadata;
- audio/media semantic metadata;
- provenance;
- licence/attribution;
- derivation lineage.

Package trust authenticates bytes; decoder isolation converts verified source bytes into a target-private derivative. Neither operation is allowed to synthesize a new canonical Asset by taking fields from competing revisions.

The decoder cache key must include at least exact `AssetId + revision_digest + target/profile + derivative kind/version`. Cache/decoder/GPU/audio handles remain transient. A decode failure leaves the prior coherent canonical Asset revision untouched. SEC-023 deliberately rejects a partial replacement candidate.

## 10. Adversarial evidence

The machine-readable corpus `SMX-039-SECURITY-MECHANISM-FIXTURES.json` contains exactly **SEC-001–SEC-024**. The executable spike covers:

- the real production SPB1 parser, foreign-archive rejection, total/per-entry bounds and executable-kind denial;
- exact media-budget boundaries, max+1 failures, recursive authority injection and “decoder call count stays zero” ordering;
- browser constrained-WASM acceptance and unsafe-decoder release blocking;
- Linux native/headless sandbox-component omission one at a time;
- trust threshold, revocation, rollback, expiry/freeze, exact target binding and dual-threshold root rotation;
- a real Ed25519 OpenSSL roundtrip plus tamper rejection;
- authenticity/capability separation;
- protected Asset complete-revision preservation.

The spike is intentionally small enough to falsify the selected seams. It is not a replacement for SMX-040 real-process/browser hardening tests.

## 11. Alternatives and residual risk

### Generic ZIP/TAR as production package container — rejected

It adds path traversal, Unicode/case collisions, links/devices, extraction roots and decompression behavior without product value for the canonical package format. SPB1 removes that surface. Generic archives may exist only as separately hardened import formats.

### In-process native media decoders for arbitrary public content — rejected

Size preflight reduces denial-of-service but does not contain memory-corruption bugs. Public-untrusted decode therefore requires the selected worker isolation. A trusted/local mode may deliberately choose more compatibility, but must be visibly a different trust domain.

### “Web Worker means process sandbox” — rejected

Browsers do not promise a one-worker-per-OS-process security boundary. The web selection therefore additionally constrains decoder code to fixed-memory WebAssembly with a minimal import surface and uses browser/worker policy as defence in depth.

### One publisher signature — rejected

It lacks threshold compromise resistance, freshness, rollback/freeze and coherent metadata-set protection. TUF-compatible role separation is selected instead.

### Signature means safe content/capability — rejected

A trusted signer can accidentally ship malformed media, and publisher trust is not host authority. Decoder isolation and SMX-027 remain mandatory.

### Residual attack surface

This spike does not certify:

- a concrete SMX-040 seccomp syscall list, Landlock ruleset or rlimit values;
- Windows/macOS/mobile equivalent sandboxes;
- browser-engine exploit resistance or guaranteed Worker process placement;
- vulnerabilities within the chosen trusted runtime, OpenSSL/TUF implementation, browser, kernel, Godot or decoder module;
- side channels or speculative-execution classes;
- operational root-key ceremony, HSM/offline-key custody, incident response or transparency-log deployment;
- public-repository availability under an active network attacker (denial remains possible);
- final safe quota values for all legitimate content.

These are implementation/operations obligations, not permission to weaken the semantic boundary.

## 12. SMX-040 handoff

SMX-040 may implement directly from this selection. It must:

1. keep production ordinary packages on SPB1 and preserve current parser bounds/adversarial fixtures;
2. add a production `SecurityBoundary`/decoder broker that preflights all selected dimensions before worker invocation and revalidates outputs before cache publication;
3. implement the constrained Web Worker/WASM path with explicit worker CSP/network denial and a hardened public-player build with `JavaScriptBridge` disabled;
4. implement and test the Linux native/headless decoder worker with no_new_privs, seccomp allowlist, Landlock deny-by-default and rlimits; if a required primitive is absent, public-untrusted mode fails closed;
5. add TUF-compatible repository trust state with root/targets/snapshot/timestamp roles, Ed25519 signatures, sequential dual-threshold root rotation, expiry/freshness and rollback/mix-and-match defenses;
6. bind trusted targets to exact immutable PackageRevisionId + length + digest before SPB1/canonical activation;
7. preserve SMX-027 authorization at host-use time; trust/signatures never create capabilities;
8. preserve the complete protected Asset revision and keep decoder derivatives target-private;
9. calibrate OS worker and media limits on named real targets, retain finite independent ceilings, and record measurements as environment-specific evidence rather than universal SLOs;
10. release-block public untrusted content on any target/profile that cannot meet the selected physical isolation contract.

SMX-040 must not silently replace a missing sandbox with an in-process decoder or call a green semantic harness “sandbox certification”.

## 13. Primary sources checked 2026-09-21

- The Update Framework specification, current page reports **v1.0.36**, last modified 2026-08-05: <https://theupdateframework.io/specification/latest/>. Relevant properties used here are threshold roles, trusted root bootstrap/rotation, targets/snapshot/timestamp separation, expiry/freshness, rollback/freeze/mix-and-match defenses and exact target hash/length verification.
- Linux kernel Landlock userspace API: <https://www.kernel.org/doc/html/latest/userspace-api/landlock.html>. Landlock is a restrictive, stackable filesystem access-control mechanism; unprivileged confinement is tied to `no_new_privs` requirements.
- Linux `no_new_privs`: <https://www.kernel.org/doc/html/latest/userspace-api/no_new_privs.html>. It prevents `execve()` from gaining privileges and is required for unprivileged seccomp-filter installation.
- Linux seccomp filter documentation: <https://www.kernel.org/doc/html/latest/userspace-api/seccomp_filter.html>. seccomp-BPF restricts syscall surface and composes with `no_new_privs`; it is not a filesystem namespace by itself.
- MDN Web Workers/CSP/cross-origin isolation: <https://developer.mozilla.org/en-US/docs/Web/API/Worker/Worker>, <https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy>, <https://developer.mozilla.org/en-US/docs/Web/API/WorkerGlobalScope/crossOriginIsolated>. Workers lack direct DOM access, but Worker separation is not treated here as a guaranteed process sandbox; worker scripts require their own CSP response policy.
- Godot JavaScriptBridge 4.x documentation: <https://docs.godotengine.org/en/4.6/classes/class_javascriptbridge.html>. The bridge exposes browser JavaScript context in Web export and can be disabled at build time; official templates enable it by default, which is why the hardened public profile requires a custom build.
- Godot Web export documentation: <https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html>. Threaded Web exports require secure context/cross-origin isolation; those headers are deployment requirements, not a substitute for content isolation.
