# SMX-042 collaboration substrate spike

Disposable mechanism-selection evidence for issue #67. This directory is **not**
the production collaboration implementation.

Run:

```bash
PYTHONPATH=experiments/smx-042-collaboration-substrate-spike \
python -m unittest discover -s experiments/smx-042-collaboration-substrate-spike -p 'test_*.py' -v

PYTHONPATH=experiments/smx-042-collaboration-substrate-spike \
python experiments/smx-042-collaboration-substrate-spike/spike.py
```

The spike selects a SplashMX semantic transaction DAG with exact receipts,
validated checkpoints and conservative causal-stability compaction. The SQLite
oracle exercises the native physical mapping already selected by SMX-022/025;
it does not make SQLite identity semantic and it is not browser production code.

The dedicated CI gate also reruns the SMX-018 collaboration harness. Production
implementation belongs to SMX-043.
