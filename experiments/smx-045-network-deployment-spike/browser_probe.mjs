#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright";

const root = process.argv[2] || process.cwd();
const outPath = path.join(root, "artifacts", "smx045-browser-evidence.json");
fs.mkdirSync(path.dirname(outPath), { recursive: true });

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();

  const evidence = await page.evaluate(async () => {
    const now = () => performance.now();

    async function openPair(configA = {}, configB = {}, timeoutMs = 5000) {
      const a = new RTCPeerConnection(configA);
      const b = new RTCPeerConnection(configB);
      let aCandidates = 0;
      let bCandidates = 0;
      let candidateError = null;

      a.onicecandidate = async (event) => {
        if (!event.candidate) return;
        aCandidates += 1;
        try {
          await b.addIceCandidate(event.candidate);
        } catch (err) {
          candidateError = String(err);
        }
      };
      b.onicecandidate = async (event) => {
        if (!event.candidate) return;
        bCandidates += 1;
        try {
          await a.addIceCandidate(event.candidate);
        } catch (err) {
          candidateError = String(err);
        }
      };

      const received = new Promise((resolve) => {
        b.ondatachannel = (event) => {
          event.channel.onmessage = (message) => resolve(message.data);
        };
      });

      const channel = a.createDataChannel("smx-semantic-envelope", { ordered: true });
      const opened = new Promise((resolve, reject) => {
        const timer = setTimeout(
          () => reject(new Error(`data channel open timeout (${timeoutMs} ms)`)),
          timeoutMs,
        );
        channel.onopen = () => {
          clearTimeout(timer);
          resolve();
        };
      });

      const started = now();
      const offer = await a.createOffer();
      await a.setLocalDescription(offer);
      await b.setRemoteDescription(offer);
      const answer = await b.createAnswer();
      await b.setLocalDescription(answer);
      await a.setRemoteDescription(answer);
      await opened;
      const openMs = now() - started;

      const pingStarted = now();
      channel.send("smx045-ping");
      const value = await Promise.race([
        received,
        new Promise((_, reject) =>
          setTimeout(() => reject(new Error("data channel ping timeout")), 2000),
        ),
      ]);
      const rttMs = now() - pingStarted;

      const result = {
        open_ms: Number(openMs.toFixed(3)),
        loopback_message_rtt_ms: Number(rttMs.toFixed(3)),
        received: value,
        a_candidates: aCandidates,
        b_candidates: bCandidates,
        a_ice_state: a.iceConnectionState,
        b_ice_state: b.iceConnectionState,
        restart_ice_available: typeof a.restartIce === "function",
        candidate_error: candidateError,
      };
      channel.close();
      a.close();
      b.close();
      return result;
    }

    async function relayOnlyWithoutTurn(timeoutMs = 1200) {
      const config = { iceTransportPolicy: "relay", iceServers: [] };
      const a = new RTCPeerConnection(config);
      const b = new RTCPeerConnection(config);
      let candidates = 0;
      a.onicecandidate = (event) => {
        if (event.candidate) candidates += 1;
      };
      b.onicecandidate = (event) => {
        if (event.candidate) candidates += 1;
      };
      a.createDataChannel("expected-not-to-open");
      const offer = await a.createOffer();
      await a.setLocalDescription(offer);
      await b.setRemoteDescription(offer);
      const answer = await b.createAnswer();
      await b.setLocalDescription(answer);
      await a.setRemoteDescription(answer);
      await new Promise((resolve) => setTimeout(resolve, timeoutMs));
      const result = {
        candidates,
        a_ice_state: a.iceConnectionState,
        b_ice_state: b.iceConnectionState,
        typed_outcome: candidates === 0
          ? "network.ice_no_candidate"
          : "network.transport_unavailable",
      };
      a.close();
      b.close();
      return result;
    }

    const direct = await openPair();
    const noTurn = await relayOnlyWithoutTurn();

    return {
      user_agent: navigator.userAgent,
      visibility_state: document.visibilityState,
      direct_webrtc_datachannel: direct,
      relay_only_without_turn: noTurn,
      note: "Loopback mechanism probe only; not WAN/NAT or product latency qualification.",
    };
  });

  const payload = {
    schema: "splashmx.smx045-browser-evidence/1",
    playwright: "1.55.0",
    node: process.version,
    browser: evidence,
  };
  fs.writeFileSync(outPath, `${JSON.stringify(payload, null, 2)}\n`);
  console.log(JSON.stringify(payload, null, 2));

  if (evidence.direct_webrtc_datachannel.received !== "smx045-ping") {
    throw new Error("WebRTC DataChannel loopback did not carry the semantic envelope");
  }
  if (!evidence.direct_webrtc_datachannel.restart_ice_available) {
    throw new Error("RTCPeerConnection.restartIce is unavailable");
  }
  if (evidence.relay_only_without_turn.candidates !== 0) {
    throw new Error("relay-only probe unexpectedly found a candidate without TURN");
  }
  if (evidence.relay_only_without_turn.typed_outcome !== "network.ice_no_candidate") {
    throw new Error("ICE failure did not map to the frozen typed outcome");
  }
} finally {
  await browser.close();
}
