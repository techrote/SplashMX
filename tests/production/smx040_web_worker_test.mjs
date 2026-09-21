import assert from "node:assert/strict";
import fs from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "../..");
const workerPath = path.join(root, "src/splashmx/security/web/decoder_worker.mjs");
const profilePath = path.join(root, "src/splashmx/security/web/hardened-web-profile.json");
const worker = await import(`file://${workerPath}`);
const profile = JSON.parse(fs.readFileSync(profilePath, "utf8"));

assert.equal(profile.contract, "splashmx.hardened-web-decoder-profile/1");
assert.match(profile.csp, /connect-src 'none'/);
assert.match(profile.csp, /worker-src 'self'/);
assert.equal(profile.godot_build_attestation.javascript_bridge, false);
assert.equal(profile.godot_build_attestation.module_javascript_enabled, false);
assert.equal(profile.worker.maximum_linear_memory_bytes, 256 * 1024 * 1024);
assert.deepEqual(profile.worker.wasm_imports, ["env.memory"]);

assert.throws(
  () => worker.rejectTransientAuthority({ nested: [{ Capability_Grant: "forged" }] }),
  /security\.serialized_authority/,
);

const good = {
  type: "decode",
  request_id: "req-1",
  asset_id: "asset:web",
  revision_digest: "revision-1",
  source_digest: "digest",
  source: new ArrayBuffer(16),
  predicted_decoded_bytes: 32,
  image_pixels: 4,
  audio_frames: 0,
  derivative_kind: "rgba8",
  derivative_version: "1",
  metadata: { width: 2, height: 2 },
};
assert.equal(worker.validateDecodeMessage(good), good);
assert.throws(
  () => worker.validateDecodeMessage({ ...good, predicted_decoded_bytes: worker.MAX_DECODED_BYTES + 1 }),
  /security\.decoder_budget/,
);
assert.equal(worker.MAX_WASM_PAGES * 65536, 256 * 1024 * 1024);

const source = fs.readFileSync(workerPath, "utf8");
for (const forbidden of ["fetch(", "importScripts(", "eval("]) {
  assert.equal(source.includes(forbidden), false, `worker source contains forbidden ambient bridge ${forbidden}`);
}

console.log("SMX-040 hardened browser worker contract: OK");
