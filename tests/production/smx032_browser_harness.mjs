#!/usr/bin/env node
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { chromium } from "playwright";

const ROOT = process.cwd();
const OUT = path.join(ROOT, "artifacts", "smx032-browser-results.json");
const STORE = path.join(ROOT, "artifacts", "smx051a-browser.sqlite3");
const FORBIDDEN = ["nodepath", "scenetree", "resourceuid", "godot rpc", "package manager", "build pipeline", "export preset"];

async function startServer() {
  const env = { ...process.env, PYTHONPATH: [path.join(ROOT, "src"), process.env.PYTHONPATH].filter(Boolean).join(path.delimiter) };
  const child = spawn(process.env.PYTHON || "python", ["-m", "splashmx.editor.browser_server", "--port", "0", "--project-id", "smx032-browser", "--store-path", STORE], {
    cwd: ROOT,
    env,
    stdio: ["ignore", "pipe", "pipe"],
  });
  let stderr = "";
  child.stderr.setEncoding("utf8");
  child.stderr.on("data", (chunk) => { stderr += chunk; });
  const baseURL = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`authoring server did not start: ${stderr}`)), 10000);
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
      reject(new Error(`authoring server exited early (${code}): ${stderr}`));
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

async function waitFor(page, predicate, label, timeoutMs = 8000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const state = await page.evaluate(() => window.splashmxState?.());
    if (state && predicate(state)) return state;
    await page.waitForTimeout(40);
  }
  throw new Error(`timed out waiting for ${label}`);
}

async function setSelection(page, ids) {
  await page.evaluate(async (thingIds) => {
    const response = await fetch("/api/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "select", data: { thing_ids: thingIds } }),
    });
    if (!response.ok) throw new Error(await response.text());
  }, ids);
  await page.reload({ waitUntil: "networkidle" });
  return waitFor(page, (state) => JSON.stringify(state.editor.selection) === JSON.stringify([...ids].sort()), "selection");
}

async function postRaw(page, action, data) {
  return page.evaluate(async ({ action, data }) => {
    const response = await fetch("/api/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, data }),
    });
    return { status: response.status, payload: await response.json() };
  }, { action, data });
}

const evidence = { issue: "SMX-032+SMX-051A", checks: {}, environment: { node: process.version } };
await fs.mkdir(path.dirname(OUT), { recursive: true });
await fs.rm(STORE, { force: true });
await fs.rm(`${STORE}.collaboration.sqlite3`, { force: true });
let server = await startServer();
let browser;
try {
  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await page.goto(server.baseURL, { waitUntil: "networkidle" });
  let state = await waitFor(page, () => true, "initial state");
  assert.equal(state.canonical.things.length, 0);

  const visibleCopy = (await page.locator("body").innerText()).toLowerCase();
  for (const term of FORBIDDEN) assert.equal(visibleCopy.includes(term), false, `ordinary surface leaked ${term}`);
  evidence.checks.author_vocabulary = true;

  await page.locator("#new-label").fill("Button");
  await page.getByTestId("create-thing").click();
  state = await waitFor(page, (value) => value.canonical.things.length === 1, "Button creation");
  const button = state.canonical.things[0].thing_id;
  await waitFor(page, (value) => value.editor.selection.includes(button), "new visual Thing selection");
  let buttonThing = state.canonical.things.find((thing) => thing.thing_id === button);
  assert(buttonThing.authored_state.visual, "new Thing did not receive canonical visual state");
  const stageThing = page.getByTestId(`stage-thing-${button}`);
  assert.equal(await stageThing.isVisible(), true);
  evidence.checks.visual_stage_creation = true;

  const startVisual = { ...buttonThing.authored_state.visual };
  let box = await stageThing.boundingBox();
  assert(box, "visual Thing did not have a Stage bounding box");
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 + 36, box.y + box.height / 2 + 24);
  await page.mouse.up();
  state = await waitFor(page, (value) => {
    const visual = value.canonical.things.find((thing) => thing.thing_id === button)?.authored_state.visual;
    return visual && visual.x === startVisual.x + 36 && visual.y === startVisual.y + 24;
  }, "pointer drag canonical visual position");
  evidence.checks.pointer_move_updates_canonical = true;

  await page.getByTestId(`stage-thing-${button}`).focus();
  const beforeKeyboardX = state.canonical.things.find((thing) => thing.thing_id === button).authored_state.visual.x;
  await page.keyboard.press("ArrowRight");
  state = await waitFor(page, (value) => value.canonical.things.find((thing) => thing.thing_id === button)?.authored_state.visual.x === beforeKeyboardX + 5, "keyboard movement");
  const beforeKeyboardHeight = state.canonical.things.find((thing) => thing.thing_id === button).authored_state.visual.height;
  await page.getByTestId(`stage-thing-${button}`).focus();
  await page.keyboard.press("Shift+ArrowDown");
  state = await waitFor(page, (value) => value.canonical.things.find((thing) => thing.thing_id === button)?.authored_state.visual.height === beforeKeyboardHeight + 5, "keyboard resize");
  evidence.checks.keyboard_visual_editing = true;

  const resizeHandle = page.getByTestId(`resize-${button}`);
  box = await resizeHandle.boundingBox();
  assert(box, "resize handle did not have a bounding box");
  const beforeResize = { ...state.canonical.things.find((thing) => thing.thing_id === button).authored_state.visual };
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 + 25, box.y + box.height / 2 + 15);
  await page.mouse.up();
  state = await waitFor(page, (value) => {
    const visual = value.canonical.things.find((thing) => thing.thing_id === button)?.authored_state.visual;
    return visual && visual.width === beforeResize.width + 25 && visual.height === beforeResize.height + 15;
  }, "pointer resize canonical visual size");
  evidence.checks.pointer_resize_updates_canonical = true;

  await page.locator('#visual-properties input[name="rotation"]').fill("15");
  await page.locator('#visual-properties input[name="fill"]').evaluate((input) => { input.value = "#336699"; input.dispatchEvent(new Event("input", { bubbles: true })); });
  await page.getByTestId("apply-visual-properties").click();
  state = await waitFor(page, (value) => {
    const visual = value.canonical.things.find((thing) => thing.thing_id === button)?.authored_state.visual;
    return visual && visual.rotation === 15 && visual.fill === "#336699";
  }, "visual properties application");
  evidence.checks.visual_properties = true;

  const visualBeforeTimeline = { ...state.canonical.things.find((thing) => thing.thing_id === button).authored_state.visual };
  await page.locator('#timeline-form select[name="property"]').selectOption("visual.x");
  await page.locator('#timeline-form input[name="start"]').fill(String(visualBeforeTimeline.x));
  await page.locator('#timeline-form input[name="end"]').fill(String(visualBeforeTimeline.x + 120));
  await page.locator('#timeline-form input[name="duration"]').fill("60");
  await page.getByTestId("add-timeline").click();
  state = await waitFor(page, (value) => {
    const tracks = value.canonical.things.find((thing) => thing.thing_id === button)?.authored_state.timeline_tracks;
    return Array.isArray(tracks) && tracks.some((track) => track.property === "visual.x");
  }, "visible Timeline track");
  const visualTrack = state.canonical.things.find((thing) => thing.thing_id === button).authored_state.timeline_tracks.find((track) => track.property === "visual.x");
  assert.deepEqual(visualTrack.keyframes, [{ tick: 0, value: visualBeforeTimeline.x }, { tick: 60, value: visualBeforeTimeline.x + 120 }]);
  assert.equal(await page.getByTestId("timeline-track").count() >= 1, true);
  const revisionBeforeScrub = state.canonical.project_revision_id;
  const canonicalVisualBeforeScrub = structuredClone(state.canonical.things.find((thing) => thing.thing_id === button).authored_state.visual);

  await page.getByTestId("timeline-scrubber").fill("30");
  await page.waitForFunction(({ id, expected }) => {
    const node = document.querySelector(`[data-testid="stage-thing-${id}"]`);
    return node && Math.abs(parseFloat(node.style.left) - expected) < 0.01;
  }, { id: button, expected: visualBeforeTimeline.x + 60 });
  state = await waitFor(page, () => true, "Timeline scrub state");
  assert.equal(state.canonical.project_revision_id, revisionBeforeScrub);
  assert.deepEqual(state.canonical.things.find((thing) => thing.thing_id === button).authored_state.visual, canonicalVisualBeforeScrub);
  evidence.checks.timeline_scrub_is_transient = true;

  await page.getByTestId("timeline-preview").click();
  await page.waitForFunction(() => document.querySelector("#status")?.textContent?.includes("Timeline preview finished"));
  await page.waitForFunction(({ id, expected }) => {
    const node = document.querySelector(`[data-testid="stage-thing-${id}"]`);
    return node && Math.abs(parseFloat(node.style.left) - expected) < 0.01;
  }, { id: button, expected: visualBeforeTimeline.x });
  state = await waitFor(page, () => true, "Timeline preview reset state");
  assert.equal(state.canonical.project_revision_id, revisionBeforeScrub);
  assert.deepEqual(state.canonical.things.find((thing) => thing.thing_id === button).authored_state.visual, canonicalVisualBeforeScrub);
  evidence.checks.timeline_visible_preview = true;

  await page.getByTestId("save").click();
  state = await waitFor(page, (value) => value.storage?.saved_revision_id === value.canonical.project_revision_id, "visual save");
  const savedVisual = { ...state.canonical.things.find((thing) => thing.thing_id === button).authored_state.visual };
  await postRaw(page, "updateVisual", { thing_id: button, visual: { ...savedVisual, x: savedVisual.x + 100 } });
  await page.reload({ waitUntil: "networkidle" });
  await page.getByTestId("reload").click();
  state = await waitFor(page, (value) => value.canonical.things.find((thing) => thing.thing_id === button)?.authored_state.visual.x === savedVisual.x, "visual reload");
  assert.deepEqual(state.canonical.things.find((thing) => thing.thing_id === button).authored_state.visual, savedVisual);
  evidence.checks.visual_save_reload = true;

  await stopServer(server.child);
  server = await startServer();
  await page.goto(server.baseURL, { waitUntil: "networkidle" });
  state = await waitFor(page, (value) => {
    const visual = value.canonical.things.find((thing) => thing.thing_id === button)?.authored_state.visual;
    return visual && visual.x === savedVisual.x && visual.width === savedVisual.width && visual.fill === savedVisual.fill;
  }, "visual state after server restart");
  assert.deepEqual(state.canonical.things.find((thing) => thing.thing_id === button).authored_state.visual, savedVisual);
  const restartedTracks = state.canonical.things.find((thing) => thing.thing_id === button).authored_state.timeline_tracks;
  assert(Array.isArray(restartedTracks) && restartedTracks.some((track) => track.property === "visual.x"));
  evidence.checks.visual_process_restart = true;
  evidence.checks.timeline_save_restart = true;

  await page.locator("#new-label").fill("Lamp");
  await page.getByTestId("create-thing").click();
  state = await waitFor(page, (value) => value.canonical.things.length === 2, "Lamp creation");
  const lamp = state.canonical.things.find((thing) => thing.label === "Lamp").thing_id;
  assert.notEqual(button, lamp);
  evidence.checks.blank_stage_create = true;

  const revisionBeforeSelection = state.canonical.project_revision_id;
  await page.locator(`[data-testid="select-${button}"]`).check();
  state = await waitFor(page, (value) => value.editor.selection.includes(button), "transient selection");
  assert.equal(state.canonical.project_revision_id, revisionBeforeSelection);
  assert.equal(JSON.stringify(state.canonical).includes("selection"), false);
  evidence.checks.transient_selection = true;

  await page.locator(`[data-testid="select-${lamp}"]`).check();
  state = await waitFor(page, (value) => value.editor.selection.length === 2, "multi selection");
  await page.getByTestId("group-selected").click();
  state = await waitFor(page, (value) => value.canonical.things.length === 3 && value.editor.selection.length === 1, "grouping");
  const group = state.editor.selection[0];
  assert(state.canonical.things.some((thing) => thing.thing_id === button && thing.parent_thing_id === group));
  assert(state.canonical.things.some((thing) => thing.thing_id === lamp && thing.parent_thing_id === group));
  evidence.checks.group_preserves_identity = true;

  await page.getByTestId("make-reusable").click();
  state = await waitFor(page, (value) => value.canonical.definitions.length >= 1, "Make reusable");
  assert(state.canonical.things.some((thing) => thing.thing_id === button));
  assert(state.canonical.things.some((thing) => thing.thing_id === lamp));
  evidence.checks.reuse_preserves_first_instance = true;

  await setSelection(page, [button]);
  await page.locator('#port-form input[name="port_id"]').fill("clicked");
  await page.locator('#port-form input[name="name"]').fill("Clicked");
  await page.locator('#port-form select[name="kind"]').selectOption("event");
  await page.locator('#port-form select[name="direction"]').selectOption("out");
  await page.getByTestId("add-port").click();
  state = await waitFor(page, (value) => value.canonical.things.find((thing) => thing.thing_id === button)?.ports.some((port) => port.port_id === "clicked"), "source port");

  await setSelection(page, [lamp]);
  await page.locator('#port-form input[name="port_id"]').fill("toggle");
  await page.locator('#port-form input[name="name"]').fill("Toggle");
  await page.locator('#port-form select[name="kind"]').selectOption("command");
  await page.locator('#port-form select[name="direction"]').selectOption("in");
  await page.getByTestId("add-port").click();
  await waitFor(page, (value) => value.canonical.things.find((thing) => thing.thing_id === lamp)?.ports.some((port) => port.port_id === "toggle"), "target port");

  await page.locator('#connection-form select[name="source_thing_id"]').selectOption(button);
  await page.locator('#connection-form input[name="source_port_id"]').fill("clicked");
  await page.locator('#connection-form select[name="target_thing_id"]').selectOption(lamp);
  await page.locator('#connection-form input[name="target_port_id"]').fill("toggle");
  await page.getByTestId("connect").click();
  state = await waitFor(page, (value) => value.canonical.connections.length === 1, "stable-port connection");
  assert.deepEqual(state.canonical.connections[0].source, { thing_id: button, port_id: "clicked" });
  assert.deepEqual(state.canonical.connections[0].target, { thing_id: lamp, port_id: "toggle" });
  evidence.checks.stable_port_connection = true;

  await setSelection(page, [button]);
  await page.getByTestId("add-rule").click();
  state = await waitFor(page, (value) => value.canonical.things.find((thing) => thing.thing_id === button)?.behaviours.length === 1, "Rule attachment");
  assert.equal(state.canonical.things.find((thing) => thing.thing_id === button).behaviours[0].authored_config.projection, "Rule");

  await setSelection(page, [lamp]);
  await page.getByTestId("add-behaviour").click();
  state = await waitFor(page, (value) => value.canonical.things.find((thing) => thing.thing_id === lamp)?.behaviours.length === 1, "Behaviour attachment");
  assert.equal(state.canonical.things.find((thing) => thing.thing_id === lamp).behaviours[0].authored_config.projection, "Behaviour");
  evidence.checks.rule_behaviour_projection = true;

  await setSelection(page, [button]);
  await page.locator('#timeline-form select[name="property"]').selectOption("visual.y");
  await page.getByTestId("add-timeline").click();
  state = await waitFor(page, (value) => Array.isArray(value.canonical.things.find((thing) => thing.thing_id === button)?.authored_state.timeline_tracks), "Timeline track");
  const timeline = state.canonical.things.find((thing) => thing.thing_id === button).authored_state.timeline_tracks[0];
  assert.equal(timeline.target_thing_id, button);
  evidence.checks.optional_timeline = true;

  await page.getByTestId("inspect-toggle").click();
  state = await waitFor(page, (value) => value.editor.inspect_open === true, "Inspect");
  assert.equal(await page.locator("#inspect").isVisible(), true);
  evidence.checks.inspect_projection = true;

  await page.getByTestId("import-file").setInputFiles({ name: "tone.wav", mimeType: "audio/wav", buffer: Buffer.from("RIFF-SMX032-BROWSER") });
  await page.getByTestId("import-media").click();
  state = await waitFor(page, (value) => value.canonical.assets.length === 1, "protected media import");
  const asset = state.canonical.assets[0];
  assert(asset.revision_digest.startsWith("sha256:"));
  assert(asset.source_digest.startsWith("sha256:"));
  assert.equal(asset.media_semantics.kind, "audio");
  assert.equal(asset.licence_attribution.licence, "CC0");
  assert.equal(asset.derivation_lineage.length, 1);
  evidence.checks.protected_media = true;

  const beforeBadConnection = state.canonical.connections.length;
  const badConnection = await postRaw(page, "connect", {
    source_thing_id: button,
    source_port_id: "clicked",
    target_thing_id: lamp,
    target_port_id: "missing",
    connection_id: "bad-browser-connection",
  });
  assert.equal(badConnection.status, 409);
  const afterBadConnection = await (await page.request.get(`${server.baseURL}/api/state`)).json();
  assert.equal(afterBadConnection.state.canonical.connections.length, beforeBadConnection);
  evidence.checks.invalid_connection_rollback = true;

  const beforeBadAsset = afterBadConnection.state.canonical.assets.length;
  const badAsset = await postRaw(page, "importAsset", {
    content_base64: Buffer.from("replacement").toString("base64"),
    source_name: "bad.wav",
    media_type: "audio/wav",
    media_semantics: { kind: "audio" },
    provenance: {},
    licence_attribution: { licence: "CC0" },
    derivation_lineage: [{ operation: "source", parent: null }],
    asset_id: "bad-asset",
    thing_id: "bad-asset-thing",
  });
  assert.equal(badAsset.status, 409);
  const afterBadAsset = await (await page.request.get(`${server.baseURL}/api/state`)).json();
  assert.equal(afterBadAsset.state.canonical.assets.length, beforeBadAsset);
  assert.equal(afterBadAsset.state.canonical.things.some((thing) => thing.thing_id === "bad-asset-thing"), false);
  evidence.checks.incomplete_media_rollback = true;

  const finalCopy = (await page.locator("body").innerText()).toLowerCase();
  for (const term of FORBIDDEN) assert.equal(finalCopy.includes(term), false, `ordinary surface leaked ${term}`);
  evidence.final = {
    project_revision_id: afterBadAsset.state.canonical.project_revision_id,
    thing_count: afterBadAsset.state.canonical.things.length,
    definition_count: afterBadAsset.state.canonical.definitions.length,
    connection_count: afterBadAsset.state.canonical.connections.length,
    asset_count: afterBadAsset.state.canonical.assets.length,
  };
  evidence.passed = true;
} catch (error) {
  evidence.passed = false;
  evidence.error = String(error?.stack || error);
  throw error;
} finally {
  await fs.mkdir(path.dirname(OUT), { recursive: true });
  await fs.writeFile(OUT, JSON.stringify(evidence, null, 2) + "\n", "utf8");
  if (browser) await browser.close();
  await stopServer(server?.child);
}
