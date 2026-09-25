#!/usr/bin/env node
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright";

const ROOT = process.cwd();
const OUT = path.join(ROOT, "artifacts", "smx051d-editor-godot-evidence.json");
const URL = process.env.SMX051D_URL || "http://127.0.0.1:8131/";

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

await fs.mkdir(path.dirname(OUT), { recursive: true });
const browser = await chromium.launch({ headless: true });
const evidence = {
  schema: "splashmx.smx051d-editor-godot-evidence/1",
  issue: "SMX-051D",
  source_url: URL,
  checks: {},
  godot: { ready: null, interaction: null },
};
const consoleLines = [];

try {
  evidence.browser = { product: await browser.version(), playwright: "1.55.0", headless: true };
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  page.on("console", (message) => {
    const text = message.text();
    consoleLines.push(text);
    if (text.startsWith("SMX051C_PLAY_READY=")) {
      evidence.godot.ready = JSON.parse(text.slice("SMX051C_PLAY_READY=".length));
    } else if (text.startsWith("SMX051D_INTERACTION=")) {
      evidence.godot.interaction = JSON.parse(text.slice("SMX051D_INTERACTION=".length));
    } else if (text.startsWith("SMX038_ERROR=")) {
      evidence.godot.error = text;
    }
  });

  await page.goto(URL, { waitUntil: "networkidle", timeout: 60_000 });
  let state = await waitForState(page, (value) => value.godot_player?.available === true, "qualified Godot runtime");
  assert.equal(state.runtime.mode, "edit");

  await page.locator("#new-label").fill("Interactive Button");
  await page.locator("#new-shape").selectOption("rectangle");
  await page.getByTestId("create-thing").click();
  state = await waitForState(page, (value) => value.canonical.things.length === 1 && value.editor.selection.length === 1, "visible Thing creation");
  const thingId = state.canonical.things[0].thing_id;
  const authoredVisual = structuredClone(state.canonical.things[0].authored_state.visual);
  evidence.authored = { thing_id: thingId, visual: authoredVisual };
  evidence.checks.visual_thing_authored = true;

  await page.getByTestId("add-rule").click();
  state = await waitForState(page, (value) => value.canonical.things[0]?.behaviours?.length === 1, "visible Rule creation");
  let rule = state.canonical.things[0].behaviours[0];
  assert.equal(rule.authored_config.projection, "Rule");
  assert.equal(rule.authored_config.event, "pointer_click");
  assert.equal(rule.authored_config.author_kind, "visual-fill");
  assert.equal(await page.getByTestId("rule-card").isVisible(), true);
  assert.equal(await page.getByTestId(`rule-badge-${thingId}`).isVisible(), true);
  evidence.checks.rule_is_visible = true;

  await page.getByTestId(`edit-rule-${rule.attachment_id}`).click();
  await page.locator('#rule-form select[name="event"]').selectOption("pointer_click");
  await page.locator('#rule-form select[name="action"]').selectOption("change_colour");
  await page.locator('#rule-form input[name="fill"]').fill("#22cc88");
  await page.getByTestId("save-rule").click();
  state = await waitForState(page, (value) => value.canonical.things[0]?.behaviours?.[0]?.authored_config?.actions?.[0]?.value === "#22cc88", "Rule edit");
  rule = state.canonical.things[0].behaviours[0];
  const attachmentId = rule.attachment_id;
  assert.equal(rule.authored_config.event, "pointer_click");
  evidence.checks.rule_reopened_and_edited = true;

  await page.getByTestId("save").click();
  state = await waitForState(page, (value) => Boolean(value.storage?.saved_revision_id), "Rule Save");
  const savedRevision = state.storage.saved_revision_id;
  assert(savedRevision);
  await page.getByTestId("reload").click();
  state = await waitForState(page, (value) => value.canonical.things[0]?.behaviours?.[0]?.attachment_id === attachmentId, "Rule Save Reload");
  assert.equal(state.canonical.things[0].behaviours[0].authored_config.actions[0].value, "#22cc88");
  evidence.checks.rule_survives_save_reload = true;

  await page.getByTestId(`stage-thing-${thingId}`).click();
  state = await waitForState(page, (value) => value.editor.selection.length === 1 && value.editor.selection[0] === thingId, "Thing reselection");
  const playRevision = state.canonical.project_revision_id;
  const beforePlayVisual = structuredClone(state.canonical.things[0].authored_state.visual);

  await page.getByTestId("play").click();
  state = await waitForState(page, (value) => value.runtime.mode === "play", "Play");
  assert.equal(state.canonical.project_revision_id, playRevision);
  assert.deepEqual(state.canonical.things[0].authored_state.visual, beforePlayVisual);
  evidence.checks.click_rule_did_not_fire_at_play_start = true;

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
  assert.equal(evidence.godot.ready.project_revision_id, playRevision);
  assert.deepEqual(evidence.godot.ready.thing_ids, [thingId]);
  evidence.checks.godot_interactive_thing_ready = true;

  const metrics = await canvas.evaluate((element) => ({
    clientWidth: element.clientWidth,
    clientHeight: element.clientHeight,
  }));
  assert(metrics.clientWidth > 0 && metrics.clientHeight > 0);
  const centreX = Number(beforePlayVisual.x) + Number(beforePlayVisual.width) / 2;
  const centreY = Number(beforePlayVisual.y) + Number(beforePlayVisual.height) / 2;
  await canvas.click({
    position: {
      x: Math.max(1, Math.min(metrics.clientWidth - 1, centreX / 640 * metrics.clientWidth)),
      y: Math.max(1, Math.min(metrics.clientHeight - 1, centreY / 360 * metrics.clientHeight)),
    },
  });

  const deadline = Date.now() + 30_000;
  while (!evidence.godot.interaction && Date.now() < deadline) {
    if (evidence.godot.error) throw new Error(evidence.godot.error);
    await page.waitForTimeout(50);
  }
  assert(evidence.godot.interaction, `Godot interaction evidence missing; console=${consoleLines.join("\n")}`);
  assert.equal(evidence.godot.interaction.contract, "splashmx.editor-godot-interaction/1");
  assert.equal(evidence.godot.interaction.project_revision_id, playRevision);
  assert.equal(evidence.godot.interaction.thing_id, thingId);
  assert.equal(evidence.godot.interaction.trigger, "pointer_click");
  assert.equal(evidence.godot.interaction.visual.fill, "#22cc88");
  evidence.checks.real_godot_click_executes_rule = true;

  state = await editorState(page);
  assert.equal(state.canonical.project_revision_id, playRevision);
  assert.deepEqual(state.canonical.things[0].authored_state.visual, beforePlayVisual);
  evidence.checks.runtime_mutation_is_not_authored = true;

  await page.getByTestId("stop").click();
  state = await waitForState(page, (value) => value.runtime.mode === "edit", "Stop");
  assert.equal(state.canonical.project_revision_id, playRevision);
  assert.deepEqual(state.canonical.things[0].authored_state.visual, beforePlayVisual);
  evidence.checks.stop_restores_authored_state = true;

  assert.equal(await page.getByTestId(`edit-rule-${attachmentId}`).isVisible(), true);
  await page.getByTestId(`delete-rule-${attachmentId}`).click();
  state = await waitForState(page, (value) => value.canonical.things[0]?.behaviours?.length === 0, "Rule delete");
  assert.equal(await page.getByTestId(`rule-badge-${thingId}`).count(), 0);
  evidence.checks.rule_delete_is_visible_and_canonical = true;

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
