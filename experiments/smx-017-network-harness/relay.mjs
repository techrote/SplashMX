import { WebSocketServer, WebSocket } from 'ws';

// Trusted test relay. It deliberately keeps transport/session identity outside
// the canonical creation and overwrites sender metadata at the trust boundary.
export function startRelay(port = 8877) {
  let nextConn = 1;
  const rooms = new Map();
  const wss = new WebSocketServer({ port, maxPayload: 64 * 1024 });

  function roomFor(name, topology) {
    if (!rooms.has(name)) {
      rooms.set(name, {
        name,
        topology,
        members: new Map(),
        authorityConnId: null,
        authorityPrincipal: topology === 'offline' ? 'local' : '',
        authorityEpoch: 1,
        checkpoint: null,
      });
    }
    const room = rooms.get(name);
    if (room.topology !== topology) throw new Error(`room topology mismatch for ${name}`);
    return room;
  }

  function send(ws, obj) {
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
  }

  function authorityMember(room) {
    return room.authorityConnId ? room.members.get(room.authorityConnId) : null;
  }

  function forward(room, source, target, payload, extra = {}) {
    send(target.ws, {
      type: 'message',
      sender_principal: source?.principal ?? 'relay',
      sender_conn_id: source?.connId ?? 'relay',
      sender_role: source?.role ?? 'relay',
      payload,
      ...extra,
    });
  }

  function broadcastFromAuthority(room, source, payload) {
    const recipients = [...room.members.values()].filter((m) => m.connId !== source.connId);
    const kind = payload.type;
    if (kind === 'checkpoint') room.checkpoint = structuredClone(payload);

    for (const target of recipients) {
      // State samples are intentionally delayed out of order. Checkpoints/events
      // remain reliable; this tests semantic ordering above WebSocket ordering.
      let delayMs = 0;
      if (kind === 'state') {
        delayMs = payload.state_seq === 1 ? 180 : payload.state_seq === 2 ? 30 : 70;
      }
      setTimeout(() => forward(room, source, target, payload, { relay_delay_ms: delayMs }), delayMs);
      if (kind === 'event') {
        setTimeout(() => forward(room, source, target, payload, { relay_duplicate: true }), delayMs + 25);
      }
    }
  }

  function notifyUnavailable(room, reason) {
    for (const member of room.members.values()) {
      send(member.ws, { type: 'authority_unavailable', reason, authority_epoch: room.authorityEpoch });
    }
  }

  function promotePeerAuthority(room) {
    if (room.topology !== 'peer') return false;
    const candidates = [...room.members.values()].filter((m) => m.ws.readyState === WebSocket.OPEN);
    if (!room.checkpoint || candidates.length === 0) {
      notifyUnavailable(room, room.checkpoint ? 'no_surviving_peer' : 'checkpoint_unconfirmed');
      return false;
    }
    candidates.sort((a, b) => a.connectedAt - b.connectedAt || a.connId.localeCompare(b.connId));
    const chosen = candidates[0];
    room.authorityConnId = chosen.connId;
    room.authorityPrincipal = chosen.principal;
    room.authorityEpoch += 1;
    chosen.role = 'authority';
    send(chosen.ws, {
      type: 'authority_granted',
      authority_epoch: room.authorityEpoch,
      checkpoint: structuredClone(room.checkpoint),
    });
    for (const member of room.members.values()) {
      if (member.connId === chosen.connId) continue;
      send(member.ws, {
        type: 'message', sender_principal: 'relay', sender_conn_id: 'relay', sender_role: 'relay',
        payload: { type: 'baseline_request' },
      });
    }
    return true;
  }

  wss.on('connection', (ws, req) => {
    const url = new URL(req.url, `http://${req.headers.host || '127.0.0.1'}`);
    const roomName = url.searchParams.get('room') || 'smx017';
    const topology = url.searchParams.get('topology') || 'peer';
    const requestedRole = url.searchParams.get('role') || 'client';
    const principal = url.searchParams.get('principal') || 'anonymous';
    const member = {
      ws,
      connId: `conn-${nextConn++}`,
      principal,
      role: requestedRole,
      connectedAt: Date.now(),
      lastHeartbeat: Date.now(),
      watchLifecycle: url.searchParams.get('lifecycle_watch') === '1',
    };
    const room = roomFor(roomName, topology);
    room.members.set(member.connId, member);

    if (topology === 'peer' && requestedRole === 'authority' && !room.authorityConnId) {
      room.authorityConnId = member.connId;
      room.authorityPrincipal = principal;
      member.role = 'authority';
    } else if (topology === 'dedicated' && requestedRole === 'server' && !room.authorityConnId) {
      room.authorityConnId = member.connId;
      room.authorityPrincipal = principal;
      member.role = 'server';
    }

    send(ws, {
      type: 'welcome',
      conn_id: member.connId,
      authority_principal: room.authorityPrincipal,
      authority_epoch: room.authorityEpoch,
      topology,
    });

    const authority = authorityMember(room);
    if (authority && authority.connId !== member.connId) {
      forward(room, { principal: 'relay', connId: 'relay', role: 'relay' }, authority,
        { type: 'baseline_request', joining_conn_id: member.connId });
    }

    ws.on('message', (data) => {
      member.lastHeartbeat = Date.now();
      let outer;
      try { outer = JSON.parse(data.toString()); }
      catch { send(ws, { type: 'authority_unavailable', reason: 'malformed_client_json' }); return; }
      if (outer.type === 'heartbeat') return;
      if (outer.type !== 'payload' || !outer.payload || typeof outer.payload !== 'object') return;
      const payload = outer.payload;
      const isAuthority = room.authorityConnId === member.connId;
      if (isAuthority) {
        broadcastFromAuthority(room, member, payload);
      } else {
        const authorityNow = authorityMember(room);
        if (!authorityNow) {
          send(ws, { type: 'authority_unavailable', reason: 'no_current_authority', authority_epoch: room.authorityEpoch });
          return;
        }
        forward(room, member, authorityNow, payload);
      }
    });

    ws.on('close', () => {
      const wasAuthority = room.authorityConnId === member.connId;
      room.members.delete(member.connId);
      if (!wasAuthority) return;
      room.authorityConnId = null;
      room.authorityPrincipal = '';
      if (room.topology === 'peer') {
        promotePeerAuthority(room);
      } else if (room.topology === 'dedicated') {
        room.authorityEpoch += 1;
        notifyUnavailable(room, 'dedicated_authority_disconnected_fail_closed');
      }
    });
  });

  const watchdog = setInterval(() => {
    const now = Date.now();
    for (const room of rooms.values()) {
      for (const member of room.members.values()) {
        if (member.watchLifecycle && now - member.lastHeartbeat > 1400 && member.ws.readyState === WebSocket.OPEN) {
          member.ws.close(4001, 'application heartbeat timeout during browser suspension');
        }
      }
    }
  }, 200);

  return {
    port,
    rooms,
    injectToAuthority(roomName, payload, sender = {}) {
      const room = rooms.get(roomName);
      if (!room) throw new Error(`unknown room ${roomName}`);
      const target = authorityMember(room);
      if (!target) throw new Error(`no authority in room ${roomName}`);
      forward(room, {
        principal: sender.principal ?? 'harness',
        connId: sender.connId ?? 'harness-injected',
        role: sender.role ?? 'client',
      }, target, payload);
    },
    roomSnapshot(roomName) {
      const room = rooms.get(roomName);
      if (!room) return null;
      return {
        topology: room.topology,
        authorityPrincipal: room.authorityPrincipal,
        authorityEpoch: room.authorityEpoch,
        checkpoint: room.checkpoint ? structuredClone(room.checkpoint) : null,
        members: [...room.members.values()].map((m) => ({ connId: m.connId, principal: m.principal, role: m.role })),
      };
    },
    async close() {
      clearInterval(watchdog);
      for (const room of rooms.values()) for (const member of room.members.values()) member.ws.close();
      await new Promise((resolve) => wss.close(resolve));
    },
  };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  startRelay(Number(process.env.SMX017_RELAY_PORT || 8877));
  console.log('SMX017 relay ready');
}
