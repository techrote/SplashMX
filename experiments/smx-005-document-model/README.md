# SMX-005 disposable canonical-document model

This directory contains a **non-production, non-normative** Python model used only to falsify the semantic claims in SMX-005.

It is intentionally dependency-free and does **not** select the final SplashMX byte encoding, database, package container, ID text syntax, collaboration algorithm, or runtime store.

## Research questions exercised

- Can stable logical IDs survive rename, reparent, and physical chunk relocation?
- Can references distinguish loaded, known-unloaded, tombstoned, unknown, incompatible, and unavailable-dependency states?
- Can the SMX-003 definition/instance/provenance/overlay model round-trip without path identity?
- Can behaviour definitions/attachments be authored independently of SMX-004 live executor state?
- Can edits apply as atomic semantic transactions with preconditions?
- Can a deterministic schema migration preserve IDs, references, and optional unknown extension data?
- Can required unknown features fail closed while optional extension payloads remain preservable?
- Can logical asset identity remain stable while immutable content blobs change?
- Can a deterministic research projection avoid map/record insertion-order dependence?
- Can malformed/duplicate/oversized/digest-invalid data fail validation?

## Run

From the repository root:

```bash
python -m unittest discover -s experiments/smx-005-document-model -p 'test_*.py'
```

The CI workflow also runs `tools/validate_smx005.py` to ensure fixture IDs, corpus references, and non-normative status remain consistent with the research document.

## Deliberate limitations

The experiment uses a JSON-shaped in-memory model and deterministic sorted-key JSON solely because Python's standard library makes it easy to inspect and reproduce. It does not claim JSON is the final format.

It does not implement:

- production migration registry/signatures;
- actual CBOR/Protobuf/SQLite encodings;
- CRDT/OT collaboration convergence;
- streaming scheduler/eviction;
- package signing/dependency acquisition;
- runtime/save snapshot semantics;
- hostile native parser fuzzing;
- final tombstone retention policy.
