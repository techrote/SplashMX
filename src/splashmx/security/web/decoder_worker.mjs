// SMX-040 hardened browser decoder worker boundary.
// This module is trusted runtime code. Ordinary content supplies only bounded bytes
// and descriptors; it never supplies JavaScript, host objects, URLs or imports.

export const MAX_SOURCE_BYTES = 64 * 1024 * 1024;
export const MAX_DECODED_BYTES = 256 * 1024 * 1024;
export const MAX_WASM_PAGES = MAX_DECODED_BYTES / 65536;
export const MAX_METADATA_DEPTH = 32;
export const MAX_METADATA_NODES = 4096;

const FORBIDDEN = new Set([
  "nodepath", "rid", "resourceuid", "resourcepath", "domnodeidentity",
  "databaserowid", "cachekey", "transportpeerid", "connectionhandle",
  "socketid", "sessionid", "processhandle", "hosthandle", "hostobject",
  "capabilitytoken", "capabilitygrant", "grantid", "delegationgrant",
  "nativehandle", "peerid", "loaderauthority"
]);

function normalizeField(value) {
  return value.toLowerCase().replace(/[^a-z0-9]/g, "");
}

export function rejectTransientAuthority(value) {
  let nodes = 0;
  const walk = (item, depth) => {
    nodes += 1;
    if (nodes > MAX_METADATA_NODES || depth > MAX_METADATA_DEPTH) {
      throw new Error("security.message_budget");
    }
    if (item === null || typeof item === "boolean" || typeof item === "number") return;
    if (typeof item === "string") {
      if (new TextEncoder().encode(item).byteLength > 256 * 1024) throw new Error("security.message_budget");
      return;
    }
    if (item instanceof Uint8Array || item instanceof ArrayBuffer) return;
    if (Array.isArray(item)) {
      for (const child of item) walk(child, depth + 1);
      return;
    }
    if (typeof item === "object") {
      for (const [key, child] of Object.entries(item)) {
        if (FORBIDDEN.has(normalizeField(key))) throw new Error("security.serialized_authority");
        walk(child, depth + 1);
      }
      return;
    }
    throw new Error("security.message_type");
  };
  walk(value, 0);
}

export function validateDecodeMessage(message) {
  rejectTransientAuthority(message);
  const expected = [
    "type", "request_id", "asset_id", "revision_digest", "source_digest",
    "source", "predicted_decoded_bytes", "image_pixels", "audio_frames",
    "derivative_kind", "derivative_version", "metadata"
  ].sort();
  const keys = Object.keys(message).sort();
  if (JSON.stringify(keys) !== JSON.stringify(expected) || message.type !== "decode") {
    throw new Error("security.decoder_request_schema");
  }
  if (!(message.source instanceof ArrayBuffer)) throw new Error("security.decoder_request_type");
  if (message.source.byteLength > MAX_SOURCE_BYTES) throw new Error("security.decoder_budget");
  if (!Number.isSafeInteger(message.predicted_decoded_bytes) || message.predicted_decoded_bytes < 0 || message.predicted_decoded_bytes > MAX_DECODED_BYTES) {
    throw new Error("security.decoder_budget");
  }
  for (const [value, max] of [[message.image_pixels, 8192 * 8192], [message.audio_frames, 57600000]]) {
    if (!Number.isSafeInteger(value) || value < 0 || value > max) throw new Error("security.decoder_budget");
  }
  return message;
}

export function instantiateDecoder(module) {
  if (!(module instanceof WebAssembly.Module)) throw new Error("security.decoder_module_type");
  const imports = WebAssembly.Module.imports(module);
  if (imports.length !== 1 || imports[0].module !== "env" || imports[0].name !== "memory" || imports[0].kind !== "memory") {
    throw new Error("security.decoder_import_surface");
  }
  const memory = new WebAssembly.Memory({ initial: 1, maximum: MAX_WASM_PAGES });
  const instance = new WebAssembly.Instance(module, { env: { memory } });
  if (typeof instance.exports.decode !== "function") throw new Error("security.decoder_export_surface");
  return { instance, memory };
}

// Codec ABIs are registered by trusted runtime code. Until a concrete pinned
// memory-safe decoder module is registered, public decode fails closed.
let trustedDecoder = null;
export function registerTrustedDecoder(module) {
  trustedDecoder = instantiateDecoder(module);
}

async function handleDecode(message) {
  validateDecodeMessage(message);
  if (trustedDecoder === null) throw new Error("security.decoder_codec_unregistered");
  throw new Error("security.decoder_codec_abi_unimplemented");
}

if (typeof self !== "undefined" && typeof self.addEventListener === "function") {
  self.addEventListener("message", async (event) => {
    const requestId = event?.data?.request_id ?? null;
    try {
      const result = await handleDecode(event.data);
      self.postMessage({ type: "result", request_id: requestId, result });
    } catch (error) {
      const code = error instanceof Error && /^security\./.test(error.message) ? error.message : "security.decoder_failed";
      self.postMessage({ type: "failure", request_id: requestId, code });
    }
  });
}
