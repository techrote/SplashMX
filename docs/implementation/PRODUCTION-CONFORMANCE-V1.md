# SplashMX production conformance bootstrap v1

**Status:** Phase-0 production guardrail contract  
**Issue:** SMX-021 / #46  
**Architecture authority:** `docs/architecture/ARCHITECTURE-V1.md`

SMX-021 creates the implementation substrate needed to keep Architecture v1 machine-checkable while production code begins. It does not choose the final canonical encoding, runtime language, VM, storage engine, package container, Godot realization, collaboration substrate or network transport.

## Conformance registry

`spec/production/conformance-registry.json` contains exactly one entry for every Architecture-v1 production gate. Each gate records the frozen requirement in implementation terms, retained evidence lineage, declared production module owners, current regression evidence and future SMX issues that must port the evidence to real production boundaries.

A gate's `future_issue_codes` list is an obligation queue, not a permanent non-empty marker. Once all listed obligations for that gate have landed, the list may be empty only if every declared owner module is `implemented` and the gate has real `tests/production/` regression coverage. This allows completed gates to reach an explicit terminal state without weakening the guard against prematurely deleting future work.

The registry also carries a non-droppable cross-cutting regression list. R-016-01..04, R-018-01..04, R-019-01 and protected-media atomicity may acquire stronger production tests, but they may not silently disappear from conformance coverage.

## Typed failures

`failure-envelope.schema.json` establishes an author-safe failure envelope: stable SplashMX code/category, localizable message key, severity/retryability, bounded public details and an optional diagnostic correlation ID.

Raw host exceptions are deliberately not part of that envelope. Godot/browser/package/database/network implementation text belongs in internal telemetry, not ordinary author-facing semantics.

## Version metadata

`artifact-version.schema.json` requires every durable production artefact family to identify its SplashMX-owned schema family/version, required semantic features and producing implementation/build.

This is a compatibility envelope, not a decision about physical bytes. Later issues may select encodings beneath it without changing the requirement that unsupported required semantics fail explicitly.

## Benchmark evidence

`benchmark-evidence.schema.json` prevents anonymous performance numbers from becoming design claims. Measurements record target profile, exact runtime/build, OS/architecture/hardware, workload, sample count and named metric/statistic/unit/value.

Browser measurements may additionally identify the browser/version. Later performance issues can extend measurement payloads through a versioned replacement rather than silently changing this contract.

## Production module ownership and identity guard

`src/MODULES.json` declares the production module map anticipated by SMX-021–052. Only `contracts.conformance` is active in Phase 0; semantic/runtime modules transition from `planned` to `implemented` only when their owning production issues genuinely land.

The manifest is validated against a common forbidden durable identity set. Host/transient identities may exist inside private adapters but cannot be declared as canonical identity inputs. The guard deliberately permits semantic `ConnectionId` while rejecting transient `connection_handle`, preserving R-019-01.

SMX-032 activates `browser.editor` as a production authoring projection. Its canonical identity inputs are `ThingId`, `DefinitionId`, `ConnectionId` and `AssetId`; browser/DOM/session handles remain non-canonical. GATE-04 now carries direct production unit and real-Chromium authoring evidence while retaining SMX-033, SMX-036 and SMX-048 as future obligations. The protected-media cross-cutting regression now also names `browser.editor`, because media import is an authoring boundary that must preserve the complete immutable Asset revision.

## CI and future issues

Every PR continues to run the complete retained research/freeze regression suite. SMX-021 adds two dependency-free checks:

```text
python tools/validate_smx021.py
python -m unittest discover -s tests/production -p 'test_smx021.py' -v
```

Future production issues must update the registry/module manifest when they activate an owned module or replace a future test obligation with real production coverage. Passing a pre-v1 harness remains evidence lineage, not production certification.

For SMX-032, the direct production authoring tests and pinned real-Chromium campaign are registered under GATE-04, while the P4 gate remains explicitly open for SMX-033. This distinction prevents a working editor shell from being mistaken for completed browser Play/Stop, persistence, diagnostics, accessibility, publication or human-usability qualification.
