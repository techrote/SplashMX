# SMX-002 disposable kernel model

This directory is a **research falsification harness**, not production SplashMX runtime code.

It exists to test a narrow semantic claim from SMX-002: a Thing can retain stable identity while containment, control, authority, observation, persistence-service, replication-session, capability-grant, engine-handle, and behaviour-facet relationships change independently.

Run:

```bash
python -m unittest discover -s experiments/smx-002-kernel-model -p 'test_*.py'
```

The exact Python classes, relation storage, string IDs, and port implementation are non-normative. Only the invariants explicitly documented in `docs/research/SMX-002-THING-KERNEL.md` are research conclusions.
