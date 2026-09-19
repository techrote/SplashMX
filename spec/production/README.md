# SplashMX production meta-contracts

This directory contains **Phase-0 implementation guardrails**, not the final project/package/IR byte formats.

- `conformance-registry.json` maps all ten Architecture-v1 production gates to retained evidence, production module owners, current regression coverage and future implementation issues.
- `failure-envelope.schema.json` defines the author-safe typed failure envelope used at production boundaries.
- `artifact-version.schema.json` defines version metadata every durable production artefact family must carry from its first implementation.
- `benchmark-evidence.schema.json` defines the minimum evidence metadata required before performance measurements are used for product or architecture claims.
- `module-manifest.schema.json` validates the production module responsibility/identity manifest at `src/MODULES.json`.

The JSON Schema documents intentionally use a small dependency-free subset validated by `tools/production_contracts.py`. They do not select a production runtime language or physical canonical encoding.

Architecture v1 remains the semantic authority. These contracts exist to make accidental drift mechanically visible.
