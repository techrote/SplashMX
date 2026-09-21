# SMX-039 physical security mechanism spike

This disposable spike falsifies the **selected physical enforcement seams** for issue #64. It is not a production sandbox implementation or certification.

It deliberately imports the production SMX-035 SPB1 parser, then probes the additional Phase-7 boundaries selected by `docs/research/SMX-039-SECURITY-MECHANISM-SELECTION.md`:

- ordinary packages remain pathless SPB1 and reject executable/native/script entry kinds;
- decoder descriptors are independently bounded and recursively reject serialized authority before any decoder call;
- public-untrusted web decode requires a dedicated constrained WASM Worker profile;
- Linux native/headless decode requires a dedicated process with no-new-privileges, seccomp, Landlock and rlimit policy;
- hosted repository trust uses threshold/freshness/rollback-aware metadata and exact target binding;
- an actual OpenSSL Ed25519 roundtrip rejects tampering;
- signatures never mint SplashMX capability;
- protected Asset replacement remains a complete canonical revision.

Run from repository root:

```sh
PYTHONPATH=src:experiments/smx-039-security-mechanism-spike \
  python -m unittest discover -s experiments/smx-039-security-mechanism-spike -p 'test_*.py' -v
```

The numeric media ceilings are candidate calibration inputs. SMX-040 must measure named real targets and retain finite independently enforced limits; it must not restate these spike values as universal product SLOs.
