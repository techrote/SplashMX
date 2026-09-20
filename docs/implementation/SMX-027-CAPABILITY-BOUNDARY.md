# SMX-027 — Principal capabilities and trusted host-service boundary

**Status:** production implementation beneath Architecture v1.0  
**Issue:** SMX-027 / #52  
**Depends on:** SMX-023 canonical core, SMX-026 common execution IR

SMX-027 implements the first production capability broker and trusted host-service crossing for ordinary SplashMX behaviour. It preserves the frozen rule that user content can stage a semantic service request but cannot obtain a Godot/browser/native host object, raw transport, capability issuer, or ambient privilege.

## Contents

| Section | Summary |
|---|---|
| 1. Production contract | States the implemented security boundary. |
| 2. Principal attribution | Defines the current production principal and confused-deputy rule. |
| 3. Grants, scopes and delegation | Defines typed leases, narrowing, expiry and bounded ancestry. |
| 4. Host-service lifecycle | Defines admission, quota accounting and the final-use authorization recheck. |
| 5. Capability declarations and denial | Defines required versus optional/reduced operation. |
| 6. Adversarial enforcement | Maps retained SMX-006/016 attacks into production tests. |
| 7. Protected media | Preserves the complete source/audio/provenance revision boundary. |
| 8. Residual physical security | Records what this issue deliberately does not certify. |

## 1. Production contract

`src/splashmx/security/capabilities.py` owns the production `security.capabilities` module. The contract is deny-by-default:

- ordinary `execution.ir` can only emit `ServiceRequest`; it cannot register or invoke a host callable;
- a trusted runtime policy explicitly issues root `CapabilityGrant` leases to a `PrincipalId`;
- a grant names exactly one stable `CapabilityId`, typed `CapabilityScope`, issuer policy, lifetime, revocation state and delegation permission;
- a trusted `HostServiceAdapter` maps one semantic service name to one capability, a typed request-target resolver and a host callable;
- no signature, publisher identity, provenance, licence, package containment, parent component or request payload creates authority;
- recursive grant/host/session/engine authority fields are rejected independently at the host-service boundary, carrying **R-016-02** beyond IR validation;
- service payloads/results are bounded plain values. Raw host objects are never returned to ordinary behaviour.

`PrincipalId` and `CapabilityId` are role-typed semantic identifiers. Grant IDs are live authority bookkeeping and are intentionally **not** canonical document identity.

Architecture v1.0 remains unchanged.

## 2. Principal attribution

The first production principal granularity is the exact Behaviour attachment origin already present in an SMX-026 `ServiceRequest`:

```text
PrincipalId("behaviour:<ThingId>:<BehaviourAttachmentId>")
```

This is derived by trusted runtime code from the request's causal origin. Content cannot supply an alternate principal. A grant held by a parent Thing/package/component therefore cannot authorize a child Behaviour request merely because the child is contained by it.

A future trusted component facade may deliberately proxy an operation, but that is a separate validated application/service contract. SMX-027 does not expose a generic content-controlled principal-override switch. This is the production confused-deputy rule from SEC-002/SEC-011 and AT-012/AT-017.

## 3. Grants, scopes and delegation

`CapabilityScope` is the first versioned production scope algebra. It contains explicit target and operation allow-sets plus an optional byte ceiling. `*` is a wildcard only within its declared dimension. Delegation is accepted only when all scope dimensions are equal or narrower; a finite parent byte ceiling cannot be removed or increased by a child.

Root grants are issued only through the trusted broker API. Delegated grants must satisfy all of the following **before allocation**:

1. the source grant and its complete ancestry are present and live;
2. the source is delegable;
3. the capability is inherited exactly rather than selected by child input;
4. scope monotonically narrows;
5. delegated expiry does not outlive the parent;
6. ancestry depth remains within `max_delegation_depth`;
7. descendant count remains within `max_descendants_per_root`;
8. total grants remain within `max_grants`.

`CapabilityBroker.from_trusted_grants()` validates a complete trusted runtime snapshot before publishing it. Missing ancestry, cycles, non-delegable ancestors, capability changes, scope widening, lifetime widening and count/depth excess fail closed. This is the production **R-016-03** enforcement path.

Revocation replaces the selected live grant with a revoked state. Descendants need not be rewritten: every authorization walks their bounded ancestry, so revoked or expired ancestors immediately make descendant leases non-live.

Policy time is an explicit non-negative integer supplied by the trusted runtime/policy layer. SMX-027 does not make wall-clock APIs part of user-content semantics.

## 4. Host-service lifecycle

The service path is deliberately two-stage:

```text
committed Behaviour activation
  -> ServiceRequest emitted by execution.ir
  -> TrustedHostServiceBoundary.admit()
       derive exact principal
       recursively validate payload
       resolve typed service target
       check live scoped grant
       check per-principal quota
       create inert AdmittedServiceCall
  -> asynchronous delay / platform scheduling
  -> TrustedHostServiceBoundary.execute()
       verify the call is still pending
       RECHECK THE SAME GRANT + PRINCIPAL + CAPABILITY + SCOPE + EXPIRY
       consume the one-shot call
       cross trusted HostServiceAdapter
       bound/validate plain result
```

Admission **never invokes the host**. The second authorization is intentionally the final semantic operation before the trusted adapter call. Revocation or expiry after admission therefore wins closed and the adapter is not called. This is the production **R-016-04** path.

Pending calls are one-shot and cannot be replayed. Per-principal pending and admission-window quotas are independent of the SMX-026 executor's service-request budgets, preserving layered resource enforcement. Starting a new accounting window is a trusted host-policy operation and does not cancel existing pending calls.

Trusted adapter exceptions are converted to typed `capability.host_service_failed` outcomes without exposing raw host exception text. Results containing arbitrary object instances or serialized authority fields are rejected before return to ordinary content.

## 5. Capability declarations and denial

`CapabilityRequirement` / `CapabilityPlan` provide preflight for Behaviour/component contracts:

- a **required** capability whose complete declared scope has no live covering grant fails with `capability.required_denied`;
- an **optional** denied capability remains explicitly denied;
- when the author/runtime contract names a `reduced_mode`, optional denial returns that explicit local mode rather than silently escalating, prompting, or substituting another capability.

This satisfies SEC-010/SEC-017 without treating declaration as grant. Browser/OS permission, when later added behind a concrete adapter, remains necessary-but-not-sufficient: the SplashMX grant check still occurs first and again at host crossing.

## 6. Adversarial enforcement

`tests/production/test_smx027.py` ports the relevant retained security attacks rather than re-running broad threat discovery. It covers:

- no ambient authority and no privilege from signing/provenance/licensing (ST-001/ST-009, AT-011);
- exact-principal containment isolation and confused-deputy denial (ST-003, AT-012/017);
- scoped target/operation/byte enforcement (ST-002);
- monotonic delegation and non-delegable children (ST-004, AT-013);
- bounded delegation depth/count plus missing/cyclic ancestry (AT-013/014, **R-016-03**);
- ancestor revocation/expiry propagation (ST-005);
- required denial and optional explicit reduced mode (ST-006);
- recursive serialized authority/host/session rejection (**R-016-02**, AT-007/022);
- copied grant-ID laundering attempts;
- independent per-principal pending/rate limits (ST-011/AT-016);
- unknown services and out-of-scope targets before host use;
- revocation and expiry races between admission and invocation (**R-016-04**, AT-015);
- one-shot call replay rejection;
- raw host object and raw host exception containment.

The retained SMX-006 and SMX-016 validators/harnesses continue to run in the dedicated SMX-027 workflow alongside SMX-026 regressions.

## 7. Protected media

SMX-027 does not grant a capability adapter permission to rewrite canonical media meaning. The protected revision rule remains unchanged: a stable `AssetId` selects one indivisible immutable revision containing **source digest + source identity + source metadata + audio/media semantics + provenance + licence/attribution + derivation lineage**.

Capability grants, service calls, signatures, package provenance, target adapters and host results are authority/runtime context. They do not become fields of that protected revision, cannot mint a replacement revision, and cannot field-mix competing revisions. Any future media-related host service must still preserve the complete revision boundary and pass the later physical decoder/process gates.

## 8. Residual physical security

This issue proves the semantic broker/service boundary in production Python code; it is **not end-to-end sandbox certification**. The following remain deliberately downstream:

- production package signature/key/revocation trust machinery;
- archive/path/container physical hardening and real media decoder/process isolation;
- actual browser/native/headless origin/process isolation and hardened Godot build policy;
- platform-specific permission adapters and cancellation of already-active host resources;
- calibrated CPU/GPU/audio/network/memory hostile budgets;
- package acquisition/dependency trust and distribution policy;
- production runtime authentication/network transport security.

Those remain owned by SMX-039–041 and later runtime/package/network work. No residual item permits weakening principal attribution, denial-by-default, monotonic delegation, recursive authority rejection or final-use authorization.
