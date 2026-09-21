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

`tools/validate_smx042.py` compares the complete CR-001..028 representability
map with the authoritative SMX-018 fixture file, so selection evidence cannot
silently drift from the frozen collaboration conflict corpus.

The dedicated CI gate also reruns the SMX-018 collaboration harness plus the
SMX-023 canonical-core and SMX-025 persistence regressions. Production
implementation belongs to SMX-043.
