#!/usr/bin/env node
import fs from "node:fs/promises";
import http from "node:http";
import https from "node:https";
import os from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { chromium } from "playwright";
import { WebSocketServer } from "ws";

const root = process.argv[2] || process.cwd();
const moduleBytes = await fs.readFile(path.join(root, "src/splashmx/runtime/web/network_transport.mjs"));

const httpServer = http.createServer((req, res) => {
  if (req.url === "/network_transport.mjs") {
    res.writeHead(200, { "content-type": "text/javascript", "cache-control": "no-store" });
    res.end(moduleBytes);
    return;
  }
  res.writeHead(200, { "content-type": "text/html", "cache-control": "no-store" });
  res.end("<!doctype html><meta charset=utf-8><title>SMX-047 production topology gate</title>");
});
await new Promise((resolve) => httpServer.listen(0, "127.0.0.1", resolve));
const httpPort = httpServer.address().port;

const tlsDir = await fs.mkdtemp(path.join(os.tmpdir(), "smx047-tls-"));
const keyPath = path.join(tlsDir, "key.pem");
const certPath = path.join(tlsDir, "cert.pem");
execFileSync(
  "openssl",
  ["req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", keyPath, "-out", certPath, "-subj", "/CN=localhost", "-days", "1"],
  { stdio: "ignore" },
);
const [key, cert] = await Promise.all([fs.readFile(keyPath), fs.readFile(certPath)]);

const dedicatedEvents = [];
let dedicatedClosedCode = null;
let resolveDedicatedClosed;
const dedicatedClosed = new Promise((resolve) => {
  resolveDedicatedClosed = resolve;
});
const httpsServer = https.createServer({ key, cert });
const wss = new WebSocketServer({ server: httpsServer, maxPayload: 65536 });
wss.on("connection", (socket) => {
  let joined = false;
  socket.on("message", (bytes, isBinary) => {
    if (isBinary) {
      socket.close(1008, "binary runtime frame rejected");
      return;
    }
    let message;
    try {
      message = JSON.parse(bytes.toString("utf8"));
    } catch {
      socket.close(1008, "malformed runtime frame");
      return;
    }
    if (!joined) {
      if (
        message.kind !== "runtime_join" ||
        message.ticket !== "ticket-smx047" ||
        message.session_id !== "session:alice" ||
        message.transport_id !== "transport:dedicated:1"
      ) {
        socket.close(1008, "invalid runtime join");
        return;
      }
      joined = true;
      dedicatedEvents.push({ kind: "join", session_id: message.session_id, transport_id: message.transport_id });
      socket.send(JSON.stringify({
        message_id: "dedicated-baseline",
        message_class: "state",
        sender_session_id: "session:authority",
        authority_epoch: 1,
        sequence: 1,
        target_thing_id: "avatar:alice",
        locus: "position_x",
        payload: { value: 3 },
      }));
      return;
    }
    dedicatedEvents.push({ kind: "semantic", message_id: message.message_id });
    if (message.message_id === "dedicated-input") {
      socket.send(JSON.stringify({
        message_id: "dedicated-authority-state",
        message_class: "state",
        sender_session_id: "session:authority",
        authority_epoch: 1,
        sequence: 2,
        target_thing_id: "avatar:alice",
        locus: "position_x",
        payload: { value: 4 },
      }));
    } else if (message.message_id === "trigger-malformed") {
      socket.send('{"message_id":');
    }
  });
  socket.on("close", (code) => {
    dedicatedClosedCode = code;
    resolveDedicatedClosed(code);
  });
});
await new Promise((resolve) => httpsServer.listen(0, "127.0.0.1", resolve));
const wssPort = httpsServer.address().port;

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ ignoreHTTPSErrors: true });
const page = await context.newPage();
await page.goto(`http://127.0.0.1:${httpPort}/`);

const browserEvidence = await page.evaluate(async ({ wssPort }) => {
  const { BrowserRuntimeTransport } = await import("/network_transport.mjs");

  const waitUntil = async (predicate, timeoutMs = 10000) => {
    const deadline = performance.now() + timeoutMs;
    while (!predicate() && performance.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, 5));
    }
    if (!predicate()) throw new Error("SMX-047 browser harness timeout");
  };

  const percentile = (values, q) => {
    const sorted = [...values].sort((a, b) => a - b);
    const index = Math.min(sorted.length - 1, Math.max(0, Math.ceil(q * sorted.length) - 1));
    return sorted[index];
  };

  const summarize = (values) => ({
    count: values.length,
    min: Math.min(...values),
    median: percentile(values, 0.5),
    p95: percentile(values, 0.95),
    max: Math.max(...values),
  });

  const connectPeerPair = async () => {
    const a = new BrowserRuntimeTransport();
    const b = new BrowserRuntimeTransport();
    const aCandidates = [];
    const bCandidates = [];
    let aRemoteReady = false;
    let bRemoteReady = false;

    await a.openPeer({ initiator: true });
    await b.openPeer({ initiator: false });
    a.onIceCandidate((candidate) => {
      if (!candidate) return;
      if (bRemoteReady) void b.addIceCandidate(candidate);
      else aCandidates.push(candidate);
    });
    b.onIceCandidate((candidate) => {
      if (!candidate) return;
      if (aRemoteReady) void a.addIceCandidate(candidate);
      else bCandidates.push(candidate);
    });

    const started = performance.now();
    const offer = await a.makeOffer();
    const answer = await b.acceptOffer(offer);
    bRemoteReady = true;
    for (const candidate of aCandidates.splice(0)) await b.addIceCandidate(candidate);
    await a.acceptAnswer(answer);
    aRemoteReady = true;
    for (const candidate of bCandidates.splice(0)) await a.addIceCandidate(candidate);
    await waitUntil(() => a.readyState === "open" && b.readyState === "open");
    return { a, b, establishmentMs: performance.now() - started };
  };

  const first = await connectPeerPair();
  const receivedByB = [];
  const ackByA = new Map();
  first.b.onSemantic((message) => {
    receivedByB.push(message.message_id);
    if (message.message_id.startsWith("ping-")) {
      first.b.sendSemantic({
        message_id: `ack-${message.message_id}`,
        message_class: "event",
        sender_session_id: "session:authority",
        authority_epoch: 1,
        sequence: Number(message.message_id.slice(5)) + 1,
        target_thing_id: "avatar:alice",
        locus: "ack",
        payload: {},
      });
    }
  });
  first.a.onSemantic((message) => {
    if (message.message_id.startsWith("ack-ping-")) ackByA.set(message.message_id, performance.now());
  });

  const peerRoundTrips = [];
  for (let index = 0; index < 12; index += 1) {
    const started = performance.now();
    const pingId = `ping-${index}`;
    first.a.sendSemantic({
      message_id: pingId,
      message_class: "input",
      sender_session_id: "session:alice",
      authority_epoch: 1,
      sequence: index + 1,
      target_thing_id: "avatar:alice",
      locus: "move",
      payload: { dx: 1 },
    });
    await waitUntil(() => ackByA.has(`ack-${pingId}`));
    peerRoundTrips.push(ackByA.get(`ack-${pingId}`) - started);
  }

  const burstCount = 64;
  const burstPayloadBytes = 512;
  for (let index = 0; index < burstCount; index += 1) {
    first.a.sendSemantic({
      message_id: `burst-${index}`,
      message_class: "input",
      sender_session_id: "session:alice",
      authority_epoch: 1,
      sequence: 100 + index,
      target_thing_id: "avatar:alice",
      locus: "move",
      payload: { padding: "x".repeat(burstPayloadBytes) },
    });
  }
  await waitUntil(() => receivedByB.filter((id) => id.startsWith("burst-")).length === burstCount);
  const burstOrder = receivedByB.filter((id) => id.startsWith("burst-"));
  for (let index = 0; index < burstCount; index += 1) {
    if (burstOrder[index] !== `burst-${index}`) throw new Error("ordered DataChannel changed semantic frame order");
  }

  first.a.restartIce();
  const preDisconnectState = {
    sender_session_id: "session:alice",
    target_thing_id: "avatar:alice",
  };
  first.a.close();
  first.b.close();

  let disconnectedSendRejected = false;
  try {
    first.a.sendSemantic({
      message_id: "after-close",
      message_class: "input",
      sender_session_id: "session:alice",
      authority_epoch: 1,
      sequence: 999,
      target_thing_id: "avatar:alice",
      locus: "move",
      payload: {},
    });
  } catch (error) {
    disconnectedSendRejected = String(error).includes("network.reconnect_required");
  }
  if (!disconnectedSendRejected) throw new Error("send after physical loss did not require reconnect");

  const reconnect = await connectPeerPair();
  const reconnectedReceived = [];
  reconnect.b.onSemantic((message) => reconnectedReceived.push(message));
  reconnect.a.sendSemantic({
    message_id: "after-reconnect",
    message_class: "input",
    sender_session_id: preDisconnectState.sender_session_id,
    authority_epoch: 1,
    sequence: 1000,
    target_thing_id: preDisconnectState.target_thing_id,
    locus: "move",
    payload: { dx: 1 },
  });
  await waitUntil(() => reconnectedReceived.length === 1);
  if (reconnectedReceived[0].sender_session_id !== "session:alice") {
    throw new Error("semantic session identity changed across physical reconnect");
  }
  reconnect.a.close();
  reconnect.b.close();

  const dedicated = new BrowserRuntimeTransport();
  const dedicatedReceived = [];
  dedicated.onSemantic((message) => dedicatedReceived.push({ message, at: performance.now() }));
  const dedicatedStarted = performance.now();
  await dedicated.connectDedicatedWss({
    url: `wss://127.0.0.1:${wssPort}/runtime`,
    joinTicket: "ticket-smx047",
    sessionId: "session:alice",
    transportId: "transport:dedicated:1",
  });
  const dedicatedEstablishmentMs = performance.now() - dedicatedStarted;
  await waitUntil(() => dedicatedReceived.some((entry) => entry.message.message_id === "dedicated-baseline"));

  const dedicatedRoundTripStarted = performance.now();
  dedicated.sendSemantic({
    message_id: "dedicated-input",
    message_class: "input",
    sender_session_id: "session:alice",
    authority_epoch: 1,
    sequence: 1,
    target_thing_id: "avatar:alice",
    locus: "move",
    payload: { dx: 1 },
  });
  await waitUntil(() => dedicatedReceived.some((entry) => entry.message.message_id === "dedicated-authority-state"));
  const dedicatedRoundTripMs = performance.now() - dedicatedRoundTripStarted;

  dedicated.sendSemantic({
    message_id: "trigger-malformed",
    message_class: "input",
    sender_session_id: "session:alice",
    authority_epoch: 1,
    sequence: 2,
    target_thing_id: "avatar:alice",
    locus: "move",
    payload: { dx: 0 },
  });

  return {
    schema: "splashmx.smx047-browser-topology-evidence/1",
    user_agent: navigator.userAgent,
    peer: {
      datachannel_establishment_ms: first.establishmentMs,
      semantic_roundtrip_ms: summarize(peerRoundTrips),
      ordered_burst_message_count: burstCount,
      ordered_burst_payload_bytes_each: burstPayloadBytes,
      ice_restart_supported: true,
      disconnected_send_requires_reconnect: disconnectedSendRejected,
      reconnect_establishment_ms: reconnect.establishmentMs,
      semantic_identity_preserved_across_reconnect: reconnectedReceived[0].sender_session_id === "session:alice",
    },
    dedicated: {
      wss_establishment_ms: dedicatedEstablishmentMs,
      semantic_roundtrip_ms: dedicatedRoundTripMs,
      baseline_received: dedicatedReceived.some((entry) => entry.message.message_id === "dedicated-baseline"),
      authoritative_state_received: dedicatedReceived.some((entry) => entry.message.message_id === "dedicated-authority-state"),
    },
    note: "CI-local selected-adapter evidence only; semantic packet-loss/reorder/duplicate/resource policy is exercised against RuntimeNetworkingService by the SMX-047 Python gate.",
  };
}, { wssPort });

const observedCloseCode = await Promise.race([
  dedicatedClosed,
  new Promise((resolve) => setTimeout(() => resolve(null), 5000)),
]);
const serverEvidence = {
  node: process.version,
  dedicated_join_received: dedicatedEvents.some((event) => event.kind === "join"),
  dedicated_input_received: dedicatedEvents.some((event) => event.kind === "semantic" && event.message_id === "dedicated-input"),
  hostile_malformed_frame_trigger_received: dedicatedEvents.some((event) => event.kind === "semantic" && event.message_id === "trigger-malformed"),
  malformed_inbound_closed_with_policy_code: observedCloseCode === 4008 && dedicatedClosedCode === 4008,
};
if (!serverEvidence.dedicated_join_received || !serverEvidence.dedicated_input_received) {
  throw new Error("dedicated production WSS path was not bidirectional");
}
if (!serverEvidence.malformed_inbound_closed_with_policy_code) {
  throw new Error(`malformed dedicated inbound frame did not fail closed; close code=${dedicatedClosedCode}`);
}

await browser.close();
await new Promise((resolve) => wss.close(resolve));
await new Promise((resolve) => httpsServer.close(resolve));
await new Promise((resolve) => httpServer.close(resolve));
await fs.rm(tlsDir, { recursive: true, force: true });

const evidence = {
  ...browserEvidence,
  server: serverEvidence,
  versions: {
    playwright: "1.55.0",
    chromium: "pinned by Playwright 1.55.0",
    node: process.version,
  },
};
const output = path.join(root, "artifacts/smx047-topology-evidence.json");
await fs.mkdir(path.dirname(output), { recursive: true });
await fs.writeFile(output, JSON.stringify(evidence, null, 2) + "\n");
console.log(JSON.stringify(evidence, null, 2));
