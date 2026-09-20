# Production source root

`src/` contains production SplashMX implementation code and the machine-readable module responsibility manifest.

SMX-021 established `MODULES.json`, typed conformance/failure/version/benchmark contracts and the shared durable-identity guardrails. The production path now includes `canonical.core` (SMX-023), canonical serialization/protected assets (SMX-024), crash-safe local persistence (SMX-025), the bounded common execution IR (SMX-026), principal capabilities/trusted host services (SMX-027), and transactional Behaviour hot replacement (SMX-028). Later issues activate lifecycle, streaming, editor, package, Godot, collaboration, networking and distribution modules according to `docs/implementation/PRODUCTION-PROGRAMME-V1.md`.

Every production module must declare its owning SMX issue, Architecture-v1 gates, responsibilities, accepted durable semantic identity classes and the shared forbidden host/transient identity classes in `MODULES.json`.

Internal adapters may use Godot/browser/database/network handles privately. They may not promote NodePath, RID, ResourceUID/resource paths, DOM identity, row/cache keys, URLs, peer/socket/session identifiers or process handles into durable SplashMX identity. R-019-01 remains explicit: semantic `ConnectionId` is valid; transient `connection_handle` is not.

The canonical core keeps authored logical state separate from transient process/editor/network context. SMX-028 preserves that separation: a runtime Behaviour replacement keeps stable `ThingId`/`BehaviourAttachmentId`, migrates private state and pending work explicitly, and rebinds capabilities from live policy rather than serializing grants through replacement. It does not silently mutate the editable canonical project.

Complete protected `AssetId` revision serialization remains owned by SMX-024; no production layer may field-mix digest, source identity/metadata, audio/media semantics, provenance, licence/attribution or derivation. Behaviour hot replacement does not broaden that mutation surface.
