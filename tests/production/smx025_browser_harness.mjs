import { chromium } from 'playwright';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';

const MODULE_PATH = path.resolve('src/splashmx/storage/browser_indexeddb.mjs');
const ARTIFACT = path.resolve('artifacts/smx025-browser-results.json');
const moduleSource = fs.readFileSync(MODULE_PATH, 'utf8');
const pageSource = '<!doctype html><meta charset="utf-8"><title>SMX-025 browser persistence</title>';

const server = http.createServer((req, res) => {
  if (req.url?.startsWith('/store.mjs')) {
    res.writeHead(200, { 'content-type': 'text/javascript', 'cache-control': 'no-store' });
    res.end(moduleSource);
    return;
  }
  res.writeHead(200, { 'content-type': 'text/html', 'cache-control': 'no-store' });
  res.end(pageSource);
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const origin = `http://127.0.0.1:${server.address().port}/`;

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext();
const page = await context.newPage();
await page.goto(origin);

const result = await page.evaluate(async () => {
  const smx = await import('/store.mjs');
  const encoder = new TextEncoder();
  const decoder = new TextDecoder();
  const protectedFields = [
    'source_digest',
    'source_identity',
    'source_metadata',
    'audio_or_media_semantics',
    'provenance',
    'licence_attribution',
    'derivation_lineage',
  ];

  const bundle = marker => ({
    asset_id: 'music',
    revision_digest: `sha256:${marker.repeat(64)}`,
    source_digest: `sha256:${marker.repeat(64)}`,
    source_identity: { kind: 'author-import', logical_name: 'music.wav', marker },
    source_metadata: { bytes: marker === 'a' ? 4096 : 8192, extension: 'wav', marker },
    audio_or_media_semantics: { kind: 'audio', channels: 2, sample_rate: 48000, loop: marker === 'a', marker },
    provenance: { creator: 'fixture-author', capture: `capture-${marker}`, marker },
    licence_attribution: { licence: 'CC0-1.0', attribution: marker, marker },
    derivation_lineage: [{ operation: 'trim', parent: `parent-${marker}`, marker }],
  });

  const payload = (revisionId, marker) => {
    const protectedAsset = bundle(marker);
    return {
      projectId: 'project-browser',
      revisionId,
      rootManifest: encoder.encode(JSON.stringify({
        format: 'splashmx-test-project-revision',
        project_id: 'project-browser',
        revision_id: revisionId,
        shard: '0:0',
        marker,
      })),
      shards: new Map([['0:0', encoder.encode(JSON.stringify({ protectedAsset }))]]),
    };
  };

  const assertComplete = (loaded, expectedRevision, expectedMarker) => {
    if (loaded.revisionId !== expectedRevision) {
      throw new Error(`expected ${expectedRevision}, reopened ${loaded.revisionId}`);
    }
    const shard = JSON.parse(decoder.decode(loaded.shards.get('0:0')));
    const asset = shard.protectedAsset;
    for (const field of protectedFields) {
      if (!(field in asset)) throw new Error(`protected field ${field} missing`);
      const encoded = JSON.stringify(asset[field]);
      if (!encoded.includes(expectedMarker)) throw new Error(`protected field ${field} mixed away from ${expectedMarker}`);
    }
    return asset;
  };

  const makeStore = async suffix => {
    const store = new smx.IndexedDBProjectStore({ dbName: `smx025-${suffix}-${crypto.randomUUID()}` });
    await store.open();
    return store;
  };

  const precommitStages = smx.COMMIT_STAGES.filter(stage => stage !== 'committed');
  const crashEvidence = {};
  for (const stage of precommitStages) {
    const store = await makeStore(`crash-${stage}`);
    await store.saveSerialized(payload('r0', 'a'));
    let failure = null;
    try {
      await store.saveSerialized(payload('r1', 'b'), { faultAt: stage });
    } catch (error) {
      failure = { code: error.code, name: error.name };
    }
    if (failure?.code !== 'storage.interrupted') throw new Error(`fault ${stage} was not explicit`);
    const reopened = await store.loadSerialized('project-browser');
    assertComplete(reopened, 'r0', 'a');
    crashEvidence[stage] = { failure, reopened: reopened.revisionId };
    store.close();
  }

  const postStore = await makeStore('postcommit');
  await postStore.saveSerialized(payload('r0', 'a'));
  let postFailure = null;
  try {
    await postStore.saveSerialized(payload('r1', 'b'), { faultAt: 'committed' });
  } catch (error) {
    postFailure = { code: error.code, name: error.name };
  }
  if (postFailure?.code !== 'storage.interrupted') throw new Error('post-commit interruption was not explicit');
  const postLoaded = await postStore.loadSerialized('project-browser');
  assertComplete(postLoaded, 'r1', 'b');
  const durability = {
    requested: 'strict',
    supported: postStore.strictDurabilitySupported,
    reported: postStore.lastReportedDurability,
  };
  const storageStatus = await postStore.storageStatus({ requestPersistence: false });
  postStore.close();

  const corruptStore = await makeStore('corruption');
  await corruptStore.saveSerialized(payload('r0', 'a'));
  const activeBefore = payload('active-r0', 'a');
  const rawDb = corruptStore.db;
  const corruptTx = rawDb.transaction(['shards'], 'readwrite', { durability: 'strict' });
  const key = JSON.stringify(['project-browser', 'r0', '0:0']);
  const shardStore = corruptTx.objectStore('shards');
  const existing = await new Promise((resolve, reject) => {
    const req = shardStore.get(key);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
  existing.payload = encoder.encode('{"tampered":true}');
  shardStore.put(existing, key);
  await new Promise((resolve, reject) => {
    corruptTx.oncomplete = resolve;
    corruptTx.onabort = () => reject(corruptTx.error || new Error('corrupt transaction aborted'));
    corruptTx.onerror = () => {};
  });
  let active = activeBefore;
  let corruptFailure = null;
  try {
    const candidate = await corruptStore.loadSerialized('project-browser');
    active = candidate;
  } catch (error) {
    corruptFailure = { code: error.code, name: error.name };
  }
  if (corruptFailure?.code !== 'storage.corrupt_store') throw new Error('corrupt browser row was not rejected');
  if (active !== activeBefore) throw new Error('corrupt candidate replaced active state');
  corruptStore.close();

  const versionStore = await makeStore('version');
  await versionStore.saveSerialized(payload('r0', 'a'));
  const versionTx = versionStore.db.transaction(['metadata'], 'readwrite', { durability: 'strict' });
  versionTx.objectStore('metadata').put(999, 'store_format_version');
  await new Promise((resolve, reject) => {
    versionTx.oncomplete = resolve;
    versionTx.onabort = () => reject(versionTx.error || new Error('version transaction aborted'));
    versionTx.onerror = () => {};
  });
  let versionFailure = null;
  try {
    await versionStore.loadSerialized('project-browser');
  } catch (error) {
    versionFailure = { code: error.code, name: error.name };
  }
  if (versionFailure?.code !== 'storage.unsupported_store_version') throw new Error('incompatible store version was not typed');
  versionStore.close();

  const mapped = {
    quota: smx.mapBrowserStorageError(new DOMException('quota', 'QuotaExceededError')).code,
    permission: smx.mapBrowserStorageError(new DOMException('denied', 'SecurityError')).code,
    abort: smx.mapBrowserStorageError(new DOMException('abort', 'AbortError')).code,
  };
  if (mapped.quota !== 'storage.quota_exceeded') throw new Error('quota mapping drifted');
  if (mapped.permission !== 'storage.permission_denied') throw new Error('permission mapping drifted');
  if (mapped.abort !== 'storage.transaction_aborted') throw new Error('abort mapping drifted');

  const unavailable = new smx.IndexedDBProjectStore({ indexedDBImpl: null, storageManager: null });
  let unavailableFailure = null;
  try {
    await unavailable.open();
  } catch (error) {
    unavailableFailure = { code: error.code, name: error.name };
  }
  if (unavailableFailure?.code !== 'storage.unavailable') throw new Error('unavailable IndexedDB was not typed');

  return {
    contract: 'splashmx.smx025-browser-results/1',
    captured_at_utc: new Date().toISOString().replace(/\.\d{3}Z$/, 'Z'),
    crashEvidence,
    postCommit: { failure: postFailure, reopened: postLoaded.revisionId },
    corruption: corruptFailure,
    incompatibleStore: versionFailure,
    mappedFailures: mapped,
    unavailable: unavailableFailure,
    durability,
    storageStatus,
    protectedFields,
    userAgent: navigator.userAgent,
  };
});

result.runtime = {
  node: process.version,
  browser: browser.version(),
  os: `${os.type()} ${os.release()}`,
  arch: os.arch(),
  cpu: os.cpus()[0]?.model || 'unknown',
  memory_bytes: os.totalmem(),
  build_id: process.env.GITHUB_SHA || 'local',
};
fs.mkdirSync(path.dirname(ARTIFACT), { recursive: true });
fs.writeFileSync(ARTIFACT, `${JSON.stringify(result, null, 2)}\n`);
console.log(JSON.stringify(result, null, 2));

await context.close();
await browser.close();
await new Promise(resolve => server.close(resolve));
