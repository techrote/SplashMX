# SMX-013 disposable component/package model

This directory is **non-production research evidence** for SMX-013. It models the smallest semantics needed to falsify the component/package contract: local-definition promotion, deterministic range resolution into exact locks, required/optional/lazy dependencies, revocation/digest checks, offline cache use, principal-attributed capability requests, transactional instance updates/migration, uninstall guards, and protected asset revision bundles.

It deliberately does **not** implement a registry, network downloader, archive parser, production signature framework, final version-constraint language, marketplace, UI, or Godot package loader.

Run:

```bash
python -m unittest discover -s experiments/smx-013-package-model -p 'test_*.py'
```

A passing suite is evidence only for the model-level invariants in `docs/research/SMX-013-COMPONENT-PACKAGES.md`; SMX-016 must still attack real malformed/untrusted package boundaries and SMX-019 must test author-facing usability.
