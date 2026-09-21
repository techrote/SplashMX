/**
 * SplashMX browser transport adapter for SMX-046.
 *
 * RTCPeerConnection/WebSocket identities stay private to this target adapter.
 * Callers exchange bounded semantic envelopes; the adapter never exposes the
 * underlying peer/channel/socket as authored or persistent state.
 */
export const MAX_RUNTIME_MESSAGE_BYTES = 65536;
export const MAX_RUNTIME_JOIN_BYTES = 4096;
export const SEMANTIC_POLICY_CLOSE_CODE = 4008;

const FORBIDDEN = new Set([
  "capability", "capability_grant", "capability_id", "host_handle",
  "node_path", "rid", "resource_uid", "resource_path", "socket_id",
  "connection_handle", "process_handle", "godot_peer_id", "peer_id",
  "javascript_handle", "filesystem_handle", "raw_network_handle",
  "transport_id", "session_id"
]);

function utf8Size(text) {
  return new TextEncoder().encode(text).byteLength;
}

function scan(value, depth = 0) {
  if (depth > 32) throw new Error("network.auth_rejected: nested authority depth exceeded");
  if (value === null || value === undefined) return;
  if (Array.isArray(value)) {
    for (const child of value) scan(child, depth + 1);
    return;
  }
  if (typeof value === "object") {
    for (const [key, child] of Object.entries(value)) {
      if (FORBIDDEN.has(key.toLowerCase())) {
        throw new Error(`network.auth_rejected: forbidden semantic payload field ${key}`);
      }
      scan(child, depth + 1);
    }
  }
}

export function encodeSemanticEnvelope(envelope, maxBytes = MAX_RUNTIME_MESSAGE_BYTES) {
  scan(envelope?.payload ?? {});
  const encoded = JSON.stringify(envelope);
  if (utf8Size(encoded) > maxBytes) throw new Error("network.message_oversize");
  return encoded;
}

export function decodeSemanticEnvelope(text, maxBytes = MAX_RUNTIME_MESSAGE_BYTES) {
  if (typeof text !== "string" || utf8Size(text) > maxBytes) throw new Error("network.message_oversize");
  const value = JSON.parse(text);
  scan(value?.payload ?? {});
  return value;
}

export class BrowserRuntimeTransport {
  #pc = null;
  #channel = null;
  #socket = null;
  #onSemantic = null;
  #maxBytes;
  #iceServers;

  constructor({ iceServers = [], maxBytes = MAX_RUNTIME_MESSAGE_BYTES } = {}) {
    this.#iceServers = structuredClone(iceServers);
    this.#maxBytes = maxBytes;
  }

  get transportKind() {
    return "webrtc_datachannel";
  }

  get readyState() {
    if (this.#channel) return this.#channel.readyState;
    if (this.#socket) {
      return ["connecting", "open", "closing", "closed"][this.#socket.readyState] ?? "closed";
    }
    return "closed";
  }

  onSemantic(callback) {
    this.#onSemantic = callback;
  }

  async openPeer({ initiator = false } = {}) {
    if (this.#pc) throw new Error("network.transport_unavailable: peer already open");
    this.#pc = new RTCPeerConnection({ iceServers: this.#iceServers });
    this.#pc.ondatachannel = (event) => this.#installChannel(event.channel);
    if (initiator) this.#installChannel(this.#pc.createDataChannel("splashmx-runtime", { ordered: true }));
    return undefined;
  }

  async makeOffer() {
    if (!this.#pc) throw new Error("network.transport_unavailable");
    const offer = await this.#pc.createOffer();
    await this.#pc.setLocalDescription(offer);
    return { type: offer.type, sdp: offer.sdp };
  }

  async acceptOffer(offer) {
    if (!this.#pc) throw new Error("network.transport_unavailable");
    await this.#pc.setRemoteDescription(offer);
    const answer = await this.#pc.createAnswer();
    await this.#pc.setLocalDescription(answer);
    return { type: answer.type, sdp: answer.sdp };
  }

  async acceptAnswer(answer) {
    if (!this.#pc) throw new Error("network.transport_unavailable");
    await this.#pc.setRemoteDescription(answer);
  }

  async addIceCandidate(candidate) {
    if (!this.#pc) throw new Error("network.transport_unavailable");
    if (candidate) await this.#pc.addIceCandidate(candidate);
  }

  onIceCandidate(callback) {
    if (!this.#pc) throw new Error("network.transport_unavailable");
    this.#pc.onicecandidate = (event) => callback(event.candidate ? event.candidate.toJSON() : null);
  }

  restartIce() {
    if (!this.#pc || typeof this.#pc.restartIce !== "function") throw new Error("network.reconnect_failed");
    this.#pc.restartIce();
  }

  sendSemantic(envelope) {
    const encoded = encodeSemanticEnvelope(envelope, this.#maxBytes);
    if (this.#channel?.readyState === "open") {
      this.#channel.send(encoded);
      return;
    }
    if (this.#socket?.readyState === 1) {
      this.#socket.send(encoded);
      return;
    }
    throw new Error("network.reconnect_required");
  }

  async connectDedicatedWss({ url, joinTicket, sessionId, transportId, WebSocketImpl = WebSocket } = {}) {
    const parsed = new URL(url);
    if (parsed.protocol !== "wss:") throw new Error("network.tls_failed");
    if (typeof joinTicket !== "string" || utf8Size(joinTicket) > MAX_RUNTIME_JOIN_BYTES) {
      throw new Error("network.auth_rejected");
    }
    if (!sessionId || !transportId || sessionId === transportId) throw new Error("network.auth_rejected");
    if (this.#socket) throw new Error("network.transport_unavailable: socket already open");
    const socket = new WebSocketImpl(parsed.href);
    this.#socket = socket;
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error("network.server_unavailable")), 10000);
      socket.addEventListener("open", () => {
        clearTimeout(timer);
        const join = JSON.stringify({ kind: "runtime_join", ticket: joinTicket, session_id: sessionId, transport_id: transportId });
        if (utf8Size(join) > this.#maxBytes) return reject(new Error("network.message_oversize"));
        socket.send(join);
        resolve();
      }, { once: true });
      socket.addEventListener("error", () => {
        clearTimeout(timer);
        reject(new Error("network.transport_unavailable"));
      }, { once: true });
    });
    socket.addEventListener("message", (event) => {
      if (typeof event.data !== "string") return;
      try {
        const decoded = decodeSemanticEnvelope(event.data, this.#maxBytes);
        this.#onSemantic?.(decoded);
      } catch {
        socket.close(SEMANTIC_POLICY_CLOSE_CODE, "invalid semantic envelope");
      }
    });
  }

  close() {
    try { this.#channel?.close(); } catch {}
    try { this.#pc?.close(); } catch {}
    try { this.#socket?.close(); } catch {}
    this.#channel = null;
    this.#pc = null;
    this.#socket = null;
  }

  #installChannel(channel) {
    if (channel.label !== "splashmx-runtime") {
      channel.close();
      throw new Error("network.transport_unavailable: unexpected data channel");
    }
    channel.binaryType = "arraybuffer";
    channel.onmessage = (event) => {
      if (typeof event.data !== "string") {
        channel.close();
        return;
      }
      try {
        this.#onSemantic?.(decodeSemanticEnvelope(event.data, this.#maxBytes));
      } catch {
        channel.close();
      }
    };
    this.#channel = channel;
  }
}
