#!/usr/bin/env python3
from pathlib import Path
p = Path('docs/research/SMX-018-COLLABORATION-HARNESS.md')
text = p.read_text(encoding='utf-8')
old = 'SMX-018 does **not** choose the final collaboration substrate. O-021 remains open for:'
new = ('SMX-018 does **not** choose the final collaboration substrate. O-021 remains open for the underlying persistence questions; '
       'SMX-018 records the production collaboration handoff as **O-026**, including:')
if old not in text:
    raise SystemExit('expected residual-work marker not found')
p.write_text(text.replace(old, new, 1), encoding='utf-8')
