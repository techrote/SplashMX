#!/usr/bin/env node
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { chromium } from "playwright";

const ROOT = process.cwd();
const OUT = path.join(ROOT, "artifacts", "smx051e-editor-godot-evidence.json");
const STORE = path.join(ROOT, "artifacts", "smx051e-editor.sqlite3");
const GODOT_ROOT = path.resolve(process.env.SMX051E_GODOT_ROOT || path.join(ROOT, "build", "web"));

async function startServer() {
  const env = { ...process.env, PYTHONPATH: [path.join(ROOT, "src"), process.env.PYTHONPATH].filter(Boolean).join(path.delimiter) };
  const child = spawn(process.env.PYTHON || "python", [
    "-m", "splashmx.editor.browser_server",
    "--port", "0",
    "--project-id", "smx051e-browser",
    "--store-path", STORE,
    "--godot-web-root", GODOT_ROOT,
  ], { cwd: ROOT, env, stdio: ["ignore", "pipe", "pipe"] });
  let stderr = "";
  child.stderr.setEncoding("utf8");
  child.stderr.on("data", (chunk) => { stderr += chunk; });
  const baseURL = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`SMX-051E authoring server did not start: ${stderr}`)), 12_000);
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
      reject(new Error(`SMX-051E authoring server exited early (${code}): ${stderr}`));
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

async function waitForState(page, predicate, label, timeoutMs = 10_000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const state = await page.evaluate(() => window.splashmxState?.());
    if (state && predicate(state)) return state;
    await page.waitForTimeout(40);
  }
  throw new Error(`Timed out waiting for ${label}`);
}

function thing(state, id) {
  return state.canonical.things.find((row) => row.thing_id === id);
}
function children(state, rootId) {
  return state.canonical.things.filter((row) => row.parent_thing_id === rootId);
}

const evidence = {
  schema: "splashmx.smx051e-grouping-library-evidence/1",
  issue: "SMX-051E",
  checks: {},
  browser: {},
  godot: { ready: null },
};
await fs.mkdir(path.dirname(OUT), { recursive: true });
await fs.rm(STORE, { force: true });
await fs.rm(`${STORE}.collaboration.sqlite3`, { force: true });

let server = await startServer();
let browser;
try {
  browser = await chromium.launch({ headless: true });
  evidence.browser = { product: await browser.version(), playwright: "1.55.0", headless: true };
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const consoleLines = [];
  page.on("console", (message) => {
    const text = message.text();
    consoleLines.push(text);
    if (text.startsWith("SMX051C_PLAY_READY=")) {
      evidence.godot.ready = JSON.parse(text.slice("SMX051C_PLAY_READY=".length));
    } else if (text.startsWith("SMX038_ERROR=")) {
      evidence.godot.error = text;
    }
  });
  const pageErrors = [];
  page.on("pageerror", (error) => pageErrors.push(String(error?.stack || error)));

  await page.goto(server.baseURL, { waitUntil: "networkidle" });
  let state = await waitForState(page, (value) => value.godot_player?.available === true, "Godot-backed editor");

  await page.locator("#new-label").fill("First");
  await page.getByTestId("create-thing").click();
  state = await waitForState(page, (value) => value.canonical.things.length === 1, "first Thing");
  const first = state.canonical.things[0].thing_id;

  await page.locator("#new-label").fill("Second");
  await page.getByTestId("create-thing").click();
  state = await waitForState(page, (value) => value.canonical.things.length === 2, "second Thing");
  const second = state.canonical.things.find((row) => row.label === "Second").thing_id;
  const originalIds = [first, second].sort();
  const firstInitial = structuredClone(thing(state, first).authored_state.visual);
  const secondInitial = structuredClone(thing(state, second).authored_state.visual);

  await page.locator(`[data-testid="select-${first}"]`).check();
  state = await waitForState(page, (value) => value.editor.selection.length === 2, "multi-select");
  await page.getByTestId("group-selected").click();
  state = await waitForState(page, (value) => value.canonical.things.length === 3 && value.editor.selection.length === 1, "visible group");
  let group = state.editor.selection[0];
  assert.deepEqual(children(state, group).map((row) => row.thing_id).sort(), originalIds);
  assert.equal(await page.getByTestId(`group-outline-${group}`).isVisible(), true);
  evidence.checks.visible_group_and_stable_children = true;

  await page.getByTestId(`group-caption-${group}`).focus();
  await page.keyboard.press("ArrowRight");
  state = await waitForState(page, (value) =>
    thing(value, first)?.authored_state?.visual?.x === firstInitial.x + 5 &&
    thing(value, second)?.authored_state?.visual?.x === secondInitial.x + 5,
  "keyboard group transform");
  evidence.checks.coherent_group_transform = true;

  await page.getByTestId("ungroup-selected").click();
  state = await waitForState(page, (value) =>
    value.canonical.things.length === 2 &&
    value.editor.selection.length === 2 &&
    thing(value, first)?.parent_thing_id === null &&
    thing(value, second)?.parent_thing_id === null,
  "Ungroup");
  assert.deepEqual(state.canonical.things.map((row) => row.thing_id).sort(), originalIds);
  evidence.checks.ungroup_preserves_children = true;

  await page.keyboard.press("Control+g");
  state = await waitForState(page, (value) => value.canonical.things.length === 3 && value.editor.selection.length === 1, "keyboard Group");
  group = state.editor.selection[0];
  assert.deepEqual(children(state, group).map((row) => row.thing_id).sort(), originalIds);
  evidence.checks.keyboard_group_equivalent = true;

  await page.getByTestId(`stage-thing-${first}`).click();
  state = await waitForState(page, (value) => value.editor.selection.length === 1 && value.editor.selection[0] === first, "first child selection");
  await page.getByTestId("add-rule").click();
  state = await waitForState(page, (value) => thing(value, first)?.behaviours?.length === 1, "Rule before promotion");
  const originalRuleId = thing(state, first).behaviours[0].attachment_id;

  const timelineStart = thing(state, first).authored_state.visual.x;
  await page.locator('#timeline-form select[name="property"]').selectOption("visual.x");
  await page.locator('#timeline-form input[name="start"]').fill(String(timelineStart));
  await page.locator('#timeline-form input[name="end"]').fill(String(timelineStart + 100));
  await page.locator('#timeline-form input[name="duration"]').fill("60");
  await page.getByTestId("add-timeline").click();
  state = await waitForState(page, (value) => Array.isArray(thing(value, first)?.authored_state?.timeline_tracks), "Timeline before promotion");

  await page.getByTestId(`group-caption-${group}`).click();
  state = await waitForState(page, (value) => value.editor.selection[0] === group, "group selection before reusable");
  await page.getByTestId("make-reusable").click();
  state = await waitForState(page, (value) => value.canonical.definitions.length === 1, "Library entry");
  const definitionId = state.canonical.definitions[0].definition_id;
  assert.equal(state.canonical.definitions[0].root_thing_id, group);
  assert.deepEqual(children(state, group).map((row) => row.thing_id).sort(), originalIds);
  assert.equal(await page.getByTestId("library-item").isVisible(), true);
  assert.match(await page.getByTestId("library-item").innerText(), /1 instance/);
  assert.equal((await page.getByTestId(`group-caption-${group}`).innerText()).includes("Reusable"), true);
  evidence.checks.make_reusable_has_immediate_library_feedback = true;

  await page.getByTestId("library-add-instance").click();
  state = await waitForState(page, (value) =>
    value.canonical.definitions.filter((row) => row.definition_id === definitionId).length === 2 &&
    value.canonical.things.length === 6,
  "second instance");
  const definitionRows = state.canonical.definitions.filter((row) => row.definition_id === definitionId);
  const secondRoot = definitionRows.find((row) => row.root_thing_id !== group).root_thing_id;
  assert.notEqual(secondRoot, group);
  const secondChildren = children(state, secondRoot);
  assert.equal(secondChildren.length, 2);
  assert.equal(secondChildren.some((row) => originalIds.includes(row.thing_id)), false);
  const copiedFirst = secondChildren.find((row) => row.label === "First");
  assert(copiedFirst);
  const copiedTrack = copiedFirst.authored_state.timeline_tracks[0];
  assert.equal(copiedTrack.target_thing_id, copiedFirst.thing_id);
  assert.equal(copiedTrack.keyframes[0].value, timelineStart + 48);
  assert.match(await page.getByTestId("library-item").innerText(), /2 instances/);
  evidence.checks.second_instance_has_new_identity_and_definition_linkage = true;
  evidence.checks.timeline_target_is_instance_local = true;

  const firstBeforeIndependentMove = thing(state, first).authored_state.visual.x;
  const copyBeforeIndependentMove = thing(state, copiedFirst.thing_id).authored_state.visual.x;
  await page.getByTestId(`group-caption-${group}`).focus();
  await page.keyboard.press("ArrowRight");
  state = await waitForState(page, (value) => thing(value, first)?.authored_state?.visual?.x === firstBeforeIndependentMove + 5, "first instance move");
  assert.equal(thing(state, copiedFirst.thing_id).authored_state.visual.x, copyBeforeIndependentMove);

  const originalY = thing(state, first).authored_state.visual.y;
  const copyY = thing(state, copiedFirst.thing_id).authored_state.visual.y;
  await page.getByTestId(`group-caption-${secondRoot}`).focus();
  await page.keyboard.press("ArrowDown");
  state = await waitForState(page, (value) => thing(value, copiedFirst.thing_id)?.authored_state?.visual?.y === copyY + 5, "second instance move");
  assert.equal(thing(state, first).authored_state.visual.y, originalY);
  evidence.checks.instances_are_independently_manipulable = true;

  await page.getByTestId("save").click();
  state = await waitForState(page, (value) => value.storage?.saved_revision_id === value.canonical.project_revision_id, "Save");
  const savedRevision = state.canonical.project_revision_id;
  const savedIds = state.canonical.things.map((row) => row.thing_id).sort();

  await page.getByTestId("reload").click();
  state = await waitForState(page, (value) => value.canonical.project_revision_id === savedRevision && value.canonical.definitions.length === 2, "Save Reload");
  assert.deepEqual(state.canonical.things.map((row) => row.thing_id).sort(), savedIds);
  assert.equal(thing(state, first).behaviours[0].attachment_id, originalRuleId);
  evidence.checks.save_reload_preserves_reuse = true;
  evidence.checks.rule_path_preserved = true;

  await stopServer(server.child);
  server = await startServer();
  await page.goto(server.baseURL, { waitUntil: "networkidle" });
  state = await waitForState(page, (value) =>
    value.godot_player?.available === true &&
    value.canonical.definitions.filter((row) => row.definition_id === definitionId).length === 2,
  "process restart");
  assert.deepEqual(state.canonical.things.map((row) => row.thing_id).sort(), savedIds);
  assert.match(await page.getByTestId("library-item").innerText(), /2 instances/);
  assert.equal(await page.getByTestId(`group-outline-${group}`).isVisible(), true);
  assert.equal(await page.getByTestId(`group-outline-${secondRoot}`).isVisible(), true);
  evidence.checks.process_restart_preserves_reuse = true;

  evidence.godot.ready = null;
  delete evidence.godot.error;
  const playRevision = state.canonical.project_revision_id;
  const visibleIds = state.canonical.things.filter((row) => row.authored_state?.visual).map((row) => row.thing_id).sort();
  await page.getByTestId("play").click();
  state = await waitForState(page, (value) => value.runtime.mode === "play", "Godot Play");
  const frame = page.frameLocator("#godot-player");
  await frame.locator("canvas").waitFor({ state: "visible", timeout: 60_000 });
  const deadline = Date.now() + 60_000;
  while (!evidence.godot.ready && Date.now() < deadline) {
    if (evidence.godot.error) throw new Error(evidence.godot.error);
    await page.waitForTimeout(60);
  }
  assert(evidence.godot.ready, `Godot ready evidence missing; console=${consoleLines.join("\n")}`);
  assert.equal(evidence.godot.ready.contract, "splashmx.editor-godot-play-ready/1");
  assert.equal(evidence.godot.ready.project_revision_id, playRevision);
  assert.deepEqual([...evidence.godot.ready.thing_ids].sort(), visibleIds);

  const projectionResponse = await page.request.get(`${server.baseURL}/api/godot-play-projection`);
  assert.equal(projectionResponse.ok(), true);
  const projection = (await projectionResponse.json()).projection;
  assert.equal(projection.things.length, visibleIds.length);
  const projectedCopy = projection.things.find((row) => row.thing_id === copiedFirst.thing_id);
  assert(projectedCopy);
  assert.equal(projectedCopy.timeline_tracks[0].property, "visual.x");
  const projectedOriginal = projection.things.find((row) => row.thing_id === first);
  assert(projectedOriginal.interactive_events.includes("pointer_click"));
  evidence.checks.real_godot_projects_both_instances = true;
  evidence.checks.timeline_rule_and_play_paths_intact = true;

  await page.getByTestId("stop").click();
  state = await waitForState(page, (value) => value.runtime.mode === "edit", "Stop");
  assert.equal(state.canonical.project_revision_id, playRevision);
  assert.deepEqual(pageErrors, []);
  evidence.checks.stop_returns_to_authored_instances = true;

  evidence.final = {
    project_revision_id: state.canonical.project_revision_id,
    definition_id: definitionId,
    first_root_thing_id: group,
    second_root_thing_id: secondRoot,
    concrete_thing_ids: savedIds,
    godot_thing_ids: evidence.godot.ready.thing_ids,
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
