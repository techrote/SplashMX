# Production source root

`src/` is reserved for production SplashMX implementation code. SMX-021 deliberately does **not** choose the production runtime language or implement the Thing kernel, IR, storage engine, editor, package system, Godot binding, collaboration or networking.

`MODULES.json` is the Phase-0 responsibility manifest. Before a later production issue adds a module/package, it must reconcile that manifest so the module declares:

- its owning SMX issue;
- Architecture-v1 conformance gates it helps satisfy;
- responsibilities it owns;
- any durable semantic identity classes accepted by its public/canonical interfaces;
- the shared forbidden host/transient identity classes.

Internal adapters may use Godot/browser/database/network handles privately. They may not promote NodePath, RID, ResourceUID/resource paths, DOM identity, row/cache keys, URLs, peer/socket/session identifiers or process handles into durable SplashMX identity.

R-019-01 is explicit here: semantic `ConnectionId` is valid; transient `connection_handle` is not.
