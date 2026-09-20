# Production source root

`src/` contains production SplashMX implementation code and the machine-readable module responsibility manifest.

SMX-021 established `MODULES.json`, typed conformance/failure/version/benchmark contracts and the shared durable-identity guardrails. SMX-023 now implements the first semantic production module, `canonical.core`, under `src/splashmx/canonical/`. Later issues activate serialization/storage, execution, editor, package, Godot, collaboration, networking and distribution modules according to `docs/implementation/PRODUCTION-PROGRAMME-V1.md`.

Every production module must declare its owning SMX issue, Architecture-v1 gates, responsibilities, accepted durable semantic identity classes and the shared forbidden host/transient identity classes in `MODULES.json`.

Internal adapters may use Godot/browser/database/network handles privately. They may not promote NodePath, RID, ResourceUID/resource paths, DOM identity, row/cache keys, URLs, peer/socket/session identifiers or process handles into durable SplashMX identity. R-019-01 remains explicit: semantic `ConnectionId` is valid; transient `connection_handle` is not.

The canonical core keeps authored logical state separate from transient process/editor/network context and does not choose physical encoding or persistence. Complete protected `AssetId` revision serialization remains owned by SMX-024; no production layer may field-mix digest, source identity/metadata, audio/media semantics, provenance, licence/attribution or derivation.
