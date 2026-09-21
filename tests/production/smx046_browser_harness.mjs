#!/usr/bin/env node
import fs from "node:fs/promises";
import http from "node:http";
import path from "node:path";
import { chromium } from "playwright";

const root = process.argv[2] || process.cwd();
const moduleBytes = await fs.readFile(path.join(root, "src/splashmx/runtime/web/network_transport.mjs"));
const server = http.createServer((req, res) => {
  if (req.url === "/network_transport.mjs") {
    res.writeHead(200, { "content-type": "text/javascript", "cache-control": "no-store" });
    res.end(moduleBytes);
    return;
  }
  res.writeHead(200, { "content-type": "text/html" });
  res.end("<!doctype html><meta charset=utf-8><title>SMX-046 browser transport</title>");
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const { port } = server.address();

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
await page.goto(`http://127.0.0.1:${port}/`);
const result = await page.evaluate(async () => {
  const { BrowserRuntimeTransport } = await import("/network_transport.mjs");
  const a = new BrowserRuntimeTransport();
  const b = new BrowserRuntimeTransport();
  const aCandidates = [], bCandidates = [];
  let aRemoteReady = false, bRemoteReady = false;
  await a.openPeer({ initiator: true });
  await b.openPeer({ initiator: false });
  a.onIceCandidate((candidate) => {
    if (!candidate) return;
    if (bRemoteReady) void b.addIceCandidate(candidate); else aCandidates.push(candidate);
  });
  b.onIceCandidate((candidate) => {
    if (!candidate) return;
    if (aRemoteReady) void a.addIceCandidate(candidate); else bCandidates.push(candidate);
  });

  const received = [];
  b.onSemantic((value) => received.push(value));
  const started = performance.now();
  const offer = await a.makeOffer();
  const answer = await b.acceptOffer(offer);
  bRemoteReady = true;
  for (const candidate of aCandidates.splice(0)) await b.addIceCandidate(candidate);
  await a.acceptAnswer(answer);
  aRemoteReady = true;
  for (const candidate of bCandidates.splice(0)) await a.addIceCandidate(candidate);

  const openDeadline = performance.now() + 10000;
  while ((a.readyState !== "open" || b.readyState !== "open") && performance.now() < openDeadline) {
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
  if (a.readyState !== "open" || b.readyState !== "open") throw new Error("network.transport_unavailable: DataChannel did not open");
  const establishedMs = performance.now() - started;

  const envelope = {
    message_id: "browser-1", message_class: "input", sender_session_id: "session:alice",
    authority_epoch: 1, sequence: 1, target_thing_id: "avatar", locus: "move", payload: { axis: 1 }
  };
  const sendStart = performance.now();
  a.sendSemantic(envelope);
  const receiveDeadline = performance.now() + 5000;
  while (received.length === 0 && performance.now() < receiveDeadline) {
    await new Promise((resolve) => setTimeout(resolve, 5));
  }
  if (received.length !== 1 || received[0].message_id !== "browser-1") throw new Error("semantic envelope not delivered once");
  const loopbackMs = performance.now() - sendStart;

  let authorityRejected = false;
  try {
    a.sendSemantic({ ...envelope, message_id: "forged", sequence: 2, payload: { nested: { capability_grant: "ambient" } } });
  } catch (error) {
    authorityRejected = String(error).includes("network.auth_rejected");
  }
  if (!authorityRejected) throw new Error("recursive authority injection was not rejected before DataChannel send");

  let oversizeRejected = false;
  try {
    a.sendSemantic({ ...envelope, message_id: "huge", sequence: 2, payload: { blob: "x".repeat(70000) } });
  } catch (error) {
    oversizeRejected = String(error).includes("network.message_oversize");
  }
  if (!oversizeRejected) throw new Error("oversized runtime message was not rejected before DataChannel send");

  let tlsRejected = false;
  try {
    await a.connectDedicatedWss({ url: "ws://127.0.0.1:1/", joinTicket: "ticket", sessionId: "session:alice", transportId: "transport:a" });
  } catch (error) {
    tlsRejected = String(error).includes("network.tls_failed");
  }
  if (!tlsRejected) throw new Error("insecure dedicated WebSocket URL was not rejected");

  a.restartIce();
  a.close(); b.close();
  return {
    schema: "splashmx.smx046-browser-evidence/1",
    user_agent: navigator.userAgent,
    webrtc_datachannel_open: true,
    semantic_message_delivered_once: true,
    recursive_authority_injection_rejected_before_send: authorityRejected,
    oversize_rejected_before_send: oversizeRejected,
    insecure_dedicated_ws_rejected: tlsRejected,
    restart_ice_supported: true,
    metrics: { local_datachannel_establishment_ms: establishedMs, local_loopback_message_ms: loopbackMs },
    note: "CI-local production-adapter mechanism evidence; not a product latency/throughput SLO."
  };
});

await browser.close();
await new Promise((resolve) => server.close(resolve));
const out = path.join(root, "artifacts/smx046-browser-evidence.json");
await fs.mkdir(path.dirname(out), { recursive: true });
await fs.writeFile(out, JSON.stringify(result, null, 2) + "\n");
console.log(JSON.stringify(result, null, 2));
