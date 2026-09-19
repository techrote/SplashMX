import assert from 'node:assert/strict';
import test from 'node:test';
import {
  activatePublished, activateThing, addConflict, addThing, addTimelineTrack,
  attachBehaviour, canonicalStringify, connect, createBlankProject, editableSnapshot,
  groupThings, makeReusable, publish, replaceAsset, sampleProject,
  setAdvancedNetwork, setNetworkPreset, setTransientPresence, sha256, startPlay,
  stopPlay, validateAsset, validateProject, validatePublished
} from './model.mjs';

const expectCode = (fn, code) => assert.throws(fn, error => error?.code === code);
const deep = value => structuredClone(value);

// UXG-001 — blank canvas -> Thing without engine/build vocabulary.
test('01 blank project creates ordinary Thing with stable identity', () => {
  const blank = createBlankProject();
  const project = addThing(blank, { thingId: 'a', name: 'A' });
  assert.equal(project.things[0].thing_id, 'a');
  assert.equal(project.things[0].parent_id, null);
});

// UXG-002 — Timeline optional; non-Timeline remains valid.
test('02 project is interactive without Timeline', () => {
  let project = createBlankProject();
  project = addThing(project, { thingId: 'a', name: 'A' });
  project = attachBehaviour(project, { attachmentId: 'b', thingId: 'a', source: 'rule', eventPort: 'a:activated', instructions: [{ op: 'toggle', thing_id: 'a', property: 'toggled' }] });
  assert.equal(project.timeline.length, 0);
  validateProject(project);
});

test('03 Timeline targets stable Thing identity', () => {
  let project = addThing(createBlankProject(), { thingId: 'a', name: 'A' });
  project = addTimelineTrack(project, { trackId: 't', thingId: 'a', keyframes: [{ t: 0, value: 0 }, { t: 1, value: 20 }] });
  assert.equal(project.timeline[0].target.thing_id, 'a');
});

// UXG-003 — Rule and advanced Behaviour share IR.
test('04 beginner Rule and advanced Behaviour share identical IR shape', () => {
  let base = addThing(createBlankProject(), { thingId: 'a', name: 'A' });
  const instructions = [{ op: 'toggle', thing_id: 'a', property: 'toggled' }];
  const rule = attachBehaviour(base, { attachmentId: 'rule', thingId: 'a', source: 'rule', eventPort: 'a:activated', instructions });
  const advanced = attachBehaviour(base, { attachmentId: 'advanced', thingId: 'a', source: 'advanced', eventPort: 'a:activated', instructions });
  assert.deepEqual(rule.behaviours[0].ir, advanced.behaviours[0].ir);
});

// UXG-004 — stable ports, not tree paths.
test('05 Connection uses stable endpoints', () => {
  let project = createBlankProject();
  project = addThing(project, { thingId: 'a', name: 'A' });
  project = addThing(project, { thingId: 'b', name: 'B' });
  project = connect(project, { connectionId: 'c', fromThingId: 'a', fromPortId: 'a:activated', toThingId: 'b', toPortId: 'b:toggle' });
  assert.equal(project.connections[0].from.port_id, 'a:activated');
});

test('06 hierarchy path masquerading as PortId is rejected', () => {
  const project = addThing(createBlankProject(), { thingId: 'a', name: 'A' });
  const broken = deep(project);
  broken.things[0].ports[0].port_id = '/root/a/activate';
  expectCode(() => validateProject(broken), 'invalid_port');
});

// UXG-005 — group -> reusable preserves concrete Thing IDs.
test('07 make reusable preserves first-instance Thing identities', () => {
  let project = createBlankProject();
  project = addThing(project, { thingId: 'a', name: 'A' });
  project = addThing(project, { thingId: 'b', name: 'B' });
  project = groupThings(project, { groupId: 'g', childIds: ['a', 'b'] });
  const before = project.things.map(t => t.thing_id).sort();
  project = makeReusable(project, { groupId: 'g', definitionId: 'd' });
  assert.deepEqual(project.things.map(t => t.thing_id).sort(), before);
  assert.equal(project.definitions[0].root_thing_id, 'g');
});

test('08 leaf cannot shortcut directly into reusable definition', () => {
  const project = addThing(createBlankProject(), { thingId: 'a', name: 'A' });
  expectCode(() => makeReusable(project, { groupId: 'a', definitionId: 'd' }), 'invalid_reuse');
});

// UXG-006 — Play/Stop plane separation.
test('09 Play mutation does not rewrite authored state', () => {
  const project = sampleProject();
  const before = canonicalStringify(project);
  const runtime = startPlay(project);
  activateThing(runtime, 'button');
  assert.equal(canonicalStringify(project), before);
  assert.notEqual(runtime.things.find(t => t.thing_id === 'lamp').state.toggled, project.things.find(t => t.thing_id === 'lamp').state.toggled);
});

test('10 Stop discards transient runtime', () => {
  const project = sampleProject();
  const runtime = startPlay(project);
  assert.equal(stopPlay(runtime), null);
});

// UXG-007 — save/reload excludes selection/presence/play session.
test('11 editable snapshot strips transient authoring context', () => {
  let project = sampleProject();
  project.authoring.selected_thing_ids = ['button'];
  project.authoring.play_session = { id: 'play-1' };
  project = setTransientPresence(project, [{ principal: 'bob', selected: 'lamp' }]);
  const saved = editableSnapshot(project);
  assert.deepEqual(saved.authoring, { selected_thing_ids: [], presence: [], play_session: null });
});

test('12 durable collaboration conflict remains in editable snapshot', () => {
  const project = addConflict(sampleProject(), { conflict_id: 'cf', locus: { thing_id: 'lamp', property: 'color' }, alternatives: ['yellow', 'blue'] });
  const saved = editableSnapshot(project);
  assert.equal(saved.collaboration.conflicts.length, 1);
  assert.equal(saved.collaboration.conflicts[0].alternatives.length, 2);
});

// UXG-008 — generic-player Publish/load.
test('13 Publish creates deterministic immutable creation revision', () => {
  const project = sampleProject();
  const a = publish(project);
  const b = publish(project);
  assert.equal(a.creation_revision_id, b.creation_revision_id);
  assert.equal(a.semantic_digest, b.semantic_digest);
  validatePublished(a);
});

test('14 generic player activates exact published revision', () => {
  const creation = publish(sampleProject());
  const active = activatePublished(creation);
  assert.equal(active.creation_revision_id, creation.creation_revision_id);
});

// UXG-009 — simple and advanced Together share declaration.
test('15 shared Together preset maps to explicit accepted axes', () => {
  const project = setNetworkPreset(sampleProject(), 'shared');
  assert.deepEqual(project.network, {
    preset: 'shared', spawn_scope: 'project', control: 'declared_controllers',
    authority: 'topology_policy', replication: 'shared_state', relevance: 'declared'
  });
});

test('16 advanced Together edits same declaration, not a second network model', () => {
  const base = setNetworkPreset(sampleProject(), 'shared');
  const advanced = setAdvancedNetwork(base, { replication: 'authoritative_state', control: 'intent_only' });
  assert.equal(advanced.network.authority, base.network.authority);
  assert.equal(advanced.network.preset, 'custom');
});

test('17 transient peer or transport fields are rejected from authored network', () => {
  const project = sampleProject();
  expectCode(() => setAdvancedNetwork(project, { peer_id: 'p1' }), 'network_context_forbidden');
});

// UXG-010 — People stays separate from Together.
test('18 People presence does not mutate Together declaration', () => {
  const project = sampleProject();
  const networkBefore = deep(project.network);
  const withPresence = setTransientPresence(project, [{ principal: 'bob' }]);
  assert.deepEqual(withPresence.network, networkBefore);
  assert.equal(withPresence.authoring.presence.length, 1);
});

test('19 conflict alternatives must remain human-visible', () => {
  const broken = sampleProject();
  broken.collaboration.conflicts.push({ conflict_id: 'bad', alternatives: ['winner-only'] });
  expectCode(() => validateProject(broken), 'invalid_collaboration');
});

// UXG-011 — author-language failure contracts.
test('20 missing Thing reference yields typed dangling_reference', () => {
  const project = sampleProject();
  const broken = deep(project);
  broken.timeline[0].target.thing_id = 'missing';
  expectCode(() => validateProject(broken), 'dangling_reference');
});

test('21 unsupported IR yields typed ir_incompatible before execution', () => {
  const project = sampleProject();
  const broken = deep(project);
  broken.behaviours[0].ir.version = 99;
  expectCode(() => validateProject(broken), 'ir_incompatible');
});

// UXG-012 — protected media revision atomicity.
test('22 protected asset complete revision validates', () => {
  assert.equal(validateAsset(sampleProject().assets[0]), true);
});

test('23 partial protected asset replacement is rejected atomically', () => {
  const project = sampleProject();
  const before = canonicalStringify(project.assets[0]);
  expectCode(() => replaceAsset(project, 'asset-tone', { digest: 'sha256:new' }), 'asset_revision_incomplete');
  assert.equal(canonicalStringify(project.assets[0]), before);
});

test('24 complete protected asset replacement preserves AssetId', () => {
  const project = sampleProject();
  const next = deep(project.assets[0].revision);
  next.digest = 'sha256:8fd6b2b450a86f6d53f6c2cf0ef7d4b5';
  next.source.identity = 'fixture://tone-v2.wav';
  next.provenance.origin = 'SMX-019 fixture v2';
  next.derivation = { kind: 'replacement', parents: [project.assets[0].revision.digest] };
  const replaced = replaceAsset(project, 'asset-tone', next);
  assert.equal(replaced.assets[0].asset_id, 'asset-tone');
  assert.equal(replaced.assets[0].revision.digest, next.digest);
});

// Additional adversarial/boundary coverage.
test('25 duplicate Thing identity is rejected', () => {
  const project = sampleProject();
  project.things.push(deep(project.things[0]));
  expectCode(() => validateProject(project), 'duplicate_identity');
});

test('26 dangling Connection endpoint is rejected', () => {
  const project = sampleProject();
  project.connections[0].to.thing_id = 'missing';
  expectCode(() => validateProject(project), 'invalid_port');
});

test('27 forbidden Godot host identity is recursively rejected', () => {
  const project = sampleProject();
  project.things[0].state.godot_node = 42;
  expectCode(() => validateProject(project), 'host_identity_forbidden');
});

test('28 canonical ConnectionId is not confused with transient connection identity', () => {
  const project = sampleProject();
  assert.doesNotThrow(() => validateProject(project));
  const broken = deep(project);
  broken.things[0].state.connection_handle = 'ws-77';
  expectCode(() => validateProject(broken), 'host_identity_forbidden');
});

test('29 publish excludes authoring and collaboration planes', () => {
  let project = sampleProject();
  project = setTransientPresence(project, [{ principal: 'bob' }]);
  project = addConflict(project, { conflict_id: 'cf', locus: { thing_id: 'lamp' }, alternatives: ['a', 'b'] });
  const creation = publish(project);
  assert.equal(Object.hasOwn(creation, 'authoring'), false);
  assert.equal(Object.hasOwn(creation, 'collaboration'), false);
});

test('30 tampered published semantic data fails digest before activation', () => {
  const creation = publish(sampleProject());
  creation.things[0].state.text = 'tampered';
  expectCode(() => validatePublished(creation), 'creation_digest_mismatch');
});

test('31 unsupported required feature fails before activation', () => {
  const creation = publish(sampleProject());
  creation.compatibility.required_features.push('future-physics');
  expectCode(() => validatePublished(creation, { supportedFeatures: ['things', 'behaviours', 'connections'] }), 'required_feature_unsupported');
});

test('32 required capability denial fails closed while optional denial does not', () => {
  const required = publish(sampleProject(), { requiredCapabilities: ['camera'] });
  expectCode(() => validatePublished(required, { grantedCapabilities: [] }), 'required_capability_denied');
  const optional = publish(sampleProject(), { optionalCapabilities: ['camera'] });
  assert.doesNotThrow(() => validatePublished(optional, { grantedCapabilities: [] }));
  assert.notEqual(required.creation_revision_id, optional.creation_revision_id);
});

test('33 published protected media exactly matches editable source bundle', () => {
  const project = sampleProject();
  const creation = publish(project);
  assert.deepEqual(creation.assets[0], project.assets[0]);
});

test('34 canonical serialization/digest is order-insensitive for object keys', () => {
  const a = { z: 1, a: { q: 2, b: 3 } };
  const b = { a: { b: 3, q: 2 }, z: 1 };
  assert.equal(canonicalStringify(a), canonicalStringify(b));
  assert.equal(sha256(a), sha256(b));
});
