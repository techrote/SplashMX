#!/usr/bin/env node
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright";

const ROOT = process.cwd();
const OUT = path.join(ROOT, "artifacts", "smx051f-editor-godot-evidence.json");
const URL = process.env.SMX051F_URL || "http://127.0.0.1:8132/";

async function editorState(page) {
  return page.evaluate(() => window.splashmxState?.());
}

async function waitForState(page, predicate, label, timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const value = await editorState(page);
    if (value && predicate(value)) return value;
    await page.waitForTimeout(40);
  }
  throw new Error(`timeout waiting for ${label}`);
}

async function createVisualThing(page, label) {
  await page.locator("#new-label").fill(label);
  await page.locator("#new-shape").selectOption("rectangle");
  await page.getByTestId("create-thing").click();
  const state = await waitForState(
    page,
    (value) => value.canonical.things.some((thing) => thing.label === label)
      && value.editor.selection.length === 1
      && value.canonical.things.some(
        (thing) => thing.label === label && thing.thing_id === value.editor.selection[0],
      ),
    `${label} creation`,
  );
  return state.canonical.things.find((thing) => thing.label === label).thing_id;
}

async function setSelectedRuleColour(page, fill) {
  await page.getByTestId("add-rule").click();
  let state = await waitForState(
    page,
    (value) => {
      const selected = value.editor.selection[0];
      return value.canonical.things.find((thing) => thing.thing_id === selected)?.behaviours?.length === 1;
    },
    "Rule creation",
  );
  const selected = state.editor.selection[0];
  let rule = state.canonical.things.find((thing) => thing.thing_id === selected).behaviours[0];
  await page.getByTestId(`edit-rule-${rule.attachment_id}`).click();
  await page.locator('#rule-form select[name="event"]').selectOption("pointer_click");
  await page.locator('#rule-form select[name="action"]').selectOption("change_colour");
  await page.locator('#rule-form input[name="fill"]').fill(fill);
  await page.getByTestId("save-rule").click();
  state = await waitForState(
    page,
    (value) => value.canonical.things.find((thing) => thing.thing_id === selected)
      ?.behaviours?.[0]?.authored_config?.actions?.[0]?.value === fill,
    "Rule colour update",
  );
  rule = state.canonical.things.find((thing) => thing.thing_id === selected).behaviours[0];
  return rule.attachment_id;
}

await fs.mkdir(path.dirname(OUT), { recursive: true });
const browser = await chromium.launch({ headless: true });
const evidence = {
  schema: "splashmx.smx051f-editor-godot-evidence/1",
  issue: "SMX-051F",
  source_url: URL,
  checks: {},
  godot: { ready: null, interactions: [] },
};
const consoleLines = [];

try {
  evidence.browser = { product: await browser.version(), playwright: "1.55.0", headless: true };
  const page = await browser.newPage({ viewport: { width: 1360, height: 1000 } });
  page.on("console", (message) => {
    const text = message.text();
    consoleLines.push(text);
    if (text.startsWith("SMX051C_PLAY_READY=")) {
      evidence.godot.ready = JSON.parse(text.slice("SMX051C_PLAY_READY=".length));
    } else if (text.startsWith("SMX051D_INTERACTION=")) {
      evidence.godot.interactions.push(JSON.parse(text.slice("SMX051D_INTERACTION=".length)));
    } else if (text.startsWith("SMX038_ERROR=")) {
      evidence.godot.error = text;
    }
  });

  await page.goto(URL, { waitUntil: "networkidle", timeout: 60_000 });
  let state = await waitForState(page, (value) => value.godot_player?.available === true, "qualified Godot runtime");
  assert.equal(state.runtime.mode, "edit");

  const buttonId = await createVisualThing(page, "Button");
  const buttonState = await editorState(page);
  const button = buttonState.canonical.things.find((thing) => thing.thing_id === buttonId);
  const buttonVisual = structuredClone(button.authored_state.visual);
  assert.deepEqual(
    button.ports.find((port) => port.port_id === "clicked"),
    { port_id: "clicked", name: "Clicked", kind: "event", direction: "out" },
  );
  evidence.checks.source_capability_is_canonical = true;

  const lampId = await createVisualThing(page, "Lamp");
  state = await editorState(page);
  assert.equal(state.authoring.connections.targets.length, 0);
  assert.match(await page.locator("#connections-help").textContent(), /add a Change colour Rule/i);
  evidence.checks.incompatible_target_hidden_before_capability = true;

  const lampRuleId = await setSelectedRuleColour(page, "#22cc88");
  state = await waitForState(
    page,
    (value) => value.authoring.connections.targets.some((row) => row.thing_id === lampId),
    "Lamp compatible action",
  );
  const lamp = state.canonical.things.find((thing) => thing.thing_id === lampId);
  assert.deepEqual(
    lamp.ports.find((port) => port.port_id === "change-colour"),
    { port_id: "change-colour", name: "Change colour", kind: "command", direction: "in" },
  );
  evidence.checks.target_action_is_canonical_rule_capability = true;

  assert.equal(await page.locator("#visual-connection-form input:not([type=hidden])").count(), 0);
  assert.equal(await page.locator(".advanced-disclosure").evaluate((element) => element.open), false);
  await page.getByTestId("connection-source-thing").selectOption(buttonId);
  await page.getByTestId("connection-target-thing").selectOption(lampId);
  assert.equal(await page.getByTestId("connection-source-event").locator("option:checked").textContent(), "Clicked");
  assert.equal(await page.getByTestId("connection-target-action").locator("option:checked").textContent(), "Change colour");
  evidence.checks.ordinary_authoring_uses_named_choices_not_typed_ids = true;

  await page.getByTestId("save-connection").click();
  state = await waitForState(page, (value) => value.canonical.connections.length === 1, "Connection creation");
  const connection = state.canonical.connections[0];
  const connectionId = connection.connection_id;
  assert.equal(connection.source.thing_id, buttonId);
  assert.equal(connection.source.port_id, "clicked");
  assert.equal(connection.target.thing_id, lampId);
  assert.equal(connection.target.port_id, "change-colour");
  assert.equal(state.authoring.connections.connections[0].connection_id, connectionId);
  assert.equal(state.authoring.connections.connections[0].play_supported, true);
  assert.match(await page.getByTestId("connection-card").textContent(), /Button — Clicked → Lamp — Change colour/);
  evidence.connection = { connection_id: connectionId, source: connection.source, target: connection.target };
  evidence.checks.visible_connection_card_and_stable_identity = true;

  const lampTwoId = await createVisualThing(page, "Lamp Two");
  await setSelectedRuleColour(page, "#cc4488");
  await page.getByTestId(`edit-connection-${connectionId}`).click();
  await page.getByTestId("connection-target-thing").selectOption(lampTwoId);
  await page.getByTestId("save-connection").click();
  state = await waitForState(
    page,
    (value) => value.canonical.connections[0]?.target?.thing_id === lampTwoId,
    "Connection target edit",
  );
  assert.equal(state.canonical.connections[0].connection_id, connectionId);
  assert.match(await page.getByTestId("connection-card").textContent(), /Lamp Two — Change colour/);

  await page.getByTestId(`edit-connection-${connectionId}`).click();
  await page.getByTestId("connection-target-thing").selectOption(lampId);
  await page.getByTestId("save-connection").click();
  state = await waitForState(
    page,
    (value) => value.canonical.connections[0]?.target?.thing_id === lampId,
    "Connection target edit restored",
  );
  assert.equal(state.canonical.connections[0].connection_id, connectionId);
  evidence.checks.connection_reopens_and_edits_without_identity_change = true;

  await page.getByTestId("save").click();
  state = await waitForState(page, (value) => Boolean(value.storage?.saved_revision_id), "Connection Save");
  const savedRevision = state.storage.saved_revision_id;
  await page.getByTestId("reload").click();
  state = await waitForState(
    page,
    (value) => value.canonical.project_revision_id === savedRevision
      && value.canonical.connections[0]?.connection_id === connectionId,
    "Connection Save Reload",
  );
  assert.equal(state.canonical.connections[0].source.thing_id, buttonId);
  assert.equal(state.canonical.connections[0].target.thing_id, lampId);
  assert.equal(state.authoring.connections.connections[0].play_supported, true);
  evidence.checks.connection_survives_save_reload = true;

  const beforePlayRevision = state.canonical.project_revision_id;
  const beforePlayLampVisual = structuredClone(
    state.canonical.things.find((thing) => thing.thing_id === lampId).authored_state.visual,
  );
  const sourceRuleCount = state.canonical.things.find((thing) => thing.thing_id === buttonId).behaviours.length;
  assert.equal(sourceRuleCount, 0);

  await page.getByTestId("play").click();
  state = await waitForState(page, (value) => value.runtime.mode === "play", "Play");
  assert.equal(state.canonical.project_revision_id, beforePlayRevision);
  const runtimeFrame = page.frameLocator("#godot-player");
  const canvas = runtimeFrame.locator("canvas");
  await canvas.waitFor({ state: "visible", timeout: 60_000 });

  const readyDeadline = Date.now() + 60_000;
  while (!evidence.godot.ready && Date.now() < readyDeadline) {
    if (evidence.godot.error) throw new Error(evidence.godot.error);
    await page.waitForTimeout(50);
  }
  assert(evidence.godot.ready, `Godot ready evidence missing; console=${consoleLines.join("\n")}`);
  assert.equal(evidence.godot.ready.contract, "splashmx.editor-godot-play-ready/1");
  assert.equal(evidence.godot.ready.project_revision_id, beforePlayRevision);
  assert(evidence.godot.ready.thing_ids.includes(buttonId));
  assert(evidence.godot.ready.thing_ids.includes(lampId));
  evidence.checks.real_godot_materialized_connected_things = true;

  const metrics = await canvas.evaluate((element) => ({
    clientWidth: element.clientWidth,
    clientHeight: element.clientHeight,
  }));
  const centreX = Number(buttonVisual.x) + Number(buttonVisual.width) / 2;
  const centreY = Number(buttonVisual.y) + Number(buttonVisual.height) / 2;
  await canvas.click({
    position: {
      x: Math.max(1, Math.min(metrics.clientWidth - 1, centreX / 640 * metrics.clientWidth)),
      y: Math.max(1, Math.min(metrics.clientHeight - 1, centreY / 360 * metrics.clientHeight)),
    },
  });

  const interactionDeadline = Date.now() + 30_000;
  while (
    !evidence.godot.interactions.some(
      (row) => row.source_thing_id === buttonId && row.thing_id === lampId && row.visual?.fill === "#22cc88",
    )
    && Date.now() < interactionDeadline
  ) {
    if (evidence.godot.error) throw new Error(evidence.godot.error);
    await page.waitForTimeout(50);
  }
  const routed = evidence.godot.interactions.find(
    (row) => row.source_thing_id === buttonId && row.thing_id === lampId && row.visual?.fill === "#22cc88",
  );
  assert(routed, `connected Godot interaction missing; interactions=${JSON.stringify(evidence.godot.interactions)}`);
  assert.equal(routed.trigger, "pointer_click");
  evidence.checks.physical_source_click_routes_connection_to_target_rule = true;

  state = await editorState(page);
  assert.equal(state.canonical.project_revision_id, beforePlayRevision);
  assert.deepEqual(
    state.canonical.things.find((thing) => thing.thing_id === lampId).authored_state.visual,
    beforePlayLampVisual,
  );
  evidence.checks.runtime_target_change_is_not_authored = true;

  await page.getByTestId("stop").click();
  state = await waitForState(page, (value) => value.runtime.mode === "edit", "Stop");
  assert.equal(state.canonical.project_revision_id, beforePlayRevision);
  assert.deepEqual(
    state.canonical.things.find((thing) => thing.thing_id === lampId).authored_state.visual,
    beforePlayLampVisual,
  );
  evidence.checks.stop_restores_unchanged_authored_state = true;

  assert.equal(
    state.canonical.things.find((thing) => thing.thing_id === lampId).behaviours[0].attachment_id,
    lampRuleId,
  );

  await page.getByTestId(`delete-connection-${connectionId}`).click();
  state = await waitForState(page, (value) => value.canonical.connections.length === 0, "Connection delete");
  assert.equal(await page.getByTestId("connection-card").count(), 0);
  evidence.checks.connection_delete_is_visible_and_canonical = true;

  evidence.passed = true;
} catch (error) {
  evidence.passed = false;
  evidence.error = String(error?.stack || error);
  throw error;
} finally {
  evidence.console_line_count = consoleLines.length;
  await fs.writeFile(OUT, JSON.stringify(evidence, null, 2) + "\n", "utf8");
  await browser.close();
}
