import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { spawn, spawnSync } from 'node:child_process';
import { chromium } from 'playwright';
import { startRelay } from './relay.mjs';

const ROOT = path.resolve(process.argv[2] || '.');
const WEB_ROOT = path.join(ROOT, 'build', 'web');
const LINUX_BIN = path.join(ROOT, 'build', 'linux', 'smx017.x86_64');
const OUT_DIR = path.join(ROOT, 'artifacts');
const EXPECTED_DIGEST = 'dd5e7bb8b33ab447b4234fb8036453b248c5721e22b9f0e1c19cc57438e71580';
fs.mkdirSync(OUT_DIR, { recursive: true });

function assert(condition, message) {
  if (!condition) throw new Error(message);
}
function sleep(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }
function parseLine(line, records) {
  const marker = 'SMX017 ';
  const at = line.indexOf(marker);
  if (at < 0) return;
  try { records.push(JSON.parse(line.slice(at + marker.length))); }
  catch { /* Godot may interleave non-record diagnostics; ignore only non-JSON tails. */ }
}
function collector(stream, records, raw) {
  let pending = '';
  stream.on('data', (chunk) => {
    const text = pending + chunk.toString();
    const lines = text.split(/\r?\n/);
    pending = lines.pop() || '';
    for (const line of lines) { raw.push(line); parseLine(line, records); }
  });
  stream.on('end', () => { if (pending) { raw.push(pending); parseLine(pending, records); } });
}
async function waitFor(records, predicate, label, timeoutMs = 10000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const found = records.find(predicate);
    if (found) return found;
    await sleep(50);
  }
  throw new Error(`timeout waiting for ${label}; recent=${JSON.stringify(records.slice(-8))}`);
}
function last(records, predicate) {
  return [...records].reverse().find(predicate);
}
function semantic(snapshot) {
  return {
    avatar_x: snapshot.avatar_x,
    door_open: snapshot.door_open,
    controller: snapshot.controller,
    containment_parent: snapshot.containment_parent,
    lifecycle: snapshot.lifecycle,
    creation_revision_id: snapshot.creation_revision_id,
    creation_sha256: snapshot.creation_sha256,
    protected_assets: snapshot.protected_assets,
  };
}
function validateCanonical(record, label) {
  assert(record.creation_revision_id === 'smx017-topology-equivalence-v1', `${label}: revision changed`);
  assert(record.creation_sha256 === EXPECTED_DIGEST, `${label}: creation digest changed`);
  assert(Array.isArray(record.protected_assets) && record.protected_assets.length === 1, `${label}: protected bundle missing`);
  const asset = record.protected_assets[0];
  const required = ['asset_id','digest','source_identity','source_metadata','audio_media_semantics','provenance','licence','derivation'];
  assert(JSON.stringify(Object.keys(asset).sort()) === JSON.stringify(required.sort()), `${label}: protected bundle fields changed`);
}

function startStaticServer(port = 8060) {
  const mime = { '.html':'text/html', '.js':'text/javascript', '.wasm':'application/wasm', '.pck':'application/octet-stream', '.png':'image/png', '.ico':'image/x-icon' };
  const server = http.createServer((req, res) => {
    const pathname = decodeURIComponent(new URL(req.url, `http://127.0.0.1:${port}`).pathname);
    const rel = pathname === '/' ? 'index.html' : pathname.replace(/^\/+/, '');
    const file = path.resolve(WEB_ROOT, rel);
    if (!file.startsWith(path.resolve(WEB_ROOT) + path.sep) && file !== path.join(path.resolve(WEB_ROOT), 'index.html')) {
      res.writeHead(403); res.end('forbidden'); return;
    }
    fs.readFile(file, (err, data) => {
      if (err) { res.writeHead(404); res.end('not found'); return; }
      res.setHeader('Content-Type', mime[path.extname(file)] || 'application/octet-stream');
      res.setHeader('Cache-Control', 'no-store');
      res.end(data);
    });
  });
  return new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, '127.0.0.1', () => resolve(server));
  });
}

function pageUrl(room, topology, role, principal, extra = {}) {
  const q = new URLSearchParams({
    smx_room: room,
    smx_topology: topology,
    smx_role: role,
    smx_principal: principal,
    ...extra,
  });
  return `http://127.0.0.1:8060/index.html?${q}`;
}

function attachPage(page, records, raw, label) {
  page.on('console', (msg) => { const text = msg.text(); raw.push(`[${label}] ${text}`); parseLine(text, records); });
  page.on('pageerror', (err) => raw.push(`[${label}] PAGEERROR ${err.message}`));
  page.on('crash', () => raw.push(`[${label}] CRASH`));
}

function runOffline() {
  const args = ['--headless', '--', '--smx-topology=offline', '--smx-role=authority', '--smx-principal=alice'];
  const proc = spawnSync(LINUX_BIN, args, { encoding: 'utf8', timeout: 15000 });
  const records = [];
  const raw = `${proc.stdout || ''}\n${proc.stderr || ''}`.split(/\r?\n/);
  for (const line of raw) parseLine(line, records);
  assert(proc.status === 0, `offline runtime failed status=${proc.status}: ${raw.slice(-20).join('\n')}`);
  const snapshot = last(records, (r) => r.event === 'snapshot' && r.reason === 'offline_complete');
  assert(snapshot, 'offline final snapshot missing');
  validateCanonical(snapshot, 'offline');
  assert(snapshot.avatar_x === 4 && snapshot.door_open === true, 'offline accepted-input outcome incorrect');
  return { records, raw, snapshot };
}

function spawnDedicated(room) {
  const records = [], raw = [];
  const proc = spawn(LINUX_BIN, [
    '--headless', '--', '--smx-topology=dedicated', '--smx-role=server',
    '--smx-principal=server', `--smx-room=${room}`, '--smx-no_reconnect=1'
  ], { stdio: ['ignore','pipe','pipe'] });
  collector(proc.stdout, records, raw); collector(proc.stderr, records, raw);
  return { proc, records, raw };
}

async function main() {
  assert(fs.existsSync(path.join(WEB_ROOT, 'index.html')), `web export missing at ${WEB_ROOT}`);
  assert(fs.existsSync(LINUX_BIN), `Linux export missing at ${LINUX_BIN}`);
  fs.chmodSync(LINUX_BIN, 0o755);
  const godotVersionPath = path.join(ROOT, 'build', 'godot-version.txt');
  const godotVersion = fs.existsSync(godotVersionPath) ? fs.readFileSync(godotVersionPath, 'utf8').trim() : 'unknown';
  const relay = startRelay(8877);
  const staticServer = await startStaticServer(8060);
  const browser = await chromium.launch({ headless: true, args: ['--use-gl=swiftshader', '--enable-webgl', '--disable-dev-shm-usage'] });
  const result = { godot_version: godotVersion, browser_version: browser.version(), node_version: process.version, observations: {} };
  let dedicated;
  try {
    const offline = runOffline();
    result.observations.offline = { snapshot: semantic(offline.snapshot) };

    // Peer-hosted: authority and participant use separate browser contexts so
    // ordinary tab focus does not accidentally become the failure injector.
    const hostCtx = await browser.newContext();
    const clientCtx = await browser.newContext();
    const host = await hostCtx.newPage();
    const client = await clientCtx.newPage();
    const hostRecords = [], clientRecords = [], peerRaw = [];
    attachPage(host, hostRecords, peerRaw, 'peer-host');
    attachPage(client, clientRecords, peerRaw, 'peer-client');
    await host.goto(pageUrl('peer', 'peer', 'authority', 'host'), { waitUntil: 'load' });
    await waitFor(hostRecords, (r) => r.event === 'welcome', 'peer host welcome', 15000);
    await client.goto(pageUrl('peer', 'peer', 'client', 'alice', { smx_lifecycle_watch: '1' }), { waitUntil: 'load' });
    const firstWelcome = await waitFor(clientRecords, (r) => r.event === 'welcome', 'peer client welcome', 15000);
    await waitFor(hostRecords, (r) => r.event === 'snapshot' && r.avatar_x === 4 && r.door_open === true, 'peer authority final state', 12000);
    await waitFor(clientRecords, (r) => r.event === 'snapshot' && r.reason === 'client_scenario_complete', 'peer client completion', 12000);
    const peerSnapshot = last(hostRecords, (r) => r.event === 'snapshot' && r.avatar_x === 4 && r.door_open === true);
    validateCanonical(peerSnapshot, 'peer');
    for (const reason of ['duplicate_or_reordered_input','undeclared_input','forbidden_host_authority_key','remote_state_assertion','oversized_ingress']) {
      assert(hostRecords.some((r) => r.event === 'reject' && r.reason === reason), `peer adversary not rejected: ${reason}`);
    }
    assert(clientRecords.some((r) => r.event === 'event_queued'), 'reliable event was not queued while Thing unloaded');
    assert(clientRecords.some((r) => r.event === 'event_deduplicated'), 'duplicated reliable event was not deduplicated');
    assert(clientRecords.some((r) => r.event === 'state_coalesced'), 'latest state was not coalesced while unloaded/irrelevant');
    assert(clientRecords.some((r) => r.event === 'relevance' && r.relevant === false && r.lifecycle === 'active'), 'relevance leave conflated with unload/destruction');
    const transfer = hostRecords.find((r) => r.event === 'control_transfer' && r.controller === 'bob');
    assert(transfer?.authority_unchanged && transfer?.containment_unchanged, 'control transfer rewrote authority/containment');

    // Measure a real browser lifecycle interruption. First try an ordinary
    // background tab; if headless Chromium reports it still visible, use the
    // Chromium lifecycle freeze state and record that distinction explicitly.
    const beforeLifecycleCount = clientRecords.length;
    let lifecycleMechanism = 'background-tab';
    const dummy = await clientCtx.newPage();
    await dummy.goto('about:blank'); await dummy.bringToFront();
    await sleep(150);
    let visibility = await client.evaluate(() => document.visibilityState);
    if (visibility !== 'hidden') {
      lifecycleMechanism = 'cdp-frozen-fallback';
      const cdp = await clientCtx.newCDPSession(client);
      await cdp.send('Page.setWebLifecycleState', { state: 'frozen' });
      await sleep(2200);
      await cdp.send('Page.setWebLifecycleState', { state: 'active' });
    } else {
      await sleep(2200);
    }
    await dummy.close(); await client.bringToFront();
    const reconnected = await waitFor(clientRecords.slice(beforeLifecycleCount), (r) => r.event === 'reconnected', 'browser reconnect after suspension', 10000);
    assert(reconnected.principal === 'alice', 'reconnect changed durable principal');
    assert(reconnected.transport_peer_id !== firstWelcome.transport_peer_id, 'reconnect reused transient peer id');
    result.observations.browser_lifecycle = {
      mechanism: lifecycleMechanism,
      observed_visibility_state: visibility,
      previous_transport_peer_id: firstWelcome.transport_peer_id,
      new_transport_peer_id: reconnected.transport_peer_id,
      application_timeout_ms: 1400,
    };

    // Confirmed peer checkpoint permits host migration and increments epoch.
    const peerBeforeClose = relay.roomSnapshot('peer');
    assert(peerBeforeClose?.checkpoint, 'peer checkpoint missing before host loss');
    const oldEpoch = peerBeforeClose.authorityEpoch;
    await host.close();
    const granted = await waitFor(clientRecords, (r) => r.event === 'authority_granted' && r.authority_epoch > oldEpoch, 'peer authority migration', 10000);
    assert(granted.checkpoint_confirmed === true, 'peer migration did not require checkpoint');
    relay.injectToAuthority('peer', { type:'input', authority_epoch: oldEpoch, input_seq:99, kind:'move', dx:1 }, { principal:'alice', connId:'stale-peer', role:'client' });
    await waitFor(clientRecords, (r) => r.event === 'reject' && r.reason === 'stale_authority_epoch', 'stale prior-epoch rejection', 5000);
    const migratedSnapshot = await waitFor(clientRecords, (r) => r.event === 'snapshot' && r.authority_epoch === granted.authority_epoch && r.avatar_x === 4, 'migrated semantic snapshot', 6000);
    validateCanonical(migratedSnapshot, 'peer-migrated');

    // Unconfirmed checkpoint loss is explicit and does not silently elect.
    const lossHostCtx = await browser.newContext();
    const lossClientCtx = await browser.newContext();
    const lossHost = await lossHostCtx.newPage();
    const lossClient = await lossClientCtx.newPage();
    const lossHostRecords = [], lossClientRecords = [];
    attachPage(lossHost, lossHostRecords, peerRaw, 'loss-host'); attachPage(lossClient, lossClientRecords, peerRaw, 'loss-client');
    await lossHost.goto(pageUrl('peer-loss', 'peer', 'authority', 'host-loss', { smx_no_checkpoint:'1' }), { waitUntil:'load' });
    await waitFor(lossHostRecords, (r) => r.event === 'welcome', 'loss host welcome', 10000);
    await lossClient.goto(pageUrl('peer-loss', 'peer', 'client', 'alice'), { waitUntil:'load' });
    await waitFor(lossClientRecords, (r) => r.event === 'welcome', 'loss client welcome', 10000);
    await lossHost.close();
    await waitFor(lossClientRecords, (r) => r.event === 'authority_unavailable' && r.reason === 'checkpoint_unconfirmed', 'unconfirmed peer loss', 6000);
    await lossClient.close(); await lossHostCtx.close(); await lossClientCtx.close();

    result.observations.peer = {
      snapshot: semantic(peerSnapshot),
      migrated_snapshot: semantic(migratedSnapshot),
      authority_epoch_before_loss: oldEpoch,
      authority_epoch_after_migration: granted.authority_epoch,
      adversarial_rejections: hostRecords.filter((r) => r.event === 'reject').map((r) => r.reason),
    };
    await client.close(); await hostCtx.close(); await clientCtx.close();

    // Dedicated authority: same exported project runs headless; browser remains
    // a client and is never promoted when the server disappears.
    dedicated = spawnDedicated('dedicated');
    await waitFor(dedicated.records, (r) => r.event === 'welcome', 'dedicated server welcome', 10000);
    const dcCtx = await browser.newContext();
    const dc = await dcCtx.newPage();
    const dcRecords = [], dcRaw = [];
    attachPage(dc, dcRecords, dcRaw, 'dedicated-client');
    await dc.goto(pageUrl('dedicated', 'dedicated', 'client', 'alice'), { waitUntil:'load' });
    await waitFor(dcRecords, (r) => r.event === 'welcome', 'dedicated client welcome', 10000);
    const dedicatedSnapshot = await waitFor(dedicated.records, (r) => r.event === 'snapshot' && r.avatar_x === 4 && r.door_open === true, 'dedicated final state', 12000);
    await waitFor(dcRecords, (r) => r.event === 'snapshot' && r.reason === 'client_scenario_complete', 'dedicated client completion', 12000);
    validateCanonical(dedicatedSnapshot, 'dedicated');
    for (const reason of ['duplicate_or_reordered_input','undeclared_input','forbidden_host_authority_key','remote_state_assertion','oversized_ingress']) {
      assert(dedicated.records.some((r) => r.event === 'reject' && r.reason === reason), `dedicated adversary not rejected: ${reason}`);
    }
    dedicated.proc.kill('SIGTERM');
    await new Promise((resolve) => dedicated.proc.once('exit', resolve));
    const unavailable = await waitFor(dcRecords, (r) => r.event === 'authority_unavailable' && r.reason === 'dedicated_authority_disconnected_fail_closed', 'dedicated fail-closed', 6000);
    const dedicatedRoom = relay.roomSnapshot('dedicated');
    assert(!dedicatedRoom.authorityPrincipal, 'dedicated client was promoted after server loss');
    assert(unavailable.topology === 'dedicated', 'dedicated failure reported under wrong topology');
    result.observations.dedicated = { snapshot: semantic(dedicatedSnapshot), authority_after_server_loss: dedicatedRoom.authorityPrincipal || null };
    await dc.close(); await dcCtx.close();

    // Authoritative semantic equivalence excludes explicitly allowed runtime
    // divergences such as authority principal/epoch, connection IDs and latency.
    const expected = semantic(offline.snapshot);
    const peerSem = semantic(peerSnapshot);
    const dedicatedSem = semantic(dedicatedSnapshot);
    assert(JSON.stringify(peerSem) === JSON.stringify(expected), `peer semantic divergence: ${JSON.stringify({expected,peerSem})}`);
    assert(JSON.stringify(dedicatedSem) === JSON.stringify(expected), `dedicated semantic divergence: ${JSON.stringify({expected,dedicatedSem})}`);

    function measuredLatencies(clientRecords, authorityRecords) {
      const out = [];
      for (const pred of clientRecords.filter((r) => r.event === 'prediction')) {
        const accepted = authorityRecords.find((r) => r.event === 'input_accepted' && r.input_seq === pred.input_seq);
        if (accepted) out.push({ input_seq: pred.input_seq, client_to_authority_wall_ms: accepted.wall_ms - pred.wall_ms });
      }
      return out;
    }
    result.observations.peer.latency_samples = measuredLatencies(clientRecords, hostRecords);
    result.observations.dedicated.latency_samples = measuredLatencies(dcRecords, dedicated.records);
    result.equivalent = true;
    result.allowed_divergences = [
      'transport peer/connection ids', 'latency and packet timing', 'current authority host/principal',
      'authority epoch after migration/failure', 'browser reconnect mechanics', 'prediction cache',
      'headless presentation omission', 'deployment/scaling policy'
    ];
    fs.writeFileSync(path.join(OUT_DIR, 'smx017-integration-results.json'), JSON.stringify(result, null, 2) + '\n');
    console.log(`SMX017 INTEGRATION PASS ${JSON.stringify({godotVersion, browser: browser.version(), peerLatency: result.observations.peer.latency_samples, dedicatedLatency: result.observations.dedicated.latency_samples})}`);
  } catch (err) {
    result.equivalent = false; result.error = String(err?.stack || err);
    fs.writeFileSync(path.join(OUT_DIR, 'smx017-integration-results.json'), JSON.stringify(result, null, 2) + '\n');
    throw err;
  } finally {
    if (dedicated?.proc && !dedicated.proc.killed) dedicated.proc.kill('SIGKILL');
    await browser.close();
    await relay.close();
    await new Promise((resolve) => staticServer.close(resolve));
  }
}

await main();
