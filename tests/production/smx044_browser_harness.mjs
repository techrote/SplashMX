#!/usr/bin/env node
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { chromium } from "playwright";

const ROOT = process.cwd();
const OUT = path.join(ROOT, "artifacts", "smx044-browser-results.json");
const STORE = path.join(ROOT, "artifacts", "smx044-project.sqlite3");
const COLLAB = `${STORE}.collaboration.sqlite3`;

async function removeStore() {
  for (const base of [STORE, COLLAB]) for (const suffix of ["", "-wal", "-shm"]) await fs.rm(base + suffix, { force: true });
}
async function startServer(clean = false) {
  if (clean) await removeStore();
  const env = { ...process.env, PYTHONPATH: [path.join(ROOT, "src"), process.env.PYTHONPATH].filter(Boolean).join(path.delimiter) };
  const child = spawn(process.env.PYTHON || "python", ["-m", "splashmx.editor.browser_server", "--port", "0", "--project-id", "smx044-browser", "--store-path", STORE], { cwd: ROOT, env, stdio: ["ignore", "pipe", "pipe"] });
  let stderr = ""; child.stderr.setEncoding("utf8"); child.stderr.on("data", (chunk) => { stderr += chunk; });
  const baseURL = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`SMX-044 server did not start: ${stderr}`)), 10000); let stdout = ""; child.stdout.setEncoding("utf8");
    child.stdout.on("data", (chunk) => { stdout += chunk; const match = stdout.match(/SMX044 READY (http:\/\/[^\s]+)/); if (match) { clearTimeout(timer); resolve(match[1]); } });
    child.on("exit", (code) => { clearTimeout(timer); reject(new Error(`server exited ${code}: ${stderr}`)); });
  });
  return { child, baseURL };
}
async function stopServer(child) { const exited = new Promise((resolve) => child.once("exit", resolve)); child.kill("SIGTERM"); await Promise.race([exited, new Promise((resolve) => setTimeout(resolve, 3000))]); }
async function state(page) { return page.evaluate(() => window.splashmxState?.()); }
async function waitFor(page, pred, label, timeout = 8000) { const start = Date.now(); while (Date.now() - start < timeout) { const value = await state(page); if (value && pred(value)) return value; await page.waitForTimeout(25); } throw new Error(`timeout waiting for ${label}`); }
async function raw(page, action, data = {}) { return page.evaluate(async ({ action, data }) => { const response = await fetch("/api/action", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action, data }) }); return { status: response.status, payload: await response.json() }; }, { action, data }); }

let server = await startServer(true); let browser;
const evidence = { schema: "splashmx.smx044-browser-evidence/1", issue: "SMX-044", metadata: { measured_at_utc: new Date().toISOString(), build_sha: process.env.GITHUB_SHA || "local", node: process.version, os: `${os.platform()} ${os.release()} ${os.arch()}`, workload: "People/Together separation; local edit to collaboration history; transient presence; process restart recovery", samples: 1, interpretation: "CI observation for this named build/runtime/workload; not a universal performance SLO" }, checks: {}, metrics_ms: {} };
try {
  browser = await chromium.launch({ headless: true }); evidence.metadata.browser = await browser.version(); const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  let t = performance.now(); await page.goto(server.baseURL, { waitUntil: "networkidle" }); let s = await waitFor(page, (x) => x.people && x.together, "People state"); evidence.metrics_ms.startup_to_people = performance.now() - t;
  assert.equal(await page.locator('#people-panel[data-plane="collaboration"]').count(), 1); assert.equal(await page.locator('#together-boundary[data-plane="runtime-networking"]').count(), 1); assert.equal(await page.locator('#people-panel #together-boundary').count(), 0); assert.equal(s.people.plane, "collaboration"); assert.equal(s.together.plane, "runtime-networking"); assert.equal(s.together.available, false); evidence.checks.people_together_separation = true;
  t = performance.now(); await page.locator("#new-label").fill("Local work"); await page.getByTestId("create-thing").click(); s = await waitFor(page, (x) => x.canonical.things.length === 1 && x.people.head_revision_id === x.canonical.project_revision_id, "local People history"); evidence.metrics_ms.local_edit_to_people = performance.now() - t; evidence.checks.local_first_history = true;
  const authored = s.canonical.project_revision_id;
  await page.locator("#presence-cursor").fill("Editing Stage"); await page.getByTestId("set-presence").click(); s = await waitFor(page, (x) => x.people.presence.length === 1, "transient presence"); assert.equal(s.people.presence[0].cursor, "Editing Stage"); evidence.checks.presence_projection = true;
  const missing = await raw(page, "peopleResolveConflict", { conflict_id: "conflict-missing", choice: "current" }); assert.equal(missing.status, 409); assert.equal(missing.payload.error.code, "people.unknown_conflict"); evidence.checks.explicit_resolution_boundary = true;
  await stopServer(server.child); server = await startServer(false); t = performance.now(); await page.goto(server.baseURL, { waitUntil: "networkidle" }); s = await waitFor(page, (x) => x.canonical.project_revision_id === authored, "collaboration restart recovery"); evidence.metrics_ms.restart_recovery = performance.now() - t; assert.equal(s.canonical.things[0].label, "Local work"); assert.equal(s.people.presence.length, 0); evidence.checks.restart_retains_authored_not_presence = true;
  evidence.final = { project_revision_id: s.canonical.project_revision_id, people_head_revision_id: s.people.head_revision_id, conflict_count: s.people.conflicts.length }; evidence.passed = true;
} catch (error) { evidence.passed = false; evidence.error = String(error?.stack || error); throw error; }
finally { await fs.mkdir(path.dirname(OUT), { recursive: true }); await fs.writeFile(OUT, JSON.stringify(evidence, null, 2) + "\n", "utf8"); if (browser) await browser.close(); if (server?.child && !server.child.killed) await stopServer(server.child); }
