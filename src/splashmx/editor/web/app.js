let state = null;

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));
const status = $("#status");

function say(message, isError = false) {
  status.textContent = message;
  status.dataset.error = isError ? "true" : "false";
}

async function readJson(response) {
  const payload = await response.json();
  if (!response.ok || !payload.ok) {
    const error = payload.error || {};
    throw new Error(error.message || "That change could not be applied.");
  }
  return payload;
}

async function refresh() {
  const payload = await readJson(await fetch("/api/state", { cache: "no-store" }));
  state = payload.state;
  render();
}

async function act(action, data = {}) {
  try {
    const payload = await readJson(await fetch("/api/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, data }),
    }));
    state = payload.state;
    render();
    say("Change applied.");
    return payload;
  } catch (error) {
    say(error.message, true);
    throw error;
  }
}

function selectedIds() {
  return state ? state.editor.selection : [];
}

function selectedOne() {
  const selected = selectedIds();
  if (selected.length !== 1) {
    throw new Error("Select exactly one Thing for this action.");
  }
  return selected[0];
}

function renderStage() {
  const stage = $("#stage");
  stage.replaceChildren();
  const selected = new Set(selectedIds());
  const byId = new Map(state.canonical.things.map((thing) => [thing.thing_id, thing]));
  const childIds = new Set(state.canonical.things.filter((thing) => thing.parent_thing_id).map((thing) => thing.thing_id));

  function card(thing, depth = 0) {
    const wrapper = document.createElement("div");
    wrapper.className = "thing";
    wrapper.dataset.thingId = thing.thing_id;
    wrapper.style.setProperty("--depth", depth);

    const label = document.createElement("label");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = selected.has(thing.thing_id);
    checkbox.dataset.testid = `select-${thing.thing_id}`;
    checkbox.addEventListener("change", async () => {
      const next = new Set(selectedIds());
      checkbox.checked ? next.add(thing.thing_id) : next.delete(thing.thing_id);
      await act("select", { thing_ids: Array.from(next) });
    });
    const title = document.createElement("span");
    title.className = "thing-title";
    title.textContent = thing.label;
    const id = document.createElement("span");
    id.className = "thing-id";
    id.textContent = thing.thing_id;
    label.append(checkbox, title, id);
    wrapper.append(label);

    const ports = document.createElement("div");
    ports.className = "ports";
    ports.textContent = thing.ports.length
      ? thing.ports.map((port) => `${port.name} · ${port.kind}/${port.direction}`).join("  |  ")
      : "No ports";
    wrapper.append(ports);

    for (const child of state.canonical.things.filter((candidate) => candidate.parent_thing_id === thing.thing_id)) {
      wrapper.append(card(child, depth + 1));
    }
    return wrapper;
  }

  for (const thing of state.canonical.things) {
    if (!childIds.has(thing.thing_id) && byId.has(thing.thing_id)) {
      stage.append(card(thing));
    }
  }
  if (!state.canonical.things.length) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "The Stage is empty. Add a Thing to begin.";
    stage.append(empty);
  }
}

function renderThingSelects() {
  for (const select of $$('[data-role="thing-select"]')) {
    const previous = select.value;
    select.replaceChildren();
    for (const thing of state.canonical.things) {
      const option = document.createElement("option");
      option.value = thing.thing_id;
      option.textContent = thing.label;
      select.append(option);
    }
    if (state.canonical.things.some((thing) => thing.thing_id === previous)) select.value = previous;
  }
}

function renderInspect() {
  const panel = $("#inspect");
  panel.hidden = !state.editor.inspect_open;
  if (panel.hidden) return;
  const chosen = new Set(selectedIds());
  const detail = {
    selection: state.canonical.things.filter((thing) => chosen.has(thing.thing_id)),
    definitions: state.canonical.definitions,
    connections: state.canonical.connections,
    assets: state.canonical.assets,
  };
  $("#inspect-data").textContent = JSON.stringify(detail, null, 2);
}

function render() {
  if (!state) return;
  $("#revision").textContent = `Revision ${state.canonical.project_revision_id}`;
  $("#inspect-toggle").setAttribute("aria-pressed", state.editor.inspect_open ? "true" : "false");
  renderStage();
  renderThingSelects();
  renderInspect();
}

$("#create-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = new FormData(event.currentTarget);
  await act("createThing", { label: data.get("label") || "Thing" });
});

$("#group-selected").addEventListener("click", async () => {
  if (!selectedIds().length) return say("Select one or more Things to group.", true);
  await act("group", { members: selectedIds(), label: "Group" });
});

$("#make-reusable").addEventListener("click", async () => {
  try {
    await act("makeReusable", { root_id: selectedOne() });
  } catch (error) {
    if (!error.message.includes("Select exactly")) throw error;
    say(error.message, true);
  }
});

$("#add-rule").addEventListener("click", async () => {
  try {
    await act("attachRule", { thing_id: selectedOne(), event: "activate", actions: [{ action: "emit", event: "activated", payload: true }] });
  } catch (error) {
    if (!error.message.includes("Select exactly")) throw error;
    say(error.message, true);
  }
});

$("#add-behaviour").addEventListener("click", async () => {
  try {
    await act("attachBehaviour", { thing_id: selectedOne(), event: "activate", actions: [{ action: "emit", event: "activated", payload: true }] });
  } catch (error) {
    if (!error.message.includes("Select exactly")) throw error;
    say(error.message, true);
  }
});

$("#port-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const form = new FormData(event.currentTarget);
    await act("addPort", {
      thing_id: selectedOne(),
      port_id: form.get("port_id"),
      name: form.get("name"),
      kind: form.get("kind"),
      direction: form.get("direction"),
    });
  } catch (error) {
    if (!error.message.includes("Select exactly")) throw error;
    say(error.message, true);
  }
});

$("#connection-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  await act("connect", {
    source_thing_id: form.get("source_thing_id"),
    source_port_id: form.get("source_port_id"),
    target_thing_id: form.get("target_thing_id"),
    target_port_id: form.get("target_port_id"),
  });
});

$("#timeline-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const form = new FormData(event.currentTarget);
    await act("timeline", {
      thing_id: selectedOne(),
      property: form.get("property"),
      keyframes: [
        { tick: 0, value: Number(form.get("start")) },
        { tick: 60, value: Number(form.get("end")) },
      ],
    });
  } catch (error) {
    if (!error.message.includes("Select exactly")) throw error;
    say(error.message, true);
  }
});

$("#inspect-toggle").addEventListener("click", async () => {
  await act("inspect", { open: !state.editor.inspect_open });
});

$("#import-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const file = form.get("file");
  if (!(file instanceof File) || !file.size) return say("Choose a non-empty source file to import.", true);
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  await act("importAsset", {
    content_base64: btoa(binary),
    source_name: file.name,
    media_type: file.type || String(form.get("media_kind")),
    media_semantics: { kind: String(form.get("media_kind")) },
    provenance: { origin: String(form.get("provenance")) },
    licence_attribution: { licence: String(form.get("licence")), attribution: "author supplied" },
    derivation_lineage: [{ operation: "source", parent: null }],
    label: file.name,
  });
});

window.splashmxState = () => structuredClone(state);
refresh().catch((error) => say(error.message, true));
