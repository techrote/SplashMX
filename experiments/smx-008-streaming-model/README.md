# SMX-008 streaming/migration research harness

This directory is a **disposable, non-production falsification model** for SMX-008. It tests streaming, dependency acquisition, cache/eviction, hot replacement, retry, and fresh-host migration semantics without selecting a production package format, CDN, version solver, or Godot loader mapping.

## Research question

Can SplashMX preserve stable Thing/component/behaviour semantics while logical objects and immutable source artifacts cross residency boundaries independently, with exact verified dependencies, atomic acquisition, explicit failure states, and transactional state migration?

## Hypotheses

- H-005
- H-010
- H-011
- H-018

## Direct corpus coverage

- C-006, C-011, C-012, C-015, C-024, C-025, C-026, C-027
- A-006, A-012, A-015

## Source baseline

Branch started from `main` commit `9d302ce481b1154606a76f4fe391f9e9c69cfdde` (SMX-007 merged result).

## Run

```bash
python -m unittest discover -s experiments/smx-008-streaming-model -p 'test_*.py'
```

Python standard library only.

## Non-normative warning

The Python records, cache representation, version strings, dependency closure algorithm, quotas, and migration callables are research stand-ins. Durable conclusions live in `docs/research/SMX-008-STREAMING-MIGRATION.md`, especially STR-001 through STR-020.
