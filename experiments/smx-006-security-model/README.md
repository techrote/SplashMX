# SMX-006 capability sandbox research harness

This directory is a **disposable, non-production falsification model** for SMX-006. It exists to test security semantics, not to define the production runtime API or storage layout.

## Research question

Can SplashMX represent deny-by-default host authority using explicit principals, scoped/delegated/revocable capability leases, bounded package/migration/network ingress, and per-principal service quotas without relying on containment or package signatures for trust?

## Hypotheses

- H-006
- H-009
- H-014
- H-015

## Direct corpus coverage

- C-011, C-022, C-026
- A-003, A-004, A-012, A-015

## Source baseline

Branch started from `main` commit `1c8e333f5285a47285eac59b8cfee6b449dd728a` (SMX-005 merged result).

## Runtime

Python 3 standard library only. No network access is required by the harness.

## Run

```bash
python -m unittest discover -s experiments/smx-006-security-model -p 'test_*.py'
```

Expected result: all deterministic tests pass.

## Non-normative warning

The Python classes, IDs, dictionaries, quota numbers, and algorithms here are deliberately small research stand-ins. Durable conclusions live in `docs/research/SMX-006-CAPABILITY-SANDBOX.md`, especially SEC-001 through SEC-018.
