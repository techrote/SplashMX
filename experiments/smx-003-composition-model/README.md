# SMX-003 disposable composition model

Purpose: test the candidate **stable local-definition graph + concrete instance graph + sparse explicit overlay** semantics from `docs/research/SMX-003-COMPOSITION-DEFINITIONS.md`.

This code is research evidence, not production SplashMX architecture. Its Python object layout is deliberately non-normative.

## Questions exercised

- Can an ordinary concrete group be promoted into a local definition without reconstructing its existing Things?
- Can multiple instances share definition provenance while retaining distinct concrete Thing identities?
- Do intentional property/structural overrides survive compatible base-definition updates?
- Do invalidated override targets and protected destructive changes become explicit conflicts?
- Can instance-only local additions survive definition revisions?
- Can a public group/component port remain stable while internal members are reparented?
- Does definition reconciliation leave controller, authority, persistence, and replication context untouched?

## Corpus coverage

The fixture manifest maps the executable cases to C-002, C-006, C-007, C-011, C-017, C-018, C-021, C-027 and adversarial A-001, A-008, A-016.

## Run

From the repository root:

```bash
python -m unittest discover -s experiments/smx-003-composition-model -p 'test_*.py'
```

Expected result: 10 tests pass.

## Deliberate omissions

This experiment does not define:

- canonical serialization or ID encodings;
- tombstone/destroyed-object lifecycle;
- collaboration merge algorithms;
- behaviour execution/state migration;
- package/component versioning;
- performance characteristics at production scale.

Those remain assigned to SMX-004/005/007/011/013/015.
