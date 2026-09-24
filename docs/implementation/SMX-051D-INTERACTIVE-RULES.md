# SMX-051D — Beginner Rules through the production Godot interaction path

**Parent:** SMX-051 / #76  
**Issue:** #117  
**Godot baseline:** 4.7.2  
**Architecture authority:** `docs/architecture/ARCHITECTURE-V1.md`

## Purpose

SMX-051D closes the next product failure identified by SMX-048: **Add Rule** previously created an attachment but gave the author no perceptible representation or visible interactive result.

The first bounded beginner workflow is:

**select a visible Thing → add/edit “When this Thing is clicked → change its colour” → Play → click the Thing in the exported Godot Web runtime → observe the colour change → Stop → return to unchanged authored state.**

This is deliberately narrow. It proves one useful event/action path end to end before widening the event/action vocabulary.

## One semantic Rule model

The beginner surface does not introduce another document or execution model.

A beginner visual Rule is a normal canonical `BehaviourAttachmentRecord` with:

- projection: `Rule`;
- event: `pointer_click`;
- author kind: `visual-fill`;
- action: the existing constrained-IR `set_public` operation targeting the Thing's transient runtime `visual` state.

`compile_rule()` remains the compiler and the SMX-026 IR remains the execution authority. There is no JavaScript, GDScript, eval, host-call or privileged fallback path for authored behaviour.

Editing replaces the canonical attachment record while retaining its stable `BehaviourAttachmentId` and publishing a new exact Behaviour revision. Deleting removes the attachment through a canonical semantic transaction.

## Author-facing Rules surface

The ordinary editor now projects those canonical attachments as a visible Rules panel.

For the current slice the author sees:

- **When:** “This Thing is clicked”
- **Then:** “Change its colour”
- a normal colour control;
- visible Rule cards;
- a Rule badge on Things that contain Rules;
- Edit and Delete controls.

No ThingId, BehaviourAttachmentId, property path or IR opcode is required in the ordinary workflow. Existing advanced Behaviour/diagnostic surfaces remain separate.

## Input and execution boundary

Godot owns physical input and rendering. SplashMX owns Rule semantics.

The editor-live Play projection declares the bounded supported event `pointer_click` for Things carrying the beginner visual Rule. The generic Godot target creates target-private `Area2D` / collision presentation alongside its existing `Node2D` / `Polygon2D` binding.

On a primary pointer activation:

1. Godot sends the stable ThingId plus `pointer_click` to the same-origin editor runtime endpoint.
2. The editor validates the event against the bounded supported vocabulary.
3. The active production `WorldRuntime` dispatches that trigger.
4. The existing constrained IR executes.
5. The editor projects only the resulting validated transient visual state back to Godot.
6. Godot applies that visual state to its private presentation binding.

Godot does **not** interpret Rule actions. The browser does **not** execute a shadow interaction model.

The returned runtime-update contract is:

`splashmx.editor-godot-runtime-update/1`

It contains only ProjectRevisionId, stable ThingId and validated author-visible visual state. The existing production target-value guard rejects transient engine/browser/process/transport identity recursively.

## Play-start semantics

Only the semantic `activate` trigger is dispatched automatically when Play begins.

Input triggers such as `pointer_click` remain dormant until the corresponding target input actually occurs. This prevents an authored click Rule from firing merely because the author pressed Play.

## Authored/runtime separation

The constrained runtime begins from the canonical authored Thing state, but `set_public` modifies only transient Play state.

For the SMX-051D workflow:

- clicking may change the Godot presentation;
- ProjectRevisionId does not advance;
- canonical authored visual state does not change;
- Save/Reload persists the Rule definition, not a transient click result;
- Stop discards the live world and returns to authored state.

## Evidence

Durable unit/boundary coverage verifies:

- beginner Rule compilation through the common IR;
- stable attachment identity across editing;
- canonical deletion;
- duplicate/invalid Rule rejection without partial publication;
- click Rules do not fire at Play start;
- explicit runtime dispatch changes transient state only;
- Save/Reload rebuilds the exact Rule program;
- the Play projection exposes only the supported interactive event;
- unsupported or unknown runtime events fail with typed outcomes.

The existing SMX-038 workflow is extended again rather than creating a separate Godot build. The exact exported Godot 4.7.2 Web runtime is served through the production editor and driven in pinned Chromium. The browser campaign authors, edits, saves/reloads, plays, physically clicks the Godot canvas, verifies the emitted interaction evidence and transient colour change, Stops, then deletes the Rule visibly.

## Scope boundary

SMX-051D does not implement:

- a general event/action catalogue;
- arbitrary user code;
- visual Connection authoring;
- reusable Library UI;
- final accessibility/localization/recovery qualification;
- final human acceptance testing.

Those remain later SMX-051 slices.

## Architecture impact

Architecture v1 is unchanged.

SplashMX remains authoritative for canonical Thing/Behaviour semantics and constrained execution. Godot remains a private target adapter for rendering and physical input. Stable ThingId crosses the boundary; Godot object identity does not.
