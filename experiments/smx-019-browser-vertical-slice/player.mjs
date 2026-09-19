import { activatePublished, activateThing, validatePublished } from './model.mjs';

const params = new URLSearchParams(location.search);
const revision = params.get('rev');
const topology = params.get('topology') ?? 'offline';
const principal = params.get('principal') ?? 'alice';
const room = params.get('room') ?? 'smx019';
const deny = new Set((params.get('deny') ?? '').split(',').filter(Boolean));
const status = document.querySelector('#player-status');
const stage = document.querySelector('#player-stage');
const details = document.querySelector('#player-details');
let active = null;
let creation = null;
let socket = null;
let authorityPrincipal = topology === 'offline' ? principal : null;
let transportConnectionId = topology === 'offline' ? 'local' : null;
let lastSharedState = null;

function friendly(error) {
  const messages = {
    schema_incompatible: 'This creation needs a newer SplashMX player.',
    ir_incompatible: 'One Behaviour needs a newer SplashMX player.',
    required_feature_unsupported: 'This creation uses a feature this player does not support yet.',
    required_capability_denied: 'This creation is not allowed to use a requested device or service.',
    creation_digest_mismatch: 'This published creation did not pass its integrity check.',
    host_identity_forbidden: 'This creation contains unsupported private runtime data.'
  };
  return messages[error?.code] ?? error?.message ?? 'This creation could not be loaded.';
}

async function loadExactCreation() {
  if (!revision) throw Object.assign(new Error('No published revision was selected.'), { code:'missing_revision' });
  const path = `/api/creation/${encodeURIComponent(revision)}`;
  const cache = 'caches' in window ? await caches.open('smx019-creations-v1') : null;
  try {
    const response = await fetch(path, { cache:'no-store' });
    if (!response.ok) throw new Error(`Published revision is unavailable (${response.status}).`);
    if (cache) await cache.put(path, response.clone());
    return await response.json();
  } catch (networkError) {
    const cached = cache ? await cache.match(path) : null;
    if (!cached) throw Object.assign(new Error('This published revision is not available offline on this device.'), { code:'offline_unavailable', cause:networkError });
    return await cached.json();
  }
}

function renderThing(thing) {
  if (thing.kind === 'group') {
    const group = document.createElement('div');
    group.className = 'thing group';
    group.dataset.thingId = thing.thing_id;
    group.style.left = '28px'; group.style.top = '24px'; group.textContent = thing.name;
    stage.append(group);
    return;
  }
  const element = thing.kind === 'button' ? document.createElement('button') : document.createElement('div');
  element.className = `thing ${thing.kind}${thing.state.toggled ? ' on' : ''}`;
  element.dataset.thingId = thing.thing_id;
  element.style.left = `${thing.state.x}px`;
  element.style.top = `${thing.state.y}px`;
  element.style.background = thing.state.toggled ? '#fff0a5' : thing.state.color;
  element.textContent = thing.state.text;
  if (thing.kind === 'button') element.addEventListener('click', () => localIntent(thing.thing_id));
  stage.append(element);
}

function render() {
  stage.replaceChildren();
  if (!active) return;
  active.runtime.things.forEach(renderThing);
  details.textContent = `${creation.creation_id} · ${creation.creation_revision_id.slice(0, 22)}… · ${topology === 'offline' ? 'Local play' : 'Shared play'}`;
}

function applyReplicatedState(payload) {
  if (!active || !payload?.things) return;
  for (const incoming of payload.things) {
    const local = active.runtime.things.find(t => t.thing_id === incoming.thing_id);
    if (local) local.state = structuredClone(incoming.state);
  }
  lastSharedState = structuredClone(payload);
  render();
}

function broadcastState() {
  if (!socket || socket.readyState !== WebSocket.OPEN) return;
  socket.send(JSON.stringify({
    type:'state',
    creation_revision_id:creation.creation_revision_id,
    things:active.runtime.things.map(t => ({ thing_id:t.thing_id, state:t.state }))
  }));
}

function localIntent(thingId) {
  if (topology === 'offline' || authorityPrincipal === principal) {
    activateThing(active.runtime, thingId);
    render();
    if (topology !== 'offline') broadcastState();
    return;
  }
  if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type:'intent', thing_id:thingId, creation_revision_id:creation.creation_revision_id }));
}

function connectPeer() {
  const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
  const url = `${scheme}://${location.host}/peer?room=${encodeURIComponent(room)}&principal=${encodeURIComponent(principal)}&rev=${encodeURIComponent(revision)}`;
  socket = new WebSocket(url);
  socket.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (message.type === 'welcome') {
      transportConnectionId = message.conn_id;
      authorityPrincipal = message.authority_principal;
      status.textContent = authorityPrincipal === principal ? 'Shared play · hosting' : 'Shared play · joined';
      if (lastSharedState === null && authorityPrincipal === principal) broadcastState();
    } else if (message.type === 'intent' && authorityPrincipal === principal) {
      if (message.creation_revision_id !== revision) return;
      activateThing(active.runtime, message.thing_id);
      render();
      broadcastState();
    } else if (message.type === 'state') {
      if (message.creation_revision_id !== revision) return;
      applyReplicatedState(message);
    } else if (message.type === 'authority') {
      authorityPrincipal = message.authority_principal;
    }
  });
}

async function boot() {
  try {
    creation = await loadExactCreation();
    const supportedFeatures = params.get('unsupported_feature') === '1' ? ['things','behaviours'] : ['things','behaviours','connections','timeline','definitions','network'];
    const grantedCapabilities = (creation.capabilities?.required ?? []).filter(cap => !deny.has(cap));
    validatePublished(creation, { supportedFeatures, grantedCapabilities });
    active = activatePublished(creation, { supportedFeatures, grantedCapabilities });
    status.textContent = 'Ready';
    render();
    if (topology === 'peer') connectPeer();
    const message = { type:'smx019-player-ready', creation_revision_id:creation.creation_revision_id };
    window.parent?.postMessage(message, location.origin);
    window.__SMX019_PLAYER__ = {
      getCreation: () => structuredClone(creation),
      getState: () => structuredClone(active.runtime),
      getContext: () => ({ topology, principal, authorityPrincipal, transportConnectionId })
    };
  } catch (error) {
    status.textContent = friendly(error);
    status.className = 'error';
    window.__SMX019_PLAYER_ERROR__ = { code:error?.code ?? 'load_failed', message:friendly(error) };
  }
}

boot();
