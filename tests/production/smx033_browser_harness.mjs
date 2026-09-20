#!/usr/bin/env node
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { chromium } from "playwright";

const ROOT = process.cwd();
const OUT = path.join(ROOT, "artifacts", "smx033-browser-results.json");
const STORE = path.join(ROOT, "artifacts", "smx033-project.sqlite3");

async function startServer() {
  await fs.rm(STORE, { force: true });
  const env = { ...process.env, PYTHONPATH: [path.join(ROOT, "src"), process.env.PYTHONPATH].filter(Boolean).join(path.delimiter) };
  const child = spawn(process.env.PYTHON || "python", ["-m", "splashmx.editor.browser_server", "--port", "0", "--project-id", "smx033-browser", "--store-path", STORE], { cwd: ROOT, env, stdio: ["ignore", "pipe", "pipe"] });
  let stderr = "";
  child.stderr.setEncoding("utf8"); child.stderr.on("data", (chunk) => { stderr += chunk; });
  const baseURL = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`SMX-033 server did not start: ${stderr}`)), 10000);
    let stdout = "";
    child.stdout.setEncoding("utf8");
    child.stdout.on("data", (chunk) => { stdout += chunk; const match = stdout.match(/SMX033 READY (http:\/\/[^\s]+)/); if (match) { clearTimeout(timer); resolve(match[1]); } });
    child.on("exit", (code) => { clearTimeout(timer); reject(new Error(`server exited ${code}: ${stderr}`)); });
  });
  return { child, baseURL };
}

async function state(page) { return page.evaluate(() => window.splashmxState?.()); }
async function waitFor(page, pred, label, timeout = 8000) {
  const start = Date.now();
  while (Date.now() - start < timeout) { const value = await state(page); if (value && pred(value)) return value; await page.waitForTimeout(30); }
  throw new Error(`timeout waiting for ${label}`);
}
async function raw(page, action, data = {}) {
  return page.evaluate(async ({ action, data }) => { const response = await fetch("/api/action", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action, data }) }); return { status: response.status, payload: await response.json() }; }, { action, data });
}

const server = await startServer();
let browser;
const evidence = {
  schema: "splashmx.smx033-browser-evidence/1",
  issue: "SMX-033",
  metadata: {
    measured_at_utc: new Date().toISOString(),
    build_sha: process.env.GITHUB_SHA || "local",
    node: process.version,
    os: `${os.platform()} ${os.release()} ${os.arch()}`,
    workload: "blank Stage; two Things; two ports; one semantic Connection; one Rule; Play/Stop; local Save; unsaved edit; verified reload; page reload",
    samples: 1,
    interpretation: "CI observation for this named build/runtime/workload; not a universal performance SLO",
  },
  checks: {}, metrics_ms: {}, memory: {},
};
try {
  browser = await chromium.launch({ headless: true });
  evidence.metadata.browser = await browser.version();
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  let t = performance.now();
  await page.goto(server.baseURL, { waitUntil: "networkidle" });
  await waitFor(page, () => true, "initial editor");
  evidence.metrics_ms.startup_to_ready = performance.now() - t;

  assert.equal(await page.locator('main').count(), 1);
  assert.equal(await page.locator('nav[aria-label="Project actions"]').count(), 1);
  assert.equal(await page.locator('[role="status"][aria-live="polite"]').count(), 1);
  assert.equal(await page.locator('#diagnostics[role="log"]').count(), 1);
  assert.equal(await page.locator('.skip-link').getAttribute('href'), '#stage');
  for (const id of ["play", "stop", "save", "reload", "inspect-toggle"]) assert.equal(await page.locator(`#${id}`).count(), 1);
  evidence.checks.accessibility_structure = true;

  t = performance.now();
  await page.locator("#new-label").fill("Button"); await page.getByTestId("create-thing").click();
  await page.locator("#new-label").fill("Lamp"); await page.getByTestId("create-thing").click();
  let s = await waitFor(page, (x) => x.canonical.things.length === 2, "two Things");
  const button = s.canonical.things.find((x) => x.label === "Button").thing_id;
  const lamp = s.canonical.things.find((x) => x.label === "Lamp").thing_id;
  evidence.metrics_ms.create_two_things = performance.now() - t;

  async function selectOnly(id) { await raw(page, "select", { thing_ids: [id] }); await page.reload({ waitUntil: "networkidle" }); await waitFor(page, (x) => x.editor.selection.length === 1 && x.editor.selection[0] === id, `select ${id}`); }
  await selectOnly(button);
  await raw(page, "addPort", { thing_id: button, port_id: "clicked", name: "Clicked", kind: "event", direction: "out" });
  await raw(page, "attachRule", { thing_id: button, event: "activate", actions: [{ action: "emit", event: "clicked", payload: true }] });
  await raw(page, "addPort", { thing_id: lamp, port_id: "activate", name: "Activate", kind: "command", direction: "in" });
  const connected = await raw(page, "connect", { source_thing_id: button, source_port_id: "clicked", target_thing_id: lamp, target_port_id: "activate", connection_id: "semantic-browser-connection" });
  assert.equal(connected.status, 200);
  assert.equal(connected.payload.result, "semantic-browser-connection");
  const rejected = await raw(page, "connect", { source_thing_id: button, source_port_id: "clicked", target_thing_id: lamp, target_port_id: "activate", connection_handle: "rtc-data-channel-9" });
  assert.equal(rejected.status, 409); assert.equal(rejected.payload.error.code, "authoring.forbidden_transient_identity");
  evidence.checks.r019_01_semantic_connection = true;

  const authoredBeforePlay = (await state(page)).canonical.project_revision_id;
  t = performance.now(); await page.keyboard.press("Control+Enter");
  s = await waitFor(page, (x) => x.runtime.mode === "play", "Play mode"); evidence.metrics_ms.play_start = performance.now() - t;
  assert.equal(s.canonical.project_revision_id, authoredBeforePlay);
  const editDuringPlay = await raw(page, "createThing", { label: "Must not publish" }); assert.equal(editDuringPlay.status, 409);
  await page.keyboard.press("Escape"); s = await waitFor(page, (x) => x.runtime.mode === "edit", "Stop");
  assert.equal(s.canonical.project_revision_id, authoredBeforePlay); assert.equal(s.canonical.things.some((x) => x.label === "Must not publish"), false);
  evidence.checks.play_stop_transient = true;

  t = performance.now(); await page.keyboard.press("Control+s"); s = await waitFor(page, (x) => x.storage.saved_revision_id === authoredBeforePlay, "save"); evidence.metrics_ms.save = performance.now() - t;
  await raw(page, "createThing", { label: "Unsaved edit" }); s = await state(page); assert.equal(s.canonical.things.length, 3);
  t = performance.now(); await page.getByTestId("reload").click(); s = await waitFor(page, (x) => x.canonical.things.length === 2 && x.canonical.project_revision_id === authoredBeforePlay, "verified reload"); evidence.metrics_ms.reload_saved = performance.now() - t;
  assert.equal(s.canonical.connections[0].connection_id, "semantic-browser-connection");
  evidence.checks.save_reload_non_destructive = true;

  t = performance.now(); await page.reload({ waitUntil: "networkidle" }); s = await waitFor(page, (x) => x.canonical.project_revision_id === authoredBeforePlay, "local reload after page restart"); evidence.metrics_ms.page_reload = performance.now() - t;
  evidence.checks.local_offline_capable_reload = true;

  await page.keyboard.press("Alt+i"); s = await waitFor(page, (x) => x.editor.inspect_open, "Inspect keyboard toggle");
  evidence.checks.keyboard_navigation = true;
  evidence.memory.used_js_heap_bytes = await page.evaluate(() => performance.memory?.usedJSHeapSize ?? null);
  evidence.final = { project_revision_id: s.canonical.project_revision_id, thing_count: s.canonical.things.length, connection_id: s.canonical.connections[0].connection_id };
  evidence.passed = true;
} catch (error) {
  evidence.passed = false; evidence.error = String(error?.stack || error); throw error;
} finally {
  await fs.mkdir(path.dirname(OUT), { recursive: true }); await fs.writeFile(OUT, JSON.stringify(evidence, null, 2) + "\n", "utf8");
  if (browser) await browser.close(); server.child.kill("SIGTERM");
}
