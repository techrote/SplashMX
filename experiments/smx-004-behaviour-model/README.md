# SMX-004 disposable behaviour-execution model

Status: **non-production research harness**.

This directory exists only to falsify the SMX-004 execution semantics documented in
`docs/research/SMX-004-BEHAVIOUR-EXECUTION.md`.

It deliberately implements a tiny subset:

- stable Things with ordered behaviour attachments;
- bounded transactional activations;
- commit-before-follow-on-event semantics;
- explicit logical timers/continuations;
- deterministic attachment-local PRNG streams;
- capability-mediated host-service requests;
- per-activation and per-tick execution budgets;
- quiescent transactional behaviour replacement;
- compatible private-state transfer, explicit migration, and continuation remapping;
- one IR object type shared by beginner-rule compilation and hand-authored advanced behaviour.

It deliberately does **not** define:

- the production IR binary/text encoding;
- the final compiler or textual language;
- Godot integration;
- persistence/serialization of runtime queues;
- a secure hostile-code sandbox;
- multiplayer replication semantics;
- browser performance.

## Run

From repository root:

```bash
python -m unittest discover -s experiments/smx-004-behaviour-model -p 'test_*.py'
```

The harness is dependency-free and deterministic.

## Research references

- `EXE-001` through `EXE-015`: candidate execution invariants.
- `ET-001` through `ET-011`: fixture classes in
  `docs/research/SMX-004-BEHAVIOUR-FIXTURES.json`.

If a later issue needs different implementation machinery while preserving the documented
semantics, replace this code rather than treating it as a compatibility layer.
