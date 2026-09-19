import {
  activateThing, addConflict, addThing, addTimelineTrack, attachBehaviour,
  connect, createBlankProject, editableSnapshot, groupThings, makeReusable,
  publish, setNetworkPreset, setTransientPresence, startPlay, stopPlay,
  validateProject
} from './model.mjs';

const STORAGE_KEY = 'smx019.editable.v1';
const $ = selector => document.querySelector(selector);
const status = $('#status');
let project = loadSaved() ?? createBlankProject();
let runtime = null;
let published = null;
let gestures = Number(sessionStorage.getItem('smx019.gestures') ?? 0);

function storageDenied() {
  return new URLSearchParams(location.search).get('deny_storage') === '1';
}

function setStatus(message, kind = '') {
  status.textContent = message;
  status.className = kind;
}

function loadSaved() {
  if (storageDenied()) return null;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const value = JSON.parse(raw);
    validateProject(value);
    return value;
  } catch {
    return null;
  }
}

function save() {
  if (storageDenied()) throw Object.assign(new Error('This browser cannot save this project here.'), { code: 'storage_unavailable' });
  const snapshot = editableSnapshot(project);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot));
  setStatus('Saved.', 'ok');
  return snapshot;
}

function renderThing(container, thing, interactive = false) {
  if (thing.kind === 'group') {
    const group = document.createElement('div');
    group.className = 'thing group';
    group.dataset.thingId = thing.thing_id;
    group.style.left = '28px';
    group.style.top = '24px';
    group.textContent = thing.name;
    container.append(group);
    return;
  }
  const element = thing.kind === 'button' && interactive ? document.createElement('button') : document.createElement('div');
  element.className = `thing ${thing.kind}${thing.state.toggled ? ' on' : ''}`;
  element.dataset.thingId = thing.thing_id;
  element.style.left = `${thing.state.x}px`;
  element.style.top = `${thing.state.y}px`;
  element.style.background = thing.state.toggled ? '#fff0a5' : thing.state.color;
  element.textContent = thing.state.text;
  if (interactive && thing.kind === 'button') {
    element.addEventListener('click', () => {
      activateThing(runtime, thing.thing_id);
      render();
    });
  }
  container.append(element);
}

function render() {
  const list = $('#thing-list');
  list.replaceChildren(...project.things.map(thing => {
    const li = document.createElement('li');
    li.textContent = thing.name;
    li.dataset.thingId = thing.thing_id;
    return li;
  }));
  const stage = $('#stage');
  stage.replaceChildren();
  project.things.forEach(thing => renderThing(stage, thing, false));
  const preview = $('#preview');
  preview.replaceChildren();
  if (!runtime) {
    const em = document.createElement('em');
    em.textContent = 'Press Play to interact.';
    preview.append(em);
  } else {
    runtime.things.forEach(thing => renderThing(preview, thing, true));
  }
  $('#components').textContent = project.definitions.length ? `${project.definitions.length} reusable part ready.` : 'No reusable parts yet.';
  $('#together-preset').value = ['local','per_player','shared','authority_controlled'].includes(project.network.preset) ? project.network.preset : 'shared';
  $('#network-control').value = project.network.control;
  $('#network-authority').value = project.network.authority;
  $('#network-replication').value = project.network.replication;
  $('#network-relevance').value = project.network.relevance;
  $('#people').textContent = `${project.authoring.presence.length} here now · ${project.collaboration.conflicts.length} competing edit(s)`;
  $('#inspect').textContent = JSON.stringify({
    things: project.things.map(t => t.thing_id),
    behaviours: project.behaviours.map(b => b.attachment_id),
    connections: project.connections.map(c => c.connection_id),
    definitions: project.definitions.map(d => d.definition_id),
    timeline: project.timeline.map(t => t.track_id),
    network: project.network,
    published: published?.creation_revision_id ?? null
  }, null, 2);
}

function ensure(predicate, message) {
  if (!predicate) throw Object.assign(new Error(message), { code: 'workflow_incomplete' });
}

const actions = {
  'add-button'() {
    if (!project.things.some(t => t.thing_id === 'button')) project = addThing(project, { thingId:'button', name:'Button', kind:'button', x:60, y:70, text:'Press me' });
    setStatus('Button Thing added.', 'ok');
  },
  'add-lamp'() {
    if (!project.things.some(t => t.thing_id === 'lamp')) project = addThing(project, { thingId:'lamp', name:'Lamp', kind:'lamp', x:270, y:70, text:'Lamp', color:'#ffd45a' });
    setStatus('Lamp Thing added.', 'ok');
  },
  'add-media'() {
    if (!project.assets.some(a => a.asset_id === 'asset-tone')) {
      project.assets.push({
        asset_id:'asset-tone',
        revision:{
          digest:'sha256:7fd6b2b450a86f6d53f6c2cf0ef7d4b5',
          source:{identity:'fixture://tone.wav',name:'tone.wav',mime:'audio/wav'},
          media:{kind:'audio',channels:1,sample_rate:48000,intended_role:'interaction-cue'},
          provenance:{origin:'SMX-019 fixture',author:'SplashMX research harness'},
          licence:'CC0-1.0',
          derivation:{kind:'source',parents:[]}
        }
      });
      project.project_revision += 1;
      validateProject(project);
    }
    setStatus('Sound added with its source details.', 'ok');
  },
  group() {
    ensure(project.things.some(t => t.thing_id === 'button') && project.things.some(t => t.thing_id === 'lamp'), 'Add Button and Lamp Things first.');
    if (!project.things.some(t => t.thing_id === 'controls')) project = groupThings(project, { groupId:'controls', name:'Controls', childIds:['button','lamp'] });
    setStatus('Things grouped.', 'ok');
  },
  reuse() {
    ensure(project.things.some(t => t.thing_id === 'controls'), 'Group the Things first.');
    if (!project.definitions.some(d => d.definition_id === 'def-controls')) project = makeReusable(project, { groupId:'controls', definitionId:'def-controls' });
    setStatus('Group is now reusable; its Things kept their identities.', 'ok');
  },
  rule() {
    ensure(project.things.some(t => t.thing_id === 'button'), 'Add the Button Thing first.');
    if (!project.behaviours.some(b => b.attachment_id === 'beh-button')) project = attachBehaviour(project, {
      attachmentId:'beh-button', thingId:'button', source:'rule', eventPort:'button:activated',
      instructions:[{op:'set',thing_id:'button',property:'last_activation',value:true}]
    });
    setStatus('Rule added as a Behaviour.', 'ok');
  },
  connect() {
    ensure(project.things.some(t => t.thing_id === 'button') && project.things.some(t => t.thing_id === 'lamp'), 'Add Button and Lamp Things first.');
    if (!project.connections.some(c => c.connection_id === 'conn-button-lamp')) project = connect(project, {
      connectionId:'conn-button-lamp', fromThingId:'button', fromPortId:'button:activated',
      toThingId:'lamp', toPortId:'lamp:toggle'
    });
    setStatus('Connection added.', 'ok');
  },
  timeline() {
    ensure(project.things.some(t => t.thing_id === 'lamp'), 'Add the Lamp Thing first.');
    if (!project.timeline.some(t => t.track_id === 'track-lamp-x')) project = addTimelineTrack(project, {
      trackId:'track-lamp-x', thingId:'lamp', property:'x', keyframes:[{t:0,value:270},{t:1,value:310}]
    });
    setStatus('Timeline motion added.', 'ok');
  },
  play() {
    runtime = startPlay(project);
    project.authoring.play_session = { local: true };
    setStatus('Playing. Edit state stays separate.', 'ok');
  },
  stop() {
    runtime = stopPlay(runtime);
    project.authoring.play_session = null;
    setStatus('Stopped. Authored state is unchanged.', 'ok');
  },
  save,
  async publish() {
    published = publish(project);
    const response = await fetch('/api/publish', { method:'POST', headers:{'content-type':'application/json'}, body:JSON.stringify(published) });
    if (!response.ok) throw new Error((await response.json()).message ?? 'Publish could not complete.');
    const stored = await response.json();
    ensure(stored.creation_revision_id === published.creation_revision_id, 'Published revision changed unexpectedly.');
    localStorage.setItem(`smx019.published.${published.creation_revision_id}`, JSON.stringify(published));
    $('#player-frame').src = `/player.html?rev=${encodeURIComponent(published.creation_revision_id)}`;
    setStatus('Published. The generic player is loading the exact revision.', 'ok');
  },
  presence() {
    project = setTransientPresence(project, [{principal:'bob', display_name:'Bob', selected:'lamp'}]);
    setStatus('Collaborator presence shown only in People.', 'ok');
  },
  conflict() {
    if (!project.collaboration.conflicts.some(c => c.conflict_id === 'cf-color')) project = addConflict(project, {
      conflict_id:'cf-color', locus:{thing_id:'lamp',property:'color'}, alternatives:['gold','blue']
    });
    setStatus('Competing edit retained for review.', 'ok');
  }
};

document.addEventListener('click', async event => {
  const action = event.target.closest('[data-action]')?.dataset.action;
  if (!action || !actions[action]) return;
  gestures += 1;
  sessionStorage.setItem('smx019.gestures', String(gestures));
  try { await actions[action](); } catch (error) { setStatus(error.message, 'error'); }
  render();
});

$('#together-preset').addEventListener('change', event => {
  gestures += 1;
  project = setNetworkPreset(project, event.target.value);
  setStatus('Together settings updated.', 'ok');
  render();
});

window.addEventListener('message', event => {
  if (event.data?.type === 'smx019-player-ready') setStatus(`Published player ready: ${event.data.creation_revision_id.slice(0, 18)}…`, 'ok');
});

if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {});
window.__SMX019__ = {
  getProject: () => structuredClone(project),
  getRuntime: () => runtime ? structuredClone(runtime) : null,
  getPublished: () => published ? structuredClone(published) : null,
  getGestures: () => gestures,
  storageDenied
};
render();
