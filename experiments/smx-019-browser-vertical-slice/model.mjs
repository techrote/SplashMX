export const FORBIDDEN_CANONICAL_KEYS = new Set([
  'node', 'node_path', 'scenetree', 'scene_tree', 'resource', 'resource_uid',
  'rid', 'rpc', 'peer_id', 'transport_peer_id', 'connection_handle',
  'socket', 'capability_grant', 'capability_token', 'host_handle',
  'javascript_bridge', 'godot_node', 'godot_resource'
]);

export const REQUIRED_ASSET_REVISION_KEYS = [
  'digest', 'source', 'media', 'provenance', 'licence', 'derivation'
];

export const AUTHOR_VOCABULARY = [
  'Thing', 'Behaviour', 'Connection', 'Stage', 'Timeline', 'Rules',
  'Components', 'Together', 'People', 'Publish', 'Inspect'
];

const deepClone = value => structuredClone(value);

export function canonicalStringify(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalStringify).join(',')}]`;
  if (value && typeof value === 'object') {
    const keys = Object.keys(value).sort();
    return `{${keys.map(k => `${JSON.stringify(k)}:${canonicalStringify(value[k])}`).join(',')}}`;
  }
  return JSON.stringify(value);
}

export function sha256(value) {
  const text = typeof value === 'string' ? value : canonicalStringify(value);
  const bytes = new TextEncoder().encode(text);
  const bitLength = bytes.length * 8;
  const withOne = bytes.length + 1;
  const paddedLength = Math.ceil((withOne + 8) / 64) * 64;
  const data = new Uint8Array(paddedLength);
  data.set(bytes);
  data[bytes.length] = 0x80;
  const view = new DataView(data.buffer);
  const high = Math.floor(bitLength / 0x100000000);
  const low = bitLength >>> 0;
  view.setUint32(paddedLength - 8, high, false);
  view.setUint32(paddedLength - 4, low, false);

  const k = [
    0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
    0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
    0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
    0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
    0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
    0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
    0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
    0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
  ];
  const rotr = (x, n) => (x >>> n) | (x << (32 - n));
  let h0=0x6a09e667,h1=0xbb67ae85,h2=0x3c6ef372,h3=0xa54ff53a,h4=0x510e527f,h5=0x9b05688c,h6=0x1f83d9ab,h7=0x5be0cd19;
  const w = new Uint32Array(64);
  for (let offset = 0; offset < data.length; offset += 64) {
    for (let i = 0; i < 16; i++) w[i] = view.getUint32(offset + i * 4, false);
    for (let i = 16; i < 64; i++) {
      const s0 = rotr(w[i-15],7) ^ rotr(w[i-15],18) ^ (w[i-15] >>> 3);
      const s1 = rotr(w[i-2],17) ^ rotr(w[i-2],19) ^ (w[i-2] >>> 10);
      w[i] = (w[i-16] + s0 + w[i-7] + s1) >>> 0;
    }
    let a=h0,b=h1,c=h2,d=h3,e=h4,f=h5,g=h6,h=h7;
    for (let i = 0; i < 64; i++) {
      const S1 = rotr(e,6) ^ rotr(e,11) ^ rotr(e,25);
      const ch = (e & f) ^ (~e & g);
      const temp1 = (h + S1 + ch + k[i] + w[i]) >>> 0;
      const S0 = rotr(a,2) ^ rotr(a,13) ^ rotr(a,22);
      const maj = (a & b) ^ (a & c) ^ (b & c);
      const temp2 = (S0 + maj) >>> 0;
      h=g; g=f; f=e; e=(d + temp1) >>> 0; d=c; c=b; b=a; a=(temp1 + temp2) >>> 0;
    }
    h0=(h0+a)>>>0; h1=(h1+b)>>>0; h2=(h2+c)>>>0; h3=(h3+d)>>>0;
    h4=(h4+e)>>>0; h5=(h5+f)>>>0; h6=(h6+g)>>>0; h7=(h7+h)>>>0;
  }
  return [h0,h1,h2,h3,h4,h5,h6,h7].map(v => v.toString(16).padStart(8,'0')).join('');
}

function assert(condition, message, code = 'invalid_project') {
  if (!condition) {
    const error = new Error(message);
    error.code = code;
    throw error;
  }
}

function walk(value, path = '$', visit = () => {}) {
  if (!value || typeof value !== 'object') return;
  if (Array.isArray(value)) {
    value.forEach((entry, index) => walk(entry, `${path}[${index}]`, visit));
    return;
  }
  for (const [key, entry] of Object.entries(value)) {
    visit(key, entry, `${path}.${key}`);
    walk(entry, `${path}.${key}`, visit);
  }
}

export function rejectHostIdentity(value) {
  walk(value, '$', (key, _entry, path) => {
    const normalized = key.toLowerCase();
    assert(!FORBIDDEN_CANONICAL_KEYS.has(normalized), `Host/runtime identity ${key} is not canonical content (${path})`, 'host_identity_forbidden');
    assert(!normalized.startsWith('godot_'), `Godot identity ${key} is not canonical content (${path})`, 'host_identity_forbidden');
  });
}

function uniqueIds(records, field, label) {
  const seen = new Set();
  for (const record of records ?? []) {
    const id = record?.[field];
    assert(typeof id === 'string' && id.length > 0, `${label} requires ${field}`);
    assert(!seen.has(id), `Duplicate ${label} identity: ${id}`, 'duplicate_identity');
    seen.add(id);
  }
  return seen;
}

export function validateAsset(asset) {
  assert(asset && typeof asset === 'object', 'Asset record is required', 'invalid_asset');
  assert(typeof asset.asset_id === 'string' && asset.asset_id.length > 0, 'AssetId is required', 'invalid_asset');
  assert(asset.revision && typeof asset.revision === 'object', 'Complete asset revision is required', 'invalid_asset');
  for (const key of REQUIRED_ASSET_REVISION_KEYS) {
    assert(Object.prototype.hasOwnProperty.call(asset.revision, key), `Asset revision is missing ${key}`, 'asset_revision_incomplete');
  }
  assert(typeof asset.revision.digest === 'string' && asset.revision.digest.length >= 16, 'Asset digest is invalid', 'invalid_asset');
  assert(asset.revision.source && typeof asset.revision.source.identity === 'string', 'Asset source identity is required', 'invalid_asset');
  assert(asset.revision.media && typeof asset.revision.media.kind === 'string', 'Asset media semantics are required', 'invalid_asset');
  assert(asset.revision.provenance && typeof asset.revision.provenance.origin === 'string', 'Asset provenance is required', 'invalid_asset');
  assert(typeof asset.revision.licence === 'string', 'Asset licence is required', 'invalid_asset');
  assert(asset.revision.derivation && typeof asset.revision.derivation === 'object', 'Asset derivation record is required', 'invalid_asset');
  rejectHostIdentity(asset);
  return true;
}

export function replaceAsset(project, assetId, replacement) {
  const draft = deepClone(project);
  const index = draft.assets.findIndex(asset => asset.asset_id === assetId);
  assert(index >= 0, `Unknown AssetId: ${assetId}`, 'unknown_asset');
  const complete = { asset_id: assetId, revision: deepClone(replacement) };
  validateAsset(complete);
  draft.assets[index] = complete;
  validateProject(draft);
  return draft;
}

export function createBlankProject() {
  return {
    format: 'SplashMX.EditableProject',
    schema_version: 1,
    project_id: 'project-browser-slice',
    project_revision: 0,
    things: [],
    definitions: [],
    behaviours: [],
    connections: [],
    timeline: [],
    assets: [],
    network: {
      preset: 'local',
      spawn_scope: 'project',
      control: 'local',
      authority: 'local',
      replication: 'none',
      relevance: 'local'
    },
    collaboration: { conflicts: [] },
    authoring: { selected_thing_ids: [], presence: [], play_session: null }
  };
}

function bump(project) {
  project.project_revision = Number(project.project_revision ?? 0) + 1;
  return project;
}

export function addThing(project, { thingId, name, kind = 'visual', parentId = null, x = 20, y = 20, text = name, color = '#d9e9ff' }) {
  const draft = deepClone(project);
  draft.things.push({
    thing_id: thingId,
    name,
    kind,
    parent_id: parentId,
    state: { x, y, text, color, visible: true, toggled: false },
    ports: [
      { port_id: `${thingId}:activate`, kind: 'command', direction: 'in' },
      { port_id: `${thingId}:activated`, kind: 'event', direction: 'out' },
      { port_id: `${thingId}:toggle`, kind: 'command', direction: 'in' }
    ]
  });
  bump(draft);
  validateProject(draft);
  return draft;
}

export function groupThings(project, { groupId, name = 'Group', childIds }) {
  const draft = addThing(project, { thingId: groupId, name, kind: 'group', text: name });
  const childSet = new Set(childIds);
  assert(childSet.size === childIds.length && childIds.length > 0, 'Group requires unique children', 'invalid_group');
  for (const childId of childIds) {
    const child = draft.things.find(t => t.thing_id === childId);
    assert(child, `Unknown child Thing: ${childId}`, 'unknown_thing');
    assert(childId !== groupId, 'Group cannot contain itself', 'invalid_group');
    child.parent_id = groupId;
  }
  bump(draft);
  validateProject(draft);
  return draft;
}

export function makeReusable(project, { groupId, definitionId }) {
  const draft = deepClone(project);
  const group = draft.things.find(t => t.thing_id === groupId);
  assert(group && group.kind === 'group', 'Make reusable starts from an ordinary group Thing', 'invalid_reuse');
  assert(!draft.definitions.some(d => d.definition_id === definitionId), `Duplicate DefinitionId: ${definitionId}`, 'duplicate_identity');
  const members = draft.things.filter(t => t.parent_id === groupId);
  assert(members.length > 0, 'Reusable group must contain at least one Thing', 'invalid_reuse');
  draft.definitions.push({
    definition_id: definitionId,
    root_thing_id: groupId,
    elements: [group, ...members].map((thing, index) => ({
      element_id: `${definitionId}:element:${index + 1}`,
      source_thing_id: thing.thing_id
    })),
    public_ports: group.ports.map(port => ({
      public_port_id: `${definitionId}:public:${port.port_id.split(':').at(-1)}`,
      target_thing_id: group.thing_id,
      target_port_id: port.port_id,
      kind: port.kind,
      direction: port.direction
    }))
  });
  group.definition_instance = { definition_id: definitionId, first_instance: true };
  bump(draft);
  validateProject(draft);
  return draft;
}

export function attachBehaviour(project, { attachmentId, thingId, source = 'rule', eventPort, instructions }) {
  const draft = deepClone(project);
  assert(source === 'rule' || source === 'advanced', 'Unknown behaviour authoring projection', 'invalid_behaviour');
  draft.behaviours.push({
    attachment_id: attachmentId,
    thing_id: thingId,
    authoring_projection: source,
    ir: {
      version: 1,
      trigger: { event_port_id: eventPort },
      instructions: deepClone(instructions)
    }
  });
  bump(draft);
  validateProject(draft);
  return draft;
}

export function connect(project, { connectionId, fromThingId, fromPortId, toThingId, toPortId }) {
  const draft = deepClone(project);
  draft.connections.push({
    connection_id: connectionId,
    from: { thing_id: fromThingId, port_id: fromPortId },
    to: { thing_id: toThingId, port_id: toPortId }
  });
  bump(draft);
  validateProject(draft);
  return draft;
}

export function addTimelineTrack(project, { trackId, thingId, property = 'x', keyframes }) {
  const draft = deepClone(project);
  draft.timeline.push({ track_id: trackId, target: { thing_id: thingId, property }, keyframes: deepClone(keyframes) });
  bump(draft);
  validateProject(draft);
  return draft;
}

export function setNetworkPreset(project, preset) {
  const draft = deepClone(project);
  const table = {
    local: { preset: 'local', spawn_scope: 'project', control: 'local', authority: 'local', replication: 'none', relevance: 'local' },
    per_player: { preset: 'per_player', spawn_scope: 'participant', control: 'participant', authority: 'topology_policy', replication: 'owner_and_observers', relevance: 'participant' },
    shared: { preset: 'shared', spawn_scope: 'project', control: 'declared_controllers', authority: 'topology_policy', replication: 'shared_state', relevance: 'declared' },
    authority_controlled: { preset: 'authority_controlled', spawn_scope: 'project', control: 'intent_only', authority: 'topology_policy', replication: 'authoritative_state', relevance: 'declared' }
  };
  assert(table[preset], `Unknown Together preset: ${preset}`, 'invalid_network');
  draft.network = deepClone(table[preset]);
  bump(draft);
  validateProject(draft);
  return draft;
}

export function setAdvancedNetwork(project, fields) {
  const allowed = new Set(['spawn_scope', 'control', 'authority', 'replication', 'relevance']);
  for (const key of Object.keys(fields)) assert(allowed.has(key), `Transport/session field ${key} is not authored networking`, 'network_context_forbidden');
  const draft = deepClone(project);
  draft.network = { ...draft.network, ...deepClone(fields), preset: 'custom' };
  bump(draft);
  validateProject(draft);
  return draft;
}

export function addConflict(project, conflict) {
  const draft = deepClone(project);
  draft.collaboration.conflicts.push({
    conflict_id: conflict.conflict_id,
    locus: deepClone(conflict.locus),
    alternatives: deepClone(conflict.alternatives),
    status: 'unresolved'
  });
  bump(draft);
  validateProject(draft);
  return draft;
}

export function setTransientPresence(project, presence) {
  const draft = deepClone(project);
  draft.authoring.presence = deepClone(presence);
  return draft;
}

export function editableSnapshot(project) {
  const snapshot = deepClone(project);
  snapshot.authoring = { selected_thing_ids: [], presence: [], play_session: null };
  return snapshot;
}

export function startPlay(project) {
  validateProject(project);
  return {
    authored_revision: project.project_revision,
    things: deepClone(project.things),
    behaviours: deepClone(project.behaviours),
    connections: deepClone(project.connections),
    timeline: deepClone(project.timeline),
    events: [],
    active: true
  };
}

export function activateThing(runtime, thingId) {
  assert(runtime.active, 'Play session is not active', 'runtime_inactive');
  const source = runtime.things.find(t => t.thing_id === thingId);
  assert(source, `Unknown runtime Thing: ${thingId}`, 'unknown_thing');
  source.state.toggled = !Boolean(source.state.toggled);
  runtime.events.push({ kind: 'activated', thing_id: thingId });
  for (const behaviour of runtime.behaviours.filter(b => b.thing_id === thingId)) {
    for (const instruction of behaviour.ir.instructions) {
      if (instruction.op === 'set') {
        const target = runtime.things.find(t => t.thing_id === instruction.thing_id);
        assert(target, `Unknown behaviour target: ${instruction.thing_id}`, 'unknown_thing');
        target.state[instruction.property] = instruction.value;
      }
      if (instruction.op === 'toggle') {
        const target = runtime.things.find(t => t.thing_id === instruction.thing_id);
        assert(target, `Unknown behaviour target: ${instruction.thing_id}`, 'unknown_thing');
        target.state[instruction.property] = !Boolean(target.state[instruction.property]);
      }
    }
  }
  for (const connection of runtime.connections.filter(c => c.from.thing_id === thingId && c.from.port_id.endsWith(':activated'))) {
    const target = runtime.things.find(t => t.thing_id === connection.to.thing_id);
    if (target && connection.to.port_id.endsWith(':toggle')) target.state.toggled = !Boolean(target.state.toggled);
  }
  return runtime;
}

export function stopPlay(_runtime) {
  return null;
}

export function validateProject(project) {
  assert(project && project.format === 'SplashMX.EditableProject', 'Unsupported editable project', 'schema_incompatible');
  assert(project.schema_version === 1, 'This project needs a newer SplashMX version', 'schema_incompatible');
  rejectHostIdentity(project);

  const thingIds = uniqueIds(project.things, 'thing_id', 'Thing');
  const definitionIds = uniqueIds(project.definitions, 'definition_id', 'Definition');
  const attachmentIds = uniqueIds(project.behaviours, 'attachment_id', 'Behaviour attachment');
  uniqueIds(project.connections, 'connection_id', 'Connection');
  uniqueIds(project.timeline, 'track_id', 'Timeline track');
  uniqueIds(project.assets, 'asset_id', 'Asset');
  void definitionIds; void attachmentIds;

  const portOwner = new Map();
  for (const thing of project.things) {
    if (thing.parent_id !== null) assert(thingIds.has(thing.parent_id), `Thing ${thing.thing_id} has unknown parent`, 'dangling_reference');
    for (const port of thing.ports ?? []) {
      assert(typeof port.port_id === 'string' && !port.port_id.includes('/'), 'Connections use stable port IDs, not hierarchy paths', 'invalid_port');
      assert(!portOwner.has(port.port_id), `Duplicate PortId: ${port.port_id}`, 'duplicate_identity');
      portOwner.set(port.port_id, thing.thing_id);
    }
  }

  for (const definition of project.definitions) {
    assert(thingIds.has(definition.root_thing_id), 'Definition root must be an existing Thing', 'dangling_reference');
    const sourceIds = new Set();
    for (const element of definition.elements ?? []) {
      assert(thingIds.has(element.source_thing_id), 'Definition element must preserve an existing Thing', 'dangling_reference');
      assert(!sourceIds.has(element.source_thing_id), 'Definition cannot duplicate a source Thing', 'invalid_reuse');
      sourceIds.add(element.source_thing_id);
    }
  }

  for (const behaviour of project.behaviours) {
    assert(thingIds.has(behaviour.thing_id), 'Behaviour target Thing is missing', 'dangling_reference');
    assert(behaviour.ir?.version === 1, 'Unsupported Behaviour IR version', 'ir_incompatible');
    const triggerPort = behaviour.ir?.trigger?.event_port_id;
    assert(portOwner.get(triggerPort) === behaviour.thing_id, 'Behaviour trigger must use a stable port on its Thing', 'invalid_port');
    for (const instruction of behaviour.ir.instructions ?? []) {
      assert(['set', 'toggle'].includes(instruction.op), `Unsupported Behaviour operation: ${instruction.op}`, 'ir_incompatible');
      assert(thingIds.has(instruction.thing_id), 'Behaviour instruction target is missing', 'dangling_reference');
    }
  }

  for (const connection of project.connections) {
    const fromOwner = portOwner.get(connection.from?.port_id);
    const toOwner = portOwner.get(connection.to?.port_id);
    assert(fromOwner === connection.from?.thing_id, 'Connection source must target a stable source port', 'invalid_port');
    assert(toOwner === connection.to?.thing_id, 'Connection destination must target a stable destination port', 'invalid_port');
  }

  for (const track of project.timeline) {
    assert(thingIds.has(track.target?.thing_id), 'Timeline target Thing is missing', 'dangling_reference');
    assert(Array.isArray(track.keyframes) && track.keyframes.length > 0, 'Timeline track needs keyframes', 'invalid_timeline');
  }

  for (const asset of project.assets) validateAsset(asset);

  assert(project.network && typeof project.network === 'object', 'Together declaration is required', 'invalid_network');
  for (const key of Object.keys(project.network)) {
    assert(['preset', 'spawn_scope', 'control', 'authority', 'replication', 'relevance'].includes(key), `Transport/session field ${key} is not canonical networking`, 'network_context_forbidden');
  }

  assert(project.collaboration && Array.isArray(project.collaboration.conflicts), 'People conflict state is invalid', 'invalid_collaboration');
  for (const conflict of project.collaboration.conflicts) {
    assert(Array.isArray(conflict.alternatives) && conflict.alternatives.length >= 2, 'Conflict must retain alternatives', 'invalid_collaboration');
  }
  return true;
}

function runtimeProjection(project) {
  return {
    things: deepClone(project.things),
    definitions: deepClone(project.definitions),
    behaviours: deepClone(project.behaviours),
    connections: deepClone(project.connections),
    timeline: deepClone(project.timeline),
    assets: deepClone(project.assets),
    network: deepClone(project.network)
  };
}

export function publish(project, { creationId = 'creation-browser-slice', requiredCapabilities = [], optionalCapabilities = [] } = {}) {
  validateProject(project);
  const semantic = runtimeProjection(project);
  rejectHostIdentity(semantic);
  const semanticDigest = sha256(semantic);
  const body = {
    format: 'SplashMX.PublishedCreationRevision',
    creation_id: creationId,
    source_project_id: project.project_id,
    source_project_revision: project.project_revision,
    semantic_digest: semanticDigest,
    compatibility: { schema_version: 1, ir_version: 1, required_features: ['things', 'behaviours', 'connections'] },
    capabilities: {
      required: [...requiredCapabilities].sort(),
      optional: [...optionalCapabilities].sort()
    },
    exact_dependency_lock: [],
    ...semantic
  };
  return { ...body, creation_revision_id: `sha256:${sha256(body)}` };
}

export function validatePublished(creation, runtime = {}) {
  assert(creation?.format === 'SplashMX.PublishedCreationRevision', 'This creation is not a published SplashMX revision', 'schema_incompatible');
  rejectHostIdentity(creation);
  assert(creation.compatibility?.schema_version === 1, 'This creation needs a newer SplashMX player', 'schema_incompatible');
  assert(creation.compatibility?.ir_version === 1, 'This creation needs a newer Behaviour player', 'ir_incompatible');
  const supportedFeatures = new Set(runtime.supportedFeatures ?? ['things', 'behaviours', 'connections', 'timeline', 'definitions', 'network']);
  for (const feature of creation.compatibility?.required_features ?? []) {
    assert(supportedFeatures.has(feature), `This player does not support required feature: ${feature}`, 'required_feature_unsupported');
  }
  const granted = new Set(runtime.grantedCapabilities ?? []);
  for (const capability of creation.capabilities?.required ?? []) {
    assert(granted.has(capability), `This creation is not allowed to use ${capability}`, 'required_capability_denied');
  }
  const semantic = {
    things: creation.things,
    definitions: creation.definitions,
    behaviours: creation.behaviours,
    connections: creation.connections,
    timeline: creation.timeline,
    assets: creation.assets,
    network: creation.network
  };
  assert(sha256(semantic) === creation.semantic_digest, 'Published creation integrity check failed', 'creation_digest_mismatch');
  const { creation_revision_id, ...revisionBody } = creation;
  assert(creation_revision_id === `sha256:${sha256(revisionBody)}`, 'Published revision identity does not match immutable publication data', 'creation_digest_mismatch');
  // Re-use project validation without smuggling publication-only fields into canonical project.
  validateProject({
    format: 'SplashMX.EditableProject', schema_version: 1,
    project_id: creation.source_project_id, project_revision: creation.source_project_revision,
    ...deepClone(semantic), collaboration: { conflicts: [] },
    authoring: { selected_thing_ids: [], presence: [], play_session: null }
  });
  return true;
}

export function activatePublished(creation, runtime = {}) {
  validatePublished(creation, runtime);
  return {
    creation_revision_id: creation.creation_revision_id,
    runtime: startPlay({
      format: 'SplashMX.EditableProject', schema_version: 1,
      project_id: creation.source_project_id, project_revision: creation.source_project_revision,
      things: deepClone(creation.things), definitions: deepClone(creation.definitions),
      behaviours: deepClone(creation.behaviours), connections: deepClone(creation.connections),
      timeline: deepClone(creation.timeline), assets: deepClone(creation.assets),
      network: deepClone(creation.network), collaboration: { conflicts: [] },
      authoring: { selected_thing_ids: [], presence: [], play_session: null }
    })
  };
}

export function sampleProject() {
  let project = createBlankProject();
  project = addThing(project, { thingId: 'button', name: 'Button', kind: 'button', x: 60, y: 60, text: 'Press me' });
  project = addThing(project, { thingId: 'lamp', name: 'Lamp', kind: 'lamp', x: 260, y: 60, text: 'Lamp', color: '#ffd45a' });
  project = groupThings(project, { groupId: 'controls', name: 'Controls', childIds: ['button', 'lamp'] });
  project = makeReusable(project, { groupId: 'controls', definitionId: 'def-controls' });
  project = attachBehaviour(project, {
    attachmentId: 'beh-button-toggle', thingId: 'button', source: 'rule', eventPort: 'button:activated',
    instructions: [{ op: 'set', thing_id: 'button', property: 'last_activation', value: true }]
  });
  project = connect(project, {
    connectionId: 'conn-button-lamp', fromThingId: 'button', fromPortId: 'button:activated',
    toThingId: 'lamp', toPortId: 'lamp:toggle'
  });
  project = addTimelineTrack(project, { trackId: 'track-lamp-x', thingId: 'lamp', property: 'x', keyframes: [{ t: 0, value: 260 }, { t: 1, value: 300 }] });
  project = setNetworkPreset(project, 'shared');
  project.assets.push({
    asset_id: 'asset-tone',
    revision: {
      digest: 'sha256:7fd6b2b450a86f6d53f6c2cf0ef7d4b5',
      source: { identity: 'fixture://tone.wav', name: 'tone.wav', mime: 'audio/wav' },
      media: { kind: 'audio', channels: 1, sample_rate: 48000, intended_role: 'interaction-cue' },
      provenance: { origin: 'SMX-019 fixture', author: 'SplashMX research harness' },
      licence: 'CC0-1.0',
      derivation: { kind: 'source', parents: [] }
    }
  });
  bump(project);
  validateProject(project);
  return project;
}
