#!/usr/bin/env node
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { chromium } from "playwright";

const ROOT = process.cwd();
const OUT = path.join(ROOT, "artifacts", "smx051g-editor-godot-evidence.json");
const STORE = path.join(ROOT, "artifacts", "smx051g-editor.sqlite3");
const GODOT_ROOT = path.resolve(process.env.SMX051G_GODOT_ROOT || path.join(ROOT, "build", "web"));

async function startServer() {
  const env = { ...process.env, PYTHONPATH: [path.join(ROOT, "src"), process.env.PYTHONPATH].filter(Boolean).join(path.delimiter) };
  const child = spawn(process.env.PYTHON || "python", [
    "-m", "splashmx.editor.browser_server",
    "--port", "0",
    "--project-id", "smx051g-browser",
    "--store-path", STORE,
    "--godot-web-root", GODOT_ROOT,
  ], { cwd: ROOT, env, stdio: ["ignore", "pipe", "pipe"] });
  let stderr = "";
  child.stderr.setEncoding("utf8");
  child.stderr.on("data", (chunk) => { stderr += chunk; });
  const baseURL = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`SMX-051G server did not start: ${stderr}`)), 15_000);
    let stdout = "";
    child.stdout.setEncoding("utf8");
    child.stdout.on("data", (chunk) => {
      stdout += chunk;
      const match = stdout.match(/SMX032 READY (http:\/\/[^\s]+)/);
      if (match) {
        clearTimeout(timer);
        resolve(match[1]);
      }
    });
    child.on("exit", (code) => {
      clearTimeout(timer);
      reject(new Error(`SMX-051G server exited early (${code}): ${stderr}`));
    });
  });
  return { child, baseURL, stderr: () => stderr };
}

async function stopServer(child) {
  if (!child || child.exitCode !== null) return;
  await new Promise((resolve) => {
    child.once("exit", resolve);
    child.kill("SIGTERM");
    setTimeout(resolve, 2000);
  });
}

async function waitForState(page, predicate, label, timeoutMs = 15_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const value = await page.evaluate(() => window.splashmxState?.());
    if (value && predicate(value)) return value;
    await page.waitForTimeout(40);
  }
  throw new Error(`timeout waiting for ${label}`);
}

function thing(state, id) {
  return state.canonical.things.find((row) => row.thing_id === id);
}

await fs.mkdir(path.dirname(OUT), { recursive: true });
await fs.rm(STORE, { force: true });
await fs.rm(`${STORE}.collaboration.sqlite3`, { force: true });

const evidence = {
  schema: "splashmx.smx051g-editor-hardening-evidence/1",
  issue: "SMX-051G",
  checks: {},
  godot: { ready: null, interactions: [] },
};
let server = await startServer();
let browser;

try {
  browser = await chromium.launch({ headless: true });
  evidence.browser = { product: await browser.version(), playwright: "1.55.0", headless: true };
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const pageErrors = [];
  const consoleLines = [];
  page.on("pageerror", (error) => pageErrors.push(String(error?.stack || error)));
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

  await page.goto(server.baseURL, { waitUntil: "networkidle", timeout: 60_000 });
  let state = await waitForState(page, (value) => value.godot_player?.available === true, "qualified editor");
  assert.equal(state.storage.state, "never-saved");
  assert.equal(await page.getByTestId("save-state").innerText(), "Not saved yet");
  assert.equal(await page.evaluate(() => window.splashmxI18n?.currentLocale()), "en");
  evidence.checks.localization_and_explicit_initial_save_state = true;

  await page.locator("#new-label").fill("Button");
  await page.getByTestId("create-thing").click();
  state = await waitForState(page, (value) => value.canonical.things.some((row) => row.label === "Button"), "Button");
  const buttonId = state.canonical.things.find((row) => row.label === "Button").thing_id;
  const initialButton = structuredClone(thing(state, buttonId).authored_state.visual);

  await page.getByTestId(`stage-thing-${buttonId}`).focus();
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("Shift+ArrowDown");
  state = await waitForState(page, (value) => {
    const visual = thing(value, buttonId)?.authored_state?.visual;
    return visual?.x === initialButton.x + 5 && visual?.height === initialButton.height + 5;
  }, "keyboard direct manipulation");
  evidence.checks.keyboard_move_and_resize = true;

  await page.getByTestId("layer-forward").click();
  state = await waitForState(page, (value) => thing(value, buttonId)?.authored_state?.visual?.layer === 1, "stacking");
  assert.equal(await page.locator(`[data-testid="stage-thing-${buttonId}"]`).evaluate((el) => el.style.zIndex), "10001");
  evidence.checks.canonical_stacking_is_visible = true;

  await page.getByTestId("zoom-in").click();
  assert.notEqual(await page.getByTestId("stage-canvas").evaluate((el) => el.style.zoom), "1");
  await page.getByTestId("stage").focus();
  const beforeScroll = await page.getByTestId("stage").evaluate((el) => el.scrollLeft);
  await page.keyboard.press("ArrowRight");
  const afterScroll = await page.getByTestId("stage").evaluate((el) => el.scrollLeft);
  assert(afterScroll > beforeScroll);
  await page.getByTestId("zoom-reset").click();
  evidence.checks.stage_zoom_and_keyboard_pan = true;

  await page.locator("#new-label").fill("Lamp");
  await page.getByTestId("create-thing").click();
  state = await waitForState(page, (value) => value.canonical.things.some((row) => row.label === "Lamp"), "Lamp");
  const lampId = state.canonical.things.find((row) => row.label === "Lamp").thing_id;

  await page.getByTestId(`stage-thing-${lampId}`).click();
  await page.locator('#timeline-form select[name="property"]').selectOption("visual.y");
  const lampY = thing(state, lampId).authored_state.visual.y;
  await page.locator('#timeline-form input[name="start"]').fill(String(lampY));
  await page.locator('#timeline-form input[name="end"]').fill(String(lampY + 80));
  await page.locator('#timeline-form input[name="duration"]').fill("60");
  await page.getByTestId("add-timeline").click();
  state = await waitForState(page, (value) => thing(value, lampId)?.authored_state?.timeline_tracks?.length === 1, "Timeline");

  await page.getByTestId("add-rule").click();
  state = await waitForState(page, (value) => thing(value, lampId)?.behaviours?.length === 1, "Rule");
  evidence.checks.animation_and_beginner_rule_visible = true;

  await page.locator(`[data-testid="select-${buttonId}"]`).check();
  state = await waitForState(page, (value) => value.editor.selection.length === 2, "multi-selection");
  await page.getByTestId("group-selected").click();
  state = await waitForState(page, (value) => value.editor.selection.length === 1 && value.canonical.things.length === 3, "Group");
  const groupId = state.editor.selection[0];
  await page.getByTestId("make-reusable").click();
  state = await waitForState(page, (value) => value.canonical.definitions.length === 1, "reusable");
  const definitionId = state.canonical.definitions[0].definition_id;
  await page.getByTestId("library-add-instance").click();
  state = await waitForState(page, (value) => value.canonical.definitions.filter((row) => row.definition_id === definitionId).length === 2, "second instance");
  evidence.checks.group_reuse_and_visible_second_instance = true;

  await page.getByTestId("connection-source-thing").selectOption(buttonId);
  await page.getByTestId("connection-target-thing").selectOption(lampId);
  await page.getByTestId("save-connection").click();
  state = await waitForState(page, (value) => value.canonical.connections.length === 1, "Connection");
  const connectionId = state.canonical.connections[0].connection_id;
  assert.match(await page.getByTestId("connection-card").innerText(), /Button — Clicked → Lamp — Change colour/);
  evidence.checks.named_connection_without_internal_id_entry = true;

  evidence.godot.ready = null;
  evidence.godot.interactions = [];
  delete evidence.godot.error;
  const beforePlayRevision = state.canonical.project_revision_id;
  const buttonVisual = structuredClone(thing(state, buttonId).authored_state.visual);
  const lampAuthoredVisual = structuredClone(thing(state, lampId).authored_state.visual);
  await page.getByTestId("play").click();
  state = await waitForState(page, (value) => value.runtime.mode === "play", "Play");
  const frame = page.frameLocator("#godot-player");
  const canvas = frame.locator("canvas");
  await canvas.waitFor({ state: "visible", timeout: 60_000 });
  const readyDeadline = Date.now() + 60_000;
  while (!evidence.godot.ready && Date.now() < readyDeadline) {
    if (evidence.godot.error) throw new Error(evidence.godot.error);
    await page.waitForTimeout(60);
  }
  assert(evidence.godot.ready, `Godot ready evidence missing; console=${consoleLines.join("\n")}`);

  const projectionResponse = await page.request.get(`${server.baseURL}/api/godot-play-projection`);
  const projection = (await projectionResponse.json()).projection;
  assert.equal(projection.things.find((row) => row.thing_id === buttonId).visual.layer, 1);
  evidence.checks.stacking_reaches_real_godot_projection = true;

  const metrics = await canvas.evaluate((el) => ({ width: el.clientWidth, height: el.clientHeight }));
  const centreX = Number(buttonVisual.x) + Number(buttonVisual.width) / 2;
  const centreY = Number(buttonVisual.y) + Number(buttonVisual.height) / 2;
  await canvas.click({ position: {
    x: Math.max(1, Math.min(metrics.width - 1, centreX / 640 * metrics.width)),
    y: Math.max(1, Math.min(metrics.height - 1, centreY / 360 * metrics.height)),
  }});
  const interactionDeadline = Date.now() + 30_000;
  while (!evidence.godot.interactions.some((row) => row.source_thing_id === buttonId && row.thing_id === lampId) && Date.now() < interactionDeadline) {
    if (evidence.godot.error) throw new Error(evidence.godot.error);
    await page.waitForTimeout(50);
  }
  assert(evidence.godot.interactions.some((row) => row.source_thing_id === buttonId && row.thing_id === lampId));
  state = await page.evaluate(() => window.splashmxState());
  assert.equal(state.canonical.project_revision_id, beforePlayRevision);
  assert.deepEqual(thing(state, lampId).authored_state.visual, lampAuthoredVisual);
  await page.getByTestId("stop").click();
  state = await waitForState(page, (value) => value.runtime.mode === "edit", "Stop");
  evidence.checks.real_godot_connection_and_stop_state_separation = true;

  await page.getByTestId("save").click();
  state = await waitForState(page, (value) => value.storage.state === "saved", "saved state");
  const savedRevision = state.canonical.project_revision_id;
  assert.equal(await page.getByTestId("save-state").innerText(), "Saved");

  const downloadPromise = page.waitForEvent("download");
  await page.getByTestId("backup-export").click();
  const download = await downloadPromise;
  const backupPath = await download.path();
  assert(backupPath);
  const backupBytes = await fs.readFile(backupPath);
  assert(backupBytes.length > 0);
  evidence.checks.smx050_backup_export = true;

  await page.getByTestId(`stage-thing-${buttonId}`).focus();
  await page.keyboard.press("ArrowRight");
  state = await waitForState(page, (value) => value.storage.state === "dirty", "dirty state");
  assert.equal(await page.getByTestId("save-state").innerText(), "Unsaved changes");
  assert.match(await page.getByTestId("reload").innerText(), /discard unsaved changes/i);
  await page.getByTestId("reload").click();
  state = await waitForState(page, (value) => value.canonical.project_revision_id === savedRevision && value.storage.state === "saved", "Reload");
  assert.equal(thing(state, buttonId).authored_state.visual.x, buttonVisual.x);
  evidence.checks.dirty_reload_consequence_and_recovery = true;

  await page.getByTestId(`stage-thing-${buttonId}`).focus();
  await page.keyboard.press("ArrowRight");
  await waitForState(page, (value) => value.storage.state === "dirty", "dirty before backup restore");
  await page.getByTestId("backup-import").setInputFiles({
    name: "workflow.smxbackup",
    mimeType: "application/vnd.splashmx.recovery",
    buffer: backupBytes,
  });
  state = await waitForState(page, (value) => value.canonical.project_revision_id === savedRevision && value.storage.state === "saved", "backup restore");
  assert.equal(state.canonical.connections[0].connection_id, connectionId);
  evidence.checks.validated_backup_restore = true;

  await page.getByTestId("inspect-toggle").click();
  state = await waitForState(page, (value) => value.editor.inspect_open === true, "Inspect");
  assert.equal(await page.getByTestId("inspect-summary").isVisible(), true);
  assert.equal(await page.locator("#inspect-raw").evaluate((el) => el.open), false);
  assert.equal(await page.locator("#shortcuts-help").count(), 1);
  evidence.checks.progressive_inspect_and_shortcut_discoverability = true;

  await stopServer(server.child);
  server = await startServer();
  await page.goto(server.baseURL, { waitUntil: "networkidle", timeout: 60_000 });
  state = await waitForState(page, (value) =>
    value.godot_player?.available === true &&
    value.canonical.project_revision_id === savedRevision &&
    value.canonical.connections.some((row) => row.connection_id === connectionId),
  "process restart");
  assert.equal(state.storage.state, "saved");
  assert.equal(thing(state, buttonId).authored_state.visual.layer, 1);
  evidence.checks.process_restart_preserves_complete_workflow = true;

  assert.deepEqual(pageErrors, []);
  evidence.final = {
    project_revision_id: state.canonical.project_revision_id,
    connection_id: connectionId,
    definition_id: definitionId,
    thing_count: state.canonical.things.length,
    save_state: state.storage.state,
  };
  evidence.passed = true;
} catch (error) {
  evidence.passed = false;
  evidence.error = String(error?.stack || error);
  throw error;
} finally {
  await fs.writeFile(OUT, JSON.stringify(evidence, null, 2) + "\n", "utf8");
  if (browser) await browser.close();
  await stopServer(server?.child);
}
