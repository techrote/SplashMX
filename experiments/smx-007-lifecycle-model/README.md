# SMX-007 lifecycle/restore research harness

This directory is a **disposable, non-production falsification model** for SMX-007. It tests lifecycle, snapshot, restore, timer, reference, tombstone, and deterministic-state semantics without Godot or any surviving in-memory runtime object.

## Research question

Can a SplashMX runtime snapshot reconstruct the declared simulation state of Things, behaviours, timers, references, and deterministic PRNG streams in a fresh process-like model while excluding transient engine/network/capability authority and avoiding duplicated external side effects?

## Hypotheses

- H-008
- H-010
- H-018

## Direct corpus coverage

- C-002, C-006, C-012, C-024, C-025
- A-002

## Source baseline

Branch started from `main` commit `b62b6a22f8a4a36a13e9cfcdd9dafb1c9804353b` (SMX-006 merged result).

## Run

```bash
python -m unittest discover -s experiments/smx-007-lifecycle-model -p 'test_*.py'
```

Python standard library only.

## Non-normative warning

The Python records, timer implementation, snapshot shape, ID syntax, and migration callable interface are research stand-ins. Durable conclusions live in `docs/research/SMX-007-LIFECYCLE-RESTORE.md`, especially LIF-001 through LIF-018.
