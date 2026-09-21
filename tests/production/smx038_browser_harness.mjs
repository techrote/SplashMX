import fs from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright";

const root = path.resolve(new URL("../..", import.meta.url).pathname);
const outPath = path.join(root, "artifacts", "smx038-browser-evidence.json");
const url = process.env.SMX038_URL || "http://127.0.0.1:8128/";

const forbidden = new Set([
  "NodePath", "RID", "ResourceUID", "resource_path", "DOM_node_identity",
  "database_row_id", "cache_key", "url", "transport_peer_id",
  "connection_handle", "socket_id", "session_id", "process_handle",
  "instance_id", "godot_object_id",
]);

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function walkKeys(value) {
  const keys = [];
  if (Array.isArray(value)) {
    for (const item of value) keys.push(...walkKeys(item));
  } else if (value && typeof value === "object") {
    for (const [key, child] of Object.entries(value)) {
      keys.push(key);
      keys.push(...walkKeys(child));
    }
  }
  return keys;
}

await fs.mkdir(path.dirname(outPath), { recursive: true });
const browser = await chromium.launch({ headless: true });
let evidence = null;
const consoleLines = [];
try {
  const page = await browser.newPage({ viewport: { width: 640, height: 360 } });
  page.on("console", (message) => {
    const text = message.text();
    consoleLines.push(text);
    if (text.startsWith("SMX038_RESULT=")) {
      evidence = JSON.parse(text.slice("SMX038_RESULT=".length));
    }
    if (text.startsWith("SMX038_ERROR=")) {
      throw new Error(text);
    }
  });
  await page.goto(url, { waitUntil: "load", timeout: 60_000 });
  const deadline = Date.now() + 60_000;
  while (evidence === null && Date.now() < deadline) {
    await page.waitForTimeout(100);
  }
  assert(evidence !== null, `SMX-038 result not observed; console=${consoleLines.join("\n")}`);
  assert(evidence.contract === "splashmx.smx038-godot-profile-evidence/1", "browser evidence contract mismatch");
  assert(evidence.profile === "browser", `expected browser profile, got ${evidence.profile}`);
  assert(evidence.frame_samples === 30, "browser frame sample count mismatch");
  assert(evidence.active_features.includes("render_2d"), "browser render profile missing");
  assert(evidence.active_features.includes("physics_2d"), "browser physics profile missing");
  assert(evidence.active_features.includes("audio_basic"), "browser audio profile missing");
  assert(evidence.active_features.includes("input"), "browser input profile missing");
  assert(evidence.protected_asset_refs.length === 1, "browser protected Asset reference missing");
  for (const [name, passed] of Object.entries(evidence.boundary_results)) {
    assert(passed === true, `browser boundary failed: ${name}`);
  }
  for (const [name, passed] of Object.entries(evidence.adapter_results)) {
    assert(passed === true, `browser adapter failed: ${name}`);
  }
  for (const [name, passed] of Object.entries(evidence.derivative_results)) {
    assert(passed === true, `browser derivative boundary failed: ${name}`);
  }
  const leaked = walkKeys(evidence).filter((key) => forbidden.has(key));
  assert(leaked.length === 0, `browser evidence leaked transient identity keys: ${leaked}`);
  evidence.browser = {
    product: await browser.version(),
    playwright: "1.55.0",
    headless: true,
  };
  evidence.source_url = url;
  evidence.console_line_count = consoleLines.length;
  await fs.writeFile(outPath, `${JSON.stringify(evidence, null, 2)}\n`, "utf8");
  console.log(JSON.stringify(evidence));
} finally {
  await browser.close();
}
