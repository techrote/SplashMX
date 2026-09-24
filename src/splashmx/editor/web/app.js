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
const DEFAULT_RULE_FILL = "#ff5a5f";
const TIMELINE_LABELS = {
  "visual.x": "Horizontal position",
  "visual.y": "Vertical position",
  "visual.rotation": "Rotation",
  "visual.width": "Width",
  "visual.height": "Height",
};
let timelinePreviewTick = null;
let timelinePreviewFrame = null;
const TIMELINE_PREVIEW_MS = 1200;

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

function timelineTracksFor(thing) {
  const rows = thing?.authored_state?.timeline_tracks;
  return Array.isArray(rows) ? rows : [];
}
function rulesFor(thing) {
  const rows = Array.isArray(thing?.behaviours) ? thing.behaviours : [];
  return rows.filter((row) => row?.authored_config?.projection === "Rule");
}
function beginnerRuleFill(rule) {
  const actions = Array.isArray(rule?.authored_config?.actions) ? rule.authored_config.actions : [];
  const action = actions.find((row) => row?.action === "set_public" && row?.key === "visual");
  const fill = action?.value?.fill;
  return typeof fill === "string" && /^#[0-9a-fA-F]{6}$/.test(fill) ? fill.toLowerCase() : DEFAULT_RULE_FILL;
}
function timelineValueAt(track, tick) {
  const keyframes = Array.isArray(track?.keyframes)
    ? track.keyframes.filter((row) => Number.isFinite(Number(row.tick)) && Number.isFinite(Number(row.value))).map((row) => ({ tick: Number(row.tick), value: Number(row.value) })).sort((a, b) => a.tick - b.tick)
    : [];
  if (!keyframes.length) return null;
  if (tick <= keyframes[0].tick) return keyframes[0].value;
  if (tick >= keyframes[keyframes.length - 1].tick) return keyframes[keyframes.length - 1].value;
  for (let index = 1; index < keyframes.length; index += 1) {
    const right = keyframes[index];
    const left = keyframes[index - 1];
    if (tick <= right.tick) {
      if (right.tick === left.tick) return right.value;
      const ratio = (tick - left.tick) / (right.tick - left.tick);
      return left.value + (right.value - left.value) * ratio;
    }
  }
  return keyframes[keyframes.length - 1].value;
}
function displayVisualFor(thing, index = 0) {
  const visual = { ...visualFor(thing, index) };
  if (timelinePreviewTick === null) return visual;
  for (const track of timelineTracksFor(thing)) {
    const property = String(track.property || "");
    if (!property.startsWith("visual.")) continue;
    const key = property.slice("visual.".length);
    if (!(key in visual) || typeof visual[key] !== "number") continue;
    const value = timelineValueAt(track, timelinePreviewTick);
    if (value !== null) visual[key] = value;
  }
  return visual;
}
function timelineMaxTick() {
  let maximum = 60;
  for (const thing of state?.canonical?.things || []) {
    for (const track of timelineTracksFor(thing)) {
      for (const keyframe of track.keyframes || []) {
        const tick = Number(keyframe.tick);
        if (Number.isFinite(tick)) maximum = Math.max(maximum, tick);
      }
    }
  }
  return maximum;
}
function cancelTimelinePreview({ restore = true } = {}) {
  if (timelinePreviewFrame !== null) cancelAnimationFrame(timelinePreviewFrame);
  timelinePreviewFrame = null;
  if (restore) timelinePreviewTick = null;
}
function applyTimelinePlayhead(tick) {
  timelinePreviewTick = Number(tick);
  renderStage();
  const scrubber = $("#timeline-scrubber");
  const output = $("#timeline-tick");
  if (scrubber) scrubber.value = String(Math.round(timelinePreviewTick));
  if (output) output.textContent = `Tick ${Math.round(timelinePreviewTick)}`;
}
function startTimelinePreview() {
  cancelTimelinePreview({ restore: false });
  const maximum = timelineMaxTick();
  const started = performance.now();
  const frame = (now) => {
    const progress = Math.min(1, (now - started) / TIMELINE_PREVIEW_MS);
    applyTimelinePlayhead(maximum * progress);
    if (progress < 1) {
      timelinePreviewFrame = requestAnimationFrame(frame);
      return;
    }
    timelinePreviewFrame = null;
    timelinePreviewTick = null;
    renderStage();
    $("#timeline-scrubber").value = "0";
    $("#timeline-tick").textContent = "Base";
    say("Timeline preview finished. Back to authored state.");
  };
  timelinePreviewFrame = requestAnimationFrame(frame);
  say("Previewing authored Timeline keyframes.");
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
    const visual = displayVisualFor(thing, index);
    const node = document.createElement("div");
    node.className = "visual-thing" + (selected.has(thing.thing_id) ? " is-selected" : "");
    node.dataset.thingId = thing.thing_id;
    node.dataset.shape = visual.shape;
    node.dataset.testid = `stage-thing-${thing.thing_id}`;
    node.tabIndex = 0;
    node.setAttribute("role", "button");
    const thingRules = rulesFor(thing);
    node.setAttribute("aria-label", `${thing.label}. Position ${Math.round(visual.x)}, ${Math.round(visual.y)}. Size ${Math.round(visual.width)} by ${Math.round(visual.height)}.${thingRules.length ? " Has Rule." : ""}`);
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

    node.append(checkbox, label);
    if (thingRules.length) {
      const badge = document.createElement("span");
      badge.className = "rule-badge";
      badge.dataset.testid = `rule-badge-${thing.thing_id}`;
      badge.textContent = "Rule";
      node.append(badge);
    }
    node.append(resize);
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

function renderRules() {
  const form = $("#rule-form");
  const fields = $("#rule-fields");
  const empty = $("#rules-empty");
  const list = $("#rules-list");
  list.replaceChildren();

  if (selectedIds().length !== 1) {
    form.hidden = true;
    fields.disabled = true;
    form.elements.attachment_id.value = "";
    empty.hidden = false;
    empty.textContent = selectedIds().length ? "Select exactly one Thing to edit its Rules." : "Select one visual Thing to add or edit a Rule.";
    return;
  }

  const thing = thingById(selectedIds()[0]);
  if (!thing) {
    form.hidden = true;
    fields.disabled = true;
    empty.hidden = false;
    return;
  }

  const rules = rulesFor(thing);
  const editingId = String(form.elements.attachment_id.value || "");
  if (editingId && !rules.some((row) => row.attachment_id === editingId)) {
    form.elements.attachment_id.value = "";
  }
  form.hidden = false;
  fields.disabled = false;
  empty.hidden = true;
  $("#rules-selection").textContent = thing.label;

  if (!form.contains(document.activeElement) && !form.elements.attachment_id.value) {
    form.elements.event.value = "pointer_click";
    form.elements.action.value = "change_colour";
    form.elements.fill.value = DEFAULT_RULE_FILL;
  }

  if (!rules.length) {
    const message = document.createElement("p");
    message.className = "muted";
    message.textContent = `${thing.label} has no Rules yet.`;
    list.append(message);
    return;
  }

  for (const rule of rules) {
    const card = document.createElement("article");
    card.className = "rule-card";
    card.dataset.testid = "rule-card";
    const text = document.createElement("div");
    const title = document.createElement("strong");
    const supported = rule.authored_config?.author_kind === "visual-fill" && rule.authored_config?.event === "pointer_click";
    const fill = beginnerRuleFill(rule);
    title.textContent = supported ? "When this Thing is clicked → change its colour" : "Advanced Rule";
    const detail = document.createElement("span");
    detail.className = "rule-detail";
    detail.textContent = supported ? fill : "Open Inspect for advanced details.";
    text.append(title, detail);

    const controls = document.createElement("div");
    controls.className = "toolbar";
    const edit = document.createElement("button");
    edit.type = "button";
    edit.dataset.testid = `edit-rule-${rule.attachment_id}`;
    edit.textContent = "Edit";
    edit.disabled = !supported;
    edit.addEventListener("click", () => {
      form.elements.attachment_id.value = rule.attachment_id;
      form.elements.event.value = "pointer_click";
      form.elements.action.value = "change_colour";
      form.elements.fill.value = fill;
      form.elements.fill.focus();
      say("Editing Rule.");
    });
    const remove = document.createElement("button");
    remove.type = "button";
    remove.dataset.testid = `delete-rule-${rule.attachment_id}`;
    remove.textContent = "Delete";
    remove.addEventListener("click", async () => {
      await act("removeRule", { thing_id: thing.thing_id, attachment_id: rule.attachment_id }, "Rule deleted.");
    });
    controls.append(edit, remove);
    card.append(text, controls);
    list.append(card);
  }
}

function renderTimeline() {
  const tracksRoot = $("#timeline-tracks");
  const fields = $("#timeline-fields");
  const scrubber = $("#timeline-scrubber");
  const output = $("#timeline-tick");
  const maximum = timelineMaxTick();
  scrubber.max = String(maximum);
  if (timelinePreviewTick === null) {
    scrubber.value = "0";
    output.textContent = "Base";
  } else {
    const clamped = Math.max(0, Math.min(maximum, timelinePreviewTick));
    timelinePreviewTick = clamped;
    scrubber.value = String(Math.round(clamped));
    output.textContent = `Tick ${Math.round(clamped)}`;
  }

  tracksRoot.replaceChildren();
  fields.disabled = selectedIds().length !== 1;
  if (selectedIds().length !== 1) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = selectedIds().length ? "Select exactly one Thing to author an animation." : "Select a Thing to author an animation.";
    tracksRoot.append(empty);
    return;
  }

  const thing = thingById(selectedIds()[0]);
  const tracks = timelineTracksFor(thing);
  const form = $("#timeline-form");
  if (thing && !form.contains(document.activeElement)) {
    const property = String(form.elements.property.value || "visual.x");
    const key = property.replace(/^visual\./, "");
    const index = state.canonical.things.findIndex((row) => row.thing_id === thing.thing_id);
    const base = visualFor(thing, Math.max(index, 0));
    if (typeof base[key] === "number") {
      form.elements.start.value = String(Math.round(base[key] * 100) / 100);
      form.elements.end.value = String(Math.round((base[key] + (key === "rotation" ? 90 : 100)) * 100) / 100);
    }
  }

  if (!tracks.length) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = `${thing.label} has no animation tracks yet.`;
    tracksRoot.append(empty);
    return;
  }

  for (const track of tracks) {
    const row = document.createElement("article");
    row.className = "timeline-track";
    row.dataset.testid = "timeline-track";
    const info = document.createElement("div");
    const property = String(track.property || "");
    const keyframes = Array.isArray(track.keyframes) ? track.keyframes : [];
    const first = keyframes[0];
    const last = keyframes[keyframes.length - 1];
    const title = document.createElement("strong");
    title.textContent = TIMELINE_LABELS[property] || "Animation";
    const values = document.createElement("div");
    values.className = "timeline-track-values";
    values.textContent = first && last ? `${first.value} → ${last.value} · ${last.tick} ticks` : "No keyframes";
    info.append(title, values);

    const line = document.createElement("div");
    line.className = "timeline-track-line";
    line.setAttribute("aria-label", `${title.textContent} keyframes`);
    for (const keyframe of keyframes) {
      const tick = Number(keyframe.tick);
      if (!Number.isFinite(tick)) continue;
      const marker = document.createElement("span");
      marker.className = "timeline-keyframe";
      marker.style.left = `${maximum ? Math.max(0, Math.min(100, tick / maximum * 100)) : 0}%`;
      marker.title = `Tick ${tick}: ${keyframe.value}`;
      line.append(marker);
    }
    row.append(info, line);
    tracksRoot.append(row);
  }
}

function renderGodotPlayer(playing) {
  const stagePanel = $("#stage-panel");
  const runtimePanel = $("#runtime-panel");
  const frame = $("#godot-player");
  const playerStatus = $("#godot-player-status");
  const available = Boolean(state?.godot_player?.available);

  if (!playing) {
    stagePanel.hidden = false;
    runtimePanel.hidden = true;
    frame.hidden = true;
    if (frame.dataset.revision) {
      frame.src = "about:blank";
      delete frame.dataset.revision;
    }
    playerStatus.textContent = available ? "Godot runtime ready." : "Godot Play runtime is not installed for this editor.";
    return;
  }

  stagePanel.hidden = true;
  runtimePanel.hidden = false;
  if (!available) {
    frame.hidden = true;
    playerStatus.textContent = "Godot Play runtime unavailable. Stop Play and install a qualified runtime.";
    return;
  }

  const revision = String(state.canonical.project_revision_id);
  const desired = `${state.godot_player.url}&revision=${encodeURIComponent(revision)}`;
  frame.hidden = false;
  if (frame.dataset.revision !== revision) {
    frame.dataset.revision = revision;
    frame.src = desired;
    playerStatus.textContent = `Starting ${state.godot_player.runtime} for revision ${revision}…`;
  }
}

async function startPlay() {
  cancelTimelinePreview();
  if (!state?.godot_player?.available) {
    say("Godot Play runtime is not available. Supply the qualified Godot Web runtime before Play.", true);
    return false;
  }
  await act("play", {}, "Playing through the Godot runtime.");
  return true;
}
async function stopPlay() {
  await act("stop", {}, "Stopped. Authored project is unchanged.");
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
function render() { if (!state) return; $("#revision").textContent = `Revision ${state.canonical.project_revision_id}`; const playing = state.runtime && state.runtime.mode === "play"; $("#mode").textContent = playing ? "Play mode · Godot" : "Edit mode"; $("#play").disabled = playing; $("#stop").disabled = !playing; $("#inspect-toggle").setAttribute("aria-pressed", state.editor.inspect_open ? "true" : "false"); renderStage(); renderProperties(); renderRules(); renderTimeline(); renderGodotPlayer(playing); renderThingSelects(); renderInspect(); renderPeople(); }

$("#create-form").addEventListener("submit", async (event) => { event.preventDefault(); const data = new FormData(event.currentTarget); const index = state?.canonical.things.length || 0; const visual = { ...VISUAL_DEFAULTS, x: 64 + (index % 4) * 190, y: 64 + Math.floor(index / 4) * 130, shape: String(data.get("shape") || "rectangle") }; const payload = await act("createThing", { label: data.get("label") || "Thing", authored_state: { visual } }, "Added a visible Thing to the Stage."); if (payload.result) await act("select", { thing_ids: [payload.result] }, "Thing created and selected."); });
$("#visual-properties").addEventListener("submit", async (event) => { event.preventDefault(); try { const thingId = selectedOne(); const form = new FormData(event.currentTarget); await commitVisual(thingId, { x: Number(form.get("x")), y: Number(form.get("y")), width: Number(form.get("width")), height: Number(form.get("height")), rotation: Number(form.get("rotation")), shape: String(form.get("shape")), fill: String(form.get("fill")) }, "Visual properties applied."); } catch (error) { if (!error.message.includes("Select exactly")) throw error; say(error.message, true); } });
$("#group-selected").addEventListener("click", async () => { if (!selectedIds().length) return say("Select one or more Things to group.", true); await act("group", { members: selectedIds(), label: "Group" }); });
$("#make-reusable").addEventListener("click", async () => { try { await act("makeReusable", { root_id: selectedOne() }); } catch (error) { if (!error.message.includes("Select exactly")) throw error; say(error.message, true); } });
$("#add-rule").addEventListener("click", async () => { try { await act("attachVisualRule", { thing_id: selectedOne(), fill: DEFAULT_RULE_FILL }, "Rule added: when this Thing is clicked, change its colour."); } catch (error) { if (!error.message.includes("Select exactly") && error.code !== "authoring.rule_exists") throw error; say(error.message, true); } });
$("#add-behaviour").addEventListener("click", async () => { try { await act("attachBehaviour", { thing_id: selectedOne(), event: "activate", actions: [{ action: "emit", event: "activated", payload: true }] }); } catch (error) { if (!error.message.includes("Select exactly")) throw error; say(error.message, true); } });
$("#rule-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const thingId = selectedOne();
    const form = new FormData(event.currentTarget);
    if (String(form.get("event")) !== "pointer_click" || String(form.get("action")) !== "change_colour") {
      return say("Choose a supported Rule event and action.", true);
    }
    const attachmentId = String(form.get("attachment_id") || "");
    const data = { thing_id: thingId, fill: String(form.get("fill") || DEFAULT_RULE_FILL) };
    if (attachmentId) {
      data.attachment_id = attachmentId;
      await act("updateVisualRule", data, "Rule updated.");
    } else {
      await act("attachVisualRule", data, "Rule added.");
    }
    event.currentTarget.elements.attachment_id.value = "";
  } catch (error) {
    if (!error.message.includes("Select exactly") && error.code !== "authoring.rule_exists") throw error;
    say(error.message, true);
  }
});
$("#cancel-rule-edit").addEventListener("click", () => {
  const form = $("#rule-form");
  form.elements.attachment_id.value = "";
  form.elements.fill.value = DEFAULT_RULE_FILL;
  say("Rule edit cancelled.");
  renderRules();
});
$("#port-form").addEventListener("submit", async (event) => { event.preventDefault(); try { const form = new FormData(event.currentTarget); await act("addPort", { thing_id: selectedOne(), port_id: form.get("port_id"), name: form.get("name"), kind: form.get("kind"), direction: form.get("direction") }); } catch (error) { if (!error.message.includes("Select exactly")) throw error; say(error.message, true); } });
$("#connection-form").addEventListener("submit", async (event) => { event.preventDefault(); const form = new FormData(event.currentTarget); await act("connect", { source_thing_id: form.get("source_thing_id"), source_port_id: form.get("source_port_id"), target_thing_id: form.get("target_thing_id"), target_port_id: form.get("target_port_id"), connection_id: form.get("connection_id") || undefined }); });
$("#timeline-form").addEventListener("submit", async (event) => { event.preventDefault(); try { cancelTimelinePreview(); const form = new FormData(event.currentTarget); const duration = Math.max(1, Math.min(3600, Number(form.get("duration")) || 60)); await act("timeline", { thing_id: selectedOne(), property: String(form.get("property")), keyframes: [{ tick: 0, value: Number(form.get("start")) }, { tick: duration, value: Number(form.get("end")) }] }, "Animation track added to the Timeline."); } catch (error) { if (!error.message.includes("Select exactly")) throw error; say(error.message, true); } });
$("#timeline-form select[name=\"property\"]").addEventListener("change", () => renderTimeline());
$("#timeline-scrubber").addEventListener("input", (event) => { cancelTimelinePreview({ restore: false }); applyTimelinePlayhead(Number(event.currentTarget.value)); });
$("#timeline-preview").addEventListener("click", () => { if (!(state?.canonical?.things || []).some((thing) => timelineTracksFor(thing).length)) return say("Add an animation track before previewing.", true); startTimelinePreview(); });
$("#timeline-reset").addEventListener("click", () => { cancelTimelinePreview(); renderStage(); $("#timeline-scrubber").value = "0"; $("#timeline-tick").textContent = "Base"; say("Timeline preview reset to authored state."); });
$("#inspect-toggle").addEventListener("click", async () => { await act("inspect", { open: !state.editor.inspect_open }, state.editor.inspect_open ? "Inspect closed." : "Inspect opened."); });
$("#clear-diagnostics").addEventListener("click", async () => { await act("clearDiagnostics", {}, "Diagnostics cleared."); });
$("#play").addEventListener("click", startPlay);
$("#stop").addEventListener("click", stopPlay);
$("#godot-player").addEventListener("load", () => { if (state?.runtime?.mode === "play" && state?.godot_player?.available) $("#godot-player-status").textContent = "Godot runtime loaded. Running the active canonical revision."; });
$("#save").addEventListener("click", async () => { await act("save", {}, "Saved locally."); });
$("#reload").addEventListener("click", async () => { await act("reload", {}, "Reloaded the verified local project."); });
$("#presence-form").addEventListener("submit", async (event) => { event.preventDefault(); const form = new FormData(event.currentTarget); await act("peoplePresence", { cursor: String(form.get("cursor") || ""), selections: selectedIds() }, "Presence updated without changing authored state."); });
$("#people-retry-local").addEventListener("click", async () => { await act("peopleRetryLocal", {}, "Local collaboration history retry completed."); });
$("#import-form").addEventListener("submit", async (event) => { event.preventDefault(); const form = new FormData(event.currentTarget); const file = form.get("file"); if (!(file instanceof File) || !file.size) return say("Choose a non-empty source file to import.", true); const bytes = new Uint8Array(await file.arrayBuffer()); let binary = ""; for (const byte of bytes) binary += String.fromCharCode(byte); await act("importAsset", { content_base64: btoa(binary), source_name: file.name, media_type: file.type || String(form.get("media_kind")), media_semantics: { kind: String(form.get("media_kind")) }, provenance: { origin: String(form.get("provenance")) }, licence_attribution: { licence: String(form.get("licence")), attribution: "author supplied" }, derivation_lineage: [{ operation: "source", parent: null }], label: file.name }); });
document.addEventListener("keydown", async (event) => { if ((event.ctrlKey || event.metaKey) && event.key === "Enter") { event.preventDefault(); if (!state.runtime || state.runtime.mode !== "play") await startPlay(); } else if (event.key === "Escape" && state.runtime && state.runtime.mode === "play") { event.preventDefault(); await stopPlay(); } else if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") { event.preventDefault(); await act("save", {}, "Saved locally."); } else if (event.altKey && event.key.toLowerCase() === "i") { event.preventDefault(); await act("inspect", { open: !state.editor.inspect_open }, "Inspect toggled."); } });
window.splashmxState = () => structuredClone(state); window.splashmxAct = (action, data = {}) => act(action, data); refresh().catch((error) => say(error.message, true));
