# SMX-016 adversarial security harness

Disposable deterministic research harness for issue #16. It attacks the accepted package/parser/IR/capability/network/host-boundary contracts; it is **not production sandbox code** and is not a claim that Godot, browsers or native processes are escape-proof.

Run:

```text
python -m unittest discover -s experiments/smx-016-security-harness -p 'test_*.py'
```

The 38 tests cover archive/path normalization and amplification, bounded canonical input, exact-lock/dependency substitution, capability escalation/delegation/revocation/confused-deputy cases, IR/allocation/event/timer/service exhaustion, migration ordering, network authority/resource attacks, web/native/headless host-surface differences, decoder preflight, and atomic protected source/audio/provenance revisions.

`model.py` uses deliberately small deterministic quotas. Those values are test fixtures only; the durable evidence is that each resource class has an independently enforceable boundary and that unsafe/privileged work is not reached after a denial.

Authoritative synthesis and residual risks are in `docs/research/SMX-016-SECURITY-HARNESS.md`.
