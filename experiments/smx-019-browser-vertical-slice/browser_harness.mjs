import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import { mkdir, stat, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('.', import.meta.url));
const port = Number(process.env.SMX019_PORT ?? 8891);
const origin = `http://127.0.0.1:${port}`;
const resultPath = resolve(process.env.SMX019_RESULTS ?? 'artifacts/smx019-browser-results.json');
const now = () => performance.now();

function waitServer(child) {
  return new Promise((resolveReady, reject) => {
    let buffer = '';
    const timer = setTimeout(() => reject(new Error('SMX-019 server did not become ready')), 15000);
    child.stdout.on('data', chunk => {
      buffer += chunk.toString();
      for (const line of buffer.split('\n')) {
        if (line.includes('smx019-server-ready')) {
          clearTimeout(timer);
          resolveReady();
          return;
        }
      }
    });
    child.stderr.on('data', chunk => process.stderr.write(chunk));
    child.on('exit', code => {
      if (code !== 0) reject(new Error(`SMX-019 server exited early (${code})`));
    });
  });
}

async function waitPlayer(page) {
  await page.waitForFunction(() => Boolean(window.__SMX019_PLAYER__ || window.__SMX019_PLAYER_ERROR__), null, { timeout:15000 });
  const error = await page.evaluate(() => window.__SMX019_PLAYER_ERROR__ ?? null);
  if (error) throw new Error(`Player failed: ${error.code}: ${error.message}`);
}

async function waitLamp(page, toggled) {
  await page.waitForFunction(expected => {
    const state = window.__SMX019_PLAYER__?.getState();
    return state?.things?.find(t => t.thing_id === 'lamp')?.state?.toggled === expected;
  }, toggled, { timeout:5000 });
}

async function fileBytes(names) {
  const output = {};
  for (const name of names) output[name] = (await stat(resolve(root, name))).size;
  return output;
}

const server = spawn(process.execPath, [resolve(root, 'server.mjs'), String(port)], {
  cwd:root, stdio:['ignore','pipe','pipe'], env:{...process.env, SMX019_PORT:String(port)}
});
let browser;
try {
  await waitServer(server);
  browser = await chromium.launch({ headless:true });
  const context = await browser.newContext();
  const page = await context.newPage();
  const campaignStart = now();
  const editorStart = now();
  await page.goto(origin, { waitUntil:'networkidle' });
  const editorLoadMs = now() - editorStart;
  await page.evaluate(() => navigator.serviceWorker?.ready);
  await page.reload({ waitUntil:'networkidle' });

  const forbiddenVisible = ['godot','scenetree','nodepath','resourceuid','rpc','package manager','export preset','build toolchain'];
  const visibleText = (await page.locator('body').innerText()).toLowerCase();
  for (const term of forbiddenVisible) {
    if (visibleText.includes(term)) throw new Error(`Author surface leaked substrate/build vocabulary: ${term}`);
  }

  const click = async action => page.locator(`[data-action="${action}"]`).click();
  const disclose = async label => {
    const summary = page.locator('summary').filter({ hasText: label }).first();
    if (!(await summary.isVisible())) throw new Error(`Progressive-disclosure surface is not reachable: ${label}`);
    const details = summary.locator('..');
    if (!(await details.evaluate(node => node.open))) await summary.click();
  };

  await click('add-button');
  await click('add-lamp');
  await click('add-media');
  await click('group');
  const beforeReuse = await page.evaluate(() => window.__SMX019__.getProject().things.map(t => t.thing_id).sort());
  await click('reuse');
  const afterReuse = await page.evaluate(() => window.__SMX019__.getProject().things.map(t => t.thing_id).sort());
  if (JSON.stringify(beforeReuse) !== JSON.stringify(afterReuse)) throw new Error('Make reusable replaced first-instance Thing identities');
  await click('rule');
  await click('connect');
  await click('timeline');
  await disclose('Together');
  await page.selectOption('#together-preset', 'shared');
  await disclose('People');
  await click('presence');
  await click('conflict');

  await click('play');
  await page.locator('#preview button[data-thing-id="button"]').click();
  const previewState = await page.evaluate(() => ({ project:window.__SMX019__.getProject(), runtime:window.__SMX019__.getRuntime() }));
  const authoredLamp = previewState.project.things.find(t => t.thing_id === 'lamp');
  const runtimeLamp = previewState.runtime.things.find(t => t.thing_id === 'lamp');
  if (authoredLamp.state.toggled !== false || runtimeLamp.state.toggled !== true) throw new Error('Play state leaked into authored state or runtime interaction failed');
  await click('stop');

  await click('save');
  const savedBeforeReload = await page.evaluate(() => window.__SMX019__.getProject());
  await page.reload({ waitUntil:'networkidle' });
  const reloaded = await page.evaluate(() => window.__SMX019__.getProject());
  if (reloaded.authoring.presence.length !== 0 || reloaded.authoring.play_session !== null) throw new Error('Transient People/play context persisted across save/reload');
  if (reloaded.collaboration.conflicts.length !== 1) throw new Error('Durable collaboration conflict did not survive editable reload');
  if (reloaded.things.length !== savedBeforeReload.things.length) throw new Error('Editable project changed across save/reload');

  const publishStart = now();
  await click('publish');
  await page.waitForFunction(() => Boolean(window.__SMX019__.getPublished()), null, { timeout:10000 });
  await page.waitForFunction(() => document.querySelector('#player-frame')?.contentWindow != null);
  const publishMs = now() - publishStart;
  const publication = await page.evaluate(() => window.__SMX019__.getPublished());
  const authored = await page.evaluate(() => window.__SMX019__.getProject());
  if (JSON.stringify(publication.assets[0]) !== JSON.stringify(authored.assets[0])) throw new Error('Protected media revision changed during publication');
  if ('authoring' in publication || 'collaboration' in publication) throw new Error('Published creation contains editor/runtime transient planes');

  const playerPage = await context.newPage();
  const playerStart = now();
  await playerPage.goto(`${origin}/player.html?rev=${encodeURIComponent(publication.creation_revision_id)}`, { waitUntil:'networkidle' });
  await waitPlayer(playerPage);
  const playerLoadMs = now() - playerStart;
  const loadedRevision = await playerPage.evaluate(() => window.__SMX019_PLAYER__.getCreation().creation_revision_id);
  if (loadedRevision !== publication.creation_revision_id) throw new Error('Generic player substituted a different published revision');
  await playerPage.locator('button[data-thing-id="button"]').click();
  await waitLamp(playerPage, true);

  const offlineStart = now();
  await context.setOffline(true);
  await playerPage.reload({ waitUntil:'domcontentloaded' });
  await waitPlayer(playerPage);
  const offlineReloadMs = now() - offlineStart;
  const offlineRevision = await playerPage.evaluate(() => window.__SMX019_PLAYER__.getCreation().creation_revision_id);
  if (offlineRevision !== publication.creation_revision_id) throw new Error('Offline cache substituted a different published revision');
  await context.setOffline(false);

  const deniedPage = await context.newPage();
  await deniedPage.goto(`${origin}/player.html?rev=${encodeURIComponent(publication.creation_revision_id)}&deny=camera`, { waitUntil:'networkidle' });
  await deniedPage.waitForFunction(() => Boolean(window.__SMX019_PLAYER_ERROR__));
  const deniedCode = await deniedPage.evaluate(() => window.__SMX019_PLAYER_ERROR__.code);
  if (deniedCode !== 'required_capability_denied') throw new Error(`Required capability denial surfaced as ${deniedCode}`);

  const incompatiblePage = await context.newPage();
  await incompatiblePage.goto(`${origin}/player.html?rev=${encodeURIComponent(publication.creation_revision_id)}&unsupported_feature=1`, { waitUntil:'networkidle' });
  await incompatiblePage.waitForFunction(() => Boolean(window.__SMX019_PLAYER_ERROR__));
  const incompatibleCode = await incompatiblePage.evaluate(() => window.__SMX019_PLAYER_ERROR__.code);
  if (incompatibleCode !== 'required_feature_unsupported') throw new Error(`Required feature incompatibility surfaced as ${incompatibleCode}`);

  await page.goto(`${origin}/?deny_storage=1`, { waitUntil:'networkidle' });
  await click('add-button');
  await click('save');
  const storageStatus = await page.locator('#status').innerText();
  if (!storageStatus.toLowerCase().includes('save failed')) throw new Error('Storage denial did not produce an author-facing save failure');

  const peerA = await context.newPage();
  const peerB = await context.newPage();
  const peerStart = now();
  await Promise.all([
    peerA.goto(`${origin}/player.html?rev=${encodeURIComponent(publication.creation_revision_id)}&topology=peer&principal=alice`, { waitUntil:'networkidle' }),
    peerB.goto(`${origin}/player.html?rev=${encodeURIComponent(publication.creation_revision_id)}&topology=peer&principal=bob`, { waitUntil:'networkidle' }),
  ]);
  await Promise.all([waitPlayer(peerA), waitPlayer(peerB)]);
  await peerB.locator('button[data-thing-id="button"]').click();
  await Promise.all([waitLamp(peerA, true), waitLamp(peerB, true)]);
  const peerConvergenceMs = now() - peerStart;
  const peerStates = await Promise.all([
    peerA.evaluate(() => window.__SMX019_PLAYER__.getState()),
    peerB.evaluate(() => window.__SMX019_PLAYER__.getState()),
  ]);
  if (JSON.stringify(peerStates[0]) !== JSON.stringify(peerStates[1])) throw new Error('Peer pages diverged');
  for (const state of peerStates) {
    const serialized = JSON.stringify(state);
    if (serialized.includes('transport_peer_id') || serialized.includes('connection_handle')) throw new Error('Transient transport identity leaked into semantic runtime state');
  }

  const file_sizes = await fileBytes(['index.html','editor.mjs','model.mjs','player.html','player.mjs','server.mjs','styles.css','sw.js']);
  const finalProject = await page.evaluate(() => window.__SMX019__.getProject());
  const result = {
    node:process.version,
    browser:await browser.version(),
    timings_ms:{
      editor_load:Number(editorLoadMs.toFixed(3)),
      publish:Number(publishMs.toFixed(3)),
      player_load:Number(playerLoadMs.toFixed(3)),
      offline_reload:Number(offlineReloadMs.toFixed(3)),
      peer_convergence:Number(peerConvergenceMs.toFixed(3)),
      campaign_total:Number((now() - campaignStart).toFixed(3)),
    },
    author_gesture_count:17,
    author_vocabulary:['Thing','Behaviour','Connection','Stage','Timeline','Rules','Components','Together','People','Publish','Inspect'],
    storage:{editable:'localStorage disposable harness adapter', publication:'CacheStorage/service worker exact-revision cache', denied_status:storageStatus},
    protected_asset:{asset_id:publication.assets[0].asset_id, digest:publication.assets[0].digest},
    file_bytes:file_sizes,
    semantic:{creation_revision_id:publication.creation_revision_id, thing_count:publication.things.length, definition_count:publication.definitions.length, connection_count:publication.connections.length, timeline_count:publication.timeline.length},
    final_editable_thing_count:finalProject.things.length,
  };
  await mkdir(dirname(resultPath), { recursive:true });
  await writeFile(resultPath, JSON.stringify(result, null, 2) + '\n');
  console.log(JSON.stringify(result, null, 2));
} finally {
  if (browser) await browser.close();
  server.kill('SIGTERM');
}
