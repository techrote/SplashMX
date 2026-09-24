#!/usr/bin/env node
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { chromium } from "playwright";

const ROOT = process.cwd();
const OUT = path.join(ROOT, "artifacts", "smx051c-editor-godot-evidence.json");
const URL = process.env.SMX051C_URL || "http://127.0.0.1:8130/";

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

function closeEnough(actual, expected, epsilon = 0.05) {
  return Math.abs(Number(actual) - Number(expected)) <= epsilon;
}

await fs.mkdir(path.dirname(OUT), { recursive: true });
const browser = await chromium.launch({ headless: true });
const evidence = {
  schema: "splashmx.smx051c-editor-godot-evidence/1",
  issue: "SMX-051C",
  source_url: URL,
  checks: {},
  godot: { ready: null, samples: [] },
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
    } else if (text.startsWith("SMX051C_SAMPLE=")) {
      evidence.godot.samples.push(JSON.parse(text.slice("SMX051C_SAMPLE=".length)));
    } else if (text.startsWith("SMX038_ERROR=")) {
      evidence.godot.error = text;
    }
  });

  await page.goto(URL, { waitUntil: "networkidle", timeout: 60_000 });
  let state = await waitForState(page, (value) => value.godot_player?.available === true, "qualified Godot runtime availability");
  assert.equal(state.runtime.mode, "edit");
  assert.equal(state.godot_player.runtime, "Godot 4.7.2");
  evidence.checks.runtime_advertised = true;

  await page.locator("#new-label").fill("Godot Sprite");
  await page.locator("#new-shape").selectOption("rectangle");
  await page.getByTestId("create-thing").click();
  state = await waitForState(page, (value) => value.canonical.things.length === 1 && value.editor.selection.length === 1, "visual Thing creation");
  const thing = state.canonical.things[0];
  const thingId = thing.thing_id;
  const baseVisual = structuredClone(thing.authored_state.visual);
  assert(baseVisual);
  evidence.checks.visual_thing_authored = true;

  const startX = Number(baseVisual.x);
  const endX = startX + 120;
  await page.locator('#timeline-form select[name="property"]').selectOption("visual.x");
  await page.locator('#timeline-form input[name="start"]').fill(String(startX));
  await page.locator('#timeline-form input[name="end"]').fill(String(endX));
  await page.locator('#timeline-form input[name="duration"]').fill("60");
  await page.getByTestId("add-timeline").click();
  state = await waitForState(page, (value) => {
    const tracks = value.canonical.things[0]?.authored_state?.timeline_tracks;
    return Array.isArray(tracks) && tracks.some((row) => row.property === "visual.x");
  }, "authored visual Timeline");
  const authoredRevision = state.canonical.project_revision_id;
  const authoredVisual = structuredClone(state.canonical.things[0].authored_state.visual);
  evidence.authored = {
    project_revision_id: authoredRevision,
    thing_id: thingId,
    start_x: startX,
    end_x: endX,
  };

  await page.getByTestId("play").click();
  state = await waitForState(page, (value) => value.runtime.mode === "play", "editor Play mode");
  assert.equal(state.canonical.project_revision_id, authoredRevision);
  assert.equal(await page.locator("#runtime-panel").isVisible(), true);
  assert.equal(await page.locator("#stage-panel").isHidden(), true);
  assert.equal(await page.getByTestId("godot-player").isVisible(), true);

  const runtimeFrame = page.frameLocator("#godot-player");
  await runtimeFrame.locator("canvas").waitFor({ state: "visible", timeout: 60_000 });
  evidence.checks.real_godot_canvas_visible = true;

  const deadline = Date.now() + 60_000;
  while (
    (evidence.godot.ready === null || evidence.godot.samples.length < 3) &&
    Date.now() < deadline
  ) {
    if (evidence.godot.error) throw new Error(evidence.godot.error);
    await page.waitForTimeout(100);
  }
  assert(evidence.godot.ready, `Godot ready evidence missing; console=${consoleLines.join("\n")}`);
  assert(evidence.godot.samples.length >= 3, `Godot samples incomplete; console=${consoleLines.join("\n")}`);
  assert.equal(evidence.godot.ready.contract, "splashmx.editor-godot-play-ready/1");
  assert.equal(evidence.godot.ready.project_revision_id, authoredRevision);
  assert.deepEqual(evidence.godot.ready.thing_ids, [thingId]);
  evidence.checks.stable_thing_identity_reaches_godot = true;

  const samples = evidence.godot.samples
    .filter((row) => row.project_revision_id === authoredRevision)
    .sort((a, b) => Number(a.tick) - Number(b.tick));
  const start = samples.find((row) => closeEnough(row.tick, 0));
  const midpoint = samples.find((row) => closeEnough(row.tick, 30));
  const end = samples.find((row) => closeEnough(row.tick, 60));
  assert(start && midpoint && end, `expected start/mid/end samples; got ${JSON.stringify(samples)}`);

  for (const sample of [start, midpoint, end]) {
    assert.equal(sample.contract, "splashmx.editor-godot-play-sample/1");
    assert.equal(sample.things.length, 1);
    assert.equal(sample.things[0].thing_id, thingId);
  }
  assert(closeEnough(start.things[0].x, startX));
  assert(closeEnough(midpoint.things[0].x, startX + 60));
  assert(closeEnough(end.things[0].x, endX));
  evidence.checks.godot_timeline_start_mid_end = true;

  state = await waitForState(page, () => true, "canonical state during Godot Play");
  assert.equal(state.canonical.project_revision_id, authoredRevision);
  assert.deepEqual(state.canonical.things[0].authored_state.visual, authoredVisual);
  evidence.checks.godot_play_does_not_mutate_authored_state = true;

  await page.getByTestId("stop").click();
  state = await waitForState(page, (value) => value.runtime.mode === "edit", "Stop back to authoring");
  assert.equal(state.canonical.project_revision_id, authoredRevision);
  assert.deepEqual(state.canonical.things[0].authored_state.visual, authoredVisual);
  assert.equal(await page.locator("#stage-panel").isVisible(), true);
  assert.equal(await page.locator("#runtime-panel").isHidden(), true);
  evidence.checks.stop_restores_authored_editor = true;

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
