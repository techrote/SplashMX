let state = null;
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));
const status = $("#status");
function say(message, isError = false) { status.textContent = message; status.dataset.error = isError ? "true" : "false"; }
async function readJson(response) { const payload = await response.json(); if (!response.ok || !payload.ok) { const error = payload.error || {}; if (payload.state) { state = payload.state; render(); } const failure = new Error(error.message || "That change could not be applied."); failure.code = error.code || "browser.action_failed"; throw failure; } return payload; }
async function refresh() { const payload = await readJson(await fetch("/api/state", { cache: "no-store" })); state = payload.state; render(); }
async function act(action, data = {}, success = "Change applied.") { try { const payload = await readJson(await fetch("/api/action", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action, data }) })); state = payload.state; render(); say(success); return payload; } catch (error) { say(error.message, true); throw error; } }
function selectedIds() { return state ? state.editor.selection : []; }
function selectedOne() { const selected = selectedIds(); if (selected.length !== 1) throw new Error("Select exactly one Thing for this action."); return selected[0]; }

const VISUAL_DEFAULTS = { x: 64, y: 64, width: 160, height: 100, rotation: 0, shape: "rectangle", fill: "#5b7cfa" };
function thingById(thingId) { return state?.canonical.things.find((thing) => thing.thing_id === thingId) || null; }
function visualFor(thing, index = 0) {
  const fallback = { ...VISUAL_DEFAULTS, x: 64 + (index % 4) * 190, y: 64 + Math.floor(index / 4) * 130 };
  return { ...fallback, ...(thing?.authored_state?.visual || {}) };
}
async function commitVisual(thingId, patch, success = "Visual properties updated.") {
  const thing = thingById(thingId);
  if (!thing) throw new Error("That Thing is no longer available.");
  const index = state.canonical.things.findIndex((row) => row.thing_id === thingId);
  const visual = { ...visualFor(thing, Math.max(0, index)), ...patch };
  return act("updateVisual", { thing_id: thingId, visual }, success);
}

function renderStage() {
  const stage = $("#stage");
  stage.replaceChildren();
  const selected = new Set(selectedIds());

  function installMove(node, thing, visual) {
    node.addEventListener("pointerdown", (event) => {
      if (event.button !== 0 || event.target.closest("input, .resize-handle")) return;
      event.preventDefault();
      const pointerId = event.pointerId;
      const startX = event.clientX;
      const startY = event.clientY;
      const originalX = Number(visual.x);
      const originalY = Number(visual.y);
      let nextX = originalX;
      let nextY = originalY;
      node.setPointerCapture(pointerId);
      const move = (moveEvent) => {
        if (moveEvent.pointerId !== pointerId) return;
        nextX = Math.round(originalX + moveEvent.clientX - startX);
        nextY = Math.round(originalY + moveEvent.clientY - startY);
        node.style.left = `${nextX}px`;
        node.style.top = `${nextY}px`;
      };
      const finish = async (upEvent) => {
        if (upEvent.pointerId !== pointerId) return;
        node.removeEventListener("pointermove", move);
        node.removeEventListener("pointerup", finish);
        node.removeEventListener("pointercancel", finish);
        if (node.hasPointerCapture(pointerId)) node.releasePointerCapture(pointerId);
        try { await commitVisual(thing.thing_id, { x: nextX, y: nextY }, `Moved ${thing.label}.`); }
        catch (error) { render(); say(error.message, true); }
      };
      node.addEventListener("pointermove", move);
      node.addEventListener("pointerup", finish);
      node.addEventListener("pointercancel", finish);
    });
  }

  function installResize(handle, node, thing, visual) {
    handle.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      event.preventDefault();
      event.stopPropagation();
      const pointerId = event.pointerId;
      const startX = event.clientX;
      const startY = event.clientY;
      const originalWidth = Number(visual.width);
      const originalHeight = Number(visual.height);
      let width = originalWidth;
      let height = originalHeight;
      handle.setPointerCapture(pointerId);
      const move = (moveEvent) => {
        if (moveEvent.pointerId !== pointerId) return;
        width = Math.max(12, Math.round(originalWidth + moveEvent.clientX - startX));
        height = Math.max(12, Math.round(originalHeight + moveEvent.clientY - startY));
        node.style.width = `${width}px`;
        node.style.height = `${height}px`;
      };
      const finish = async (upEvent) => {
        if (upEvent.pointerId !== pointerId) return;
        handle.removeEventListener("pointermove", move);
        handle.removeEventListener("pointerup", finish);
        handle.removeEventListener("pointercancel", finish);
        if (handle.hasPointerCapture(pointerId)) handle.releasePointerCapture(pointerId);
        try { await commitVisual(thing.thing_id, { width, height }, `Resized ${thing.label}.`); }
        catch (error) { render(); say(error.message, true); }
      };
      handle.addEventListener("pointermove", move);
      handle.addEventListener("pointerup", finish);
      handle.addEventListener("pointercancel", finish);
    });
  }

  state.canonical.things.forEach((thing, index) => {
    const visual = visualFor(thing, index);
    const node = document.createElement("div");
    node.className = "visual-thing" + (selected.has(thing.thing_id) ? " is-selected" : "");
    node.dataset.thingId = thing.thing_id;
    node.dataset.shape = visual.shape;
    node.dataset.testid = `stage-thing-${thing.thing_id}`;
    node.tabIndex = 0;
    node.setAttribute("role", "button");
    node.setAttribute("aria-label", `${thing.label}. Position ${Math.round(visual.x)}, ${Math.round(visual.y)}. Size ${Math.round(visual.width)} by ${Math.round(visual.height)}.`);
    node.style.left = `${visual.x}px`;
    node.style.top = `${visual.y}px`;
    node.style.width = `${visual.width}px`;
    node.style.height = `${visual.height}px`;
    node.style.background = visual.fill;
    node.style.transform = `rotate(${visual.rotation}deg)`;

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.className = "thing-select";
    checkbox.checked = selected.has(thing.thing_id);
    checkbox.dataset.testid = `select-${thing.thing_id}`;
    checkbox.setAttribute("aria-label", `Select ${thing.label}`);
    checkbox.addEventListener("change", async () => {
      const next = new Set(selectedIds());
      checkbox.checked ? next.add(thing.thing_id) : next.delete(thing.thing_id);
      await act("select", { thing_ids: Array.from(next) }, "Selection updated.");
    });

    const label = document.createElement("span");
    label.className = "visual-label";
    label.textContent = thing.label;

    const resize = document.createElement("span");
    resize.className = "resize-handle";
    resize.dataset.testid = `resize-${thing.thing_id}`;
    resize.setAttribute("role", "presentation");

    node.append(checkbox, label, resize);
    node.addEventListener("click", async (event) => {
      if (event.target.closest("input, .resize-handle")) return;
      await act("select", { thing_ids: [thing.thing_id] }, `Selected ${thing.label}.`);
    });
    node.addEventListener("keydown", async (event) => {
      if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Enter", " "].includes(event.key)) return;
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        await act("select", { thing_ids: [thing.thing_id] }, `Selected ${thing.label}.`);
        return;
      }
      event.preventDefault();
      const delta = event.altKey ? 1 : 5;
      const patch = {};
      if (event.shiftKey) {
        if (event.key === "ArrowLeft") patch.width = Math.max(12, Number(visual.width) - delta);
        if (event.key === "ArrowRight") patch.width = Number(visual.width) + delta;
        if (event.key === "ArrowUp") patch.height = Math.max(12, Number(visual.height) - delta);
        if (event.key === "ArrowDown") patch.height = Number(visual.height) + delta;
      } else {
        if (event.key === "ArrowLeft") patch.x = Number(visual.x) - delta;
        if (event.key === "ArrowRight") patch.x = Number(visual.x) + delta;
        if (event.key === "ArrowUp") patch.y = Number(visual.y) - delta;
        if (event.key === "ArrowDown") patch.y = Number(visual.y) + delta;
      }
      await commitVisual(thing.thing_id, patch, event.shiftKey ? `Resized ${thing.label}.` : `Moved ${thing.label}.`);
      if (!selectedIds().includes(thing.thing_id)) await act("select", { thing_ids: [thing.thing_id] }, `Selected ${thing.label}.`);
    });
    installMove(node, thing, visual);
    installResize(resize, node, thing, visual);
    stage.append(node);
  });

  if (!state.canonical.things.length) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "Your Stage is empty. Name a Thing and add it to start creating.";
    stage.append(empty);
  }
}

function renderProperties() {
  const form = $("#visual-properties");
  const empty = $("#properties-empty");
  if (selectedIds().length !== 1) {
    form.hidden = true;
    empty.hidden = false;
    empty.textContent = selectedIds().length ? "Select exactly one Thing to edit its visual properties." : "Select one visual Thing on the Stage.";
    return;
  }
  const thing = thingById(selectedIds()[0]);
  if (!thing) { form.hidden = true; empty.hidden = false; return; }
  const index = state.canonical.things.findIndex((row) => row.thing_id === thing.thing_id);
  const visual = visualFor(thing, Math.max(0, index));
  form.hidden = false;
  empty.hidden = true;
  $("#properties-selection").textContent = thing.label;
  for (const key of ["x", "y", "width", "height", "rotation", "shape", "fill"]) form.elements[key].value = visual[key];
}

function renderThingSelects() { for (const select of $$('[data-role="thing-select"]')) { const previous = select.value; select.replaceChildren(); for (const thing of state.canonical.things) { const option = document.createElement("option"); option.value = thing.thing_id; option.textContent = thing.label; select.append(option); } if (state.canonical.things.some((thing) => thing.thing_id === previous)) select.value = previous; } }
function renderInspect() { const panel = $("#inspect"); panel.hidden = !state.editor.inspect_open; if (panel.hidden) return; const chosen = new Set(selectedIds()); $("#inspect-data").textContent = JSON.stringify({ selection: state.canonical.things.filter((thing) => chosen.has(thing.thing_id)), definitions: state.canonical.definitions, connections: state.canonical.connections, assets: state.canonical.assets }, null, 2); const log = $("#diagnostics"); log.replaceChildren(); for (const diagnostic of state.diagnostics || []) { const article = document.createElement("article"); article.className = "diagnostic"; article.dataset.code = diagnostic.code; const heading = document.createElement("strong"); heading.textContent = diagnostic.title; const message = document.createElement("p"); message.textContent = diagnostic.message; article.append(heading, message); log.append(article); } if (!(state.diagnostics || []).length) log.textContent = "No diagnostics."; }
function renderPeople() {
  const people = state.people || { conflicts: [], presence: [] };
  const parts = [people.relay_online === false ? "Relay offline" : "Local-first collaboration ready"];
  if (people.unsynced_local_work) parts.push("local work waiting for history storage");
  if ((people.conflicts || []).length) parts.push(`${people.conflicts.length} unresolved conflict${people.conflicts.length === 1 ? "" : "s"}`);
  $("#people-status").textContent = parts.join(" · ");
  $("#people-retry-local").hidden = !people.unsynced_local_work;
  const presence = $("#people-presence"); presence.replaceChildren();
  for (const row of people.presence || []) { const item = document.createElement("p"); item.textContent = `${row.principal_id}${row.cursor ? ` — ${row.cursor}` : ""}`; presence.append(item); }
  if (!(people.presence || []).length) presence.textContent = "No transient presence is currently visible.";
  const conflicts = $("#people-conflicts"); conflicts.replaceChildren();
  for (const conflict of people.conflicts || []) {
    const article = document.createElement("article"); article.className = "diagnostic collaboration-conflict"; article.dataset.conflictId = conflict.conflict_id;
    const heading = document.createElement("strong"); heading.textContent = `${conflict.kind} · ${conflict.locus}`;
    const detail = document.createElement("pre"); detail.textContent = JSON.stringify({ conflict_id: conflict.conflict_id, alternatives: conflict.alternatives }, null, 2); article.append(heading, detail);
    const controls = document.createElement("div"); controls.className = "toolbar";
    for (const choice of conflict.choices || ["current"]) { const button = document.createElement("button"); button.type = "button"; button.dataset.testid = `people-resolve-${choice}`; button.textContent = choice === "current" ? "Keep current" : choice === "alternative-a" ? "Use alternative A" : "Use alternative B"; button.addEventListener("click", async () => { await act("peopleResolveConflict", { conflict_id: conflict.conflict_id, choice }, "Conflict resolved as a new collaboration transaction."); }); controls.append(button); }
    article.append(controls); conflicts.append(article);
  }
  if (!(people.conflicts || []).length) conflicts.textContent = "No unresolved semantic conflicts.";
}
function render() { if (!state) return; $("#revision").textContent = `Revision ${state.canonical.project_revision_id}`; const playing = state.runtime && state.runtime.mode === "play"; $("#mode").textContent = playing ? "Play mode" : "Edit mode"; $("#play").disabled = playing; $("#stop").disabled = !playing; $("#inspect-toggle").setAttribute("aria-pressed", state.editor.inspect_open ? "true" : "false"); renderStage(); renderProperties(); renderThingSelects(); renderInspect(); renderPeople(); }

$("#create-form").addEventListener("submit", async (event) => { event.preventDefault(); const data = new FormData(event.currentTarget); const index = state?.canonical.things.length || 0; const visual = { ...VISUAL_DEFAULTS, x: 64 + (index % 4) * 190, y: 64 + Math.floor(index / 4) * 130, shape: String(data.get("shape") || "rectangle") }; const payload = await act("createThing", { label: data.get("label") || "Thing", authored_state: { visual } }, "Added a visible Thing to the Stage."); if (payload.result) await act("select", { thing_ids: [payload.result] }, "Thing created and selected."); });
$("#visual-properties").addEventListener("submit", async (event) => { event.preventDefault(); try { const thingId = selectedOne(); const form = new FormData(event.currentTarget); await commitVisual(thingId, { x: Number(form.get("x")), y: Number(form.get("y")), width: Number(form.get("width")), height: Number(form.get("height")), rotation: Number(form.get("rotation")), shape: String(form.get("shape")), fill: String(form.get("fill")) }, "Visual properties applied."); } catch (error) { if (!error.message.includes("Select exactly")) throw error; say(error.message, true); } });
$("#group-selected").addEventListener("click", async () => { if (!selectedIds().length) return say("Select one or more Things to group.", true); await act("group", { members: selectedIds(), label: "Group" }); });
$("#make-reusable").addEventListener("click", async () => { try { await act("makeReusable", { root_id: selectedOne() }); } catch (error) { if (!error.message.includes("Select exactly")) throw error; say(error.message, true); } });
$("#add-rule").addEventListener("click", async () => { try { await act("attachRule", { thing_id: selectedOne(), event: "activate", actions: [{ action: "emit", event: "activated", payload: true }] }); } catch (error) { if (!error.message.includes("Select exactly")) throw error; say(error.message, true); } });
$("#add-behaviour").addEventListener("click", async () => { try { await act("attachBehaviour", { thing_id: selectedOne(), event: "activate", actions: [{ action: "emit", event: "activated", payload: true }] }); } catch (error) { if (!error.message.includes("Select exactly")) throw error; say(error.message, true); } });
$("#port-form").addEventListener("submit", async (event) => { event.preventDefault(); try { const form = new FormData(event.currentTarget); await act("addPort", { thing_id: selectedOne(), port_id: form.get("port_id"), name: form.get("name"), kind: form.get("kind"), direction: form.get("direction") }); } catch (error) { if (!error.message.includes("Select exactly")) throw error; say(error.message, true); } });
$("#connection-form").addEventListener("submit", async (event) => { event.preventDefault(); const form = new FormData(event.currentTarget); await act("connect", { source_thing_id: form.get("source_thing_id"), source_port_id: form.get("source_port_id"), target_thing_id: form.get("target_thing_id"), target_port_id: form.get("target_port_id"), connection_id: form.get("connection_id") || undefined }); });
$("#timeline-form").addEventListener("submit", async (event) => { event.preventDefault(); try { const form = new FormData(event.currentTarget); await act("timeline", { thing_id: selectedOne(), property: form.get("property"), keyframes: [{ tick: 0, value: Number(form.get("start")) }, { tick: 60, value: Number(form.get("end")) }] }); } catch (error) { if (!error.message.includes("Select exactly")) throw error; say(error.message, true); } });
$("#inspect-toggle").addEventListener("click", async () => { await act("inspect", { open: !state.editor.inspect_open }, state.editor.inspect_open ? "Inspect closed." : "Inspect opened."); });
$("#clear-diagnostics").addEventListener("click", async () => { await act("clearDiagnostics", {}, "Diagnostics cleared."); });
$("#play").addEventListener("click", async () => { await act("play", {}, "Playing transient runtime state."); });
$("#stop").addEventListener("click", async () => { await act("stop", {}, "Stopped. Authored project is unchanged."); });
$("#save").addEventListener("click", async () => { await act("save", {}, "Saved locally."); });
$("#reload").addEventListener("click", async () => { await act("reload", {}, "Reloaded the verified local project."); });
$("#presence-form").addEventListener("submit", async (event) => { event.preventDefault(); const form = new FormData(event.currentTarget); await act("peoplePresence", { cursor: String(form.get("cursor") || ""), selections: selectedIds() }, "Presence updated without changing authored state."); });
$("#people-retry-local").addEventListener("click", async () => { await act("peopleRetryLocal", {}, "Local collaboration history retry completed."); });
$("#import-form").addEventListener("submit", async (event) => { event.preventDefault(); const form = new FormData(event.currentTarget); const file = form.get("file"); if (!(file instanceof File) || !file.size) return say("Choose a non-empty source file to import.", true); const bytes = new Uint8Array(await file.arrayBuffer()); let binary = ""; for (const byte of bytes) binary += String.fromCharCode(byte); await act("importAsset", { content_base64: btoa(binary), source_name: file.name, media_type: file.type || String(form.get("media_kind")), media_semantics: { kind: String(form.get("media_kind")) }, provenance: { origin: String(form.get("provenance")) }, licence_attribution: { licence: String(form.get("licence")), attribution: "author supplied" }, derivation_lineage: [{ operation: "source", parent: null }], label: file.name }); });
document.addEventListener("keydown", async (event) => { if ((event.ctrlKey || event.metaKey) && event.key === "Enter") { event.preventDefault(); if (!state.runtime || state.runtime.mode !== "play") await act("play", {}, "Playing transient runtime state."); } else if (event.key === "Escape" && state.runtime && state.runtime.mode === "play") { event.preventDefault(); await act("stop", {}, "Stopped. Authored project is unchanged."); } else if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") { event.preventDefault(); await act("save", {}, "Saved locally."); } else if (event.altKey && event.key.toLowerCase() === "i") { event.preventDefault(); await act("inspect", { open: !state.editor.inspect_open }, "Inspect toggled."); } });
window.splashmxState = () => structuredClone(state); window.splashmxAct = (action, data = {}) => act(action, data); refresh().catch((error) => say(error.message, true));
