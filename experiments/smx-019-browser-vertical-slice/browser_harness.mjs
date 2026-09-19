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
  await page.selectOption('#together-preset', 'shared');
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

  // Exact offline reload: the player shell and exact immutable publication were cached while online.
  await context.setOffline(true);
  const offlineStart = now();
  await playerPage.reload({ waitUntil:'domcontentloaded' });
  await waitPlayer(playerPage);
  const offlineReloadMs = now() - offlineStart;
  const offlineRevision = await playerPage.evaluate(() => window.__SMX019_PLAYER__.getCreation().creation_revision_id);
  if (offlineRevision !== publication.creation_revision_id) throw new Error('Offline player substituted a different published revision');
  await context.setOffline(false);

  // A required feature must fail before activation with author-facing wording.
  const incompat = await context.newPage();
  await incompat.goto(`${origin}/player.html?rev=${encodeURIComponent(publication.creation_revision_id)}&unsupported_feature=1`, { waitUntil:'networkidle' });
  await incompat.waitForFunction(() => Boolean(window.__SMX019_PLAYER_ERROR__), null, { timeout:10000 });
  const incompatError = await incompat.evaluate(() => window.__SMX019_PLAYER_ERROR__);
  if (incompatError.code !== 'required_feature_unsupported') throw new Error(`Expected required_feature_unsupported, got ${incompatError.code}`);

  // Required capability denial must fail before activation; publication itself does not mint authority.
  const requiredCapRevision = await page.evaluate(async () => {
    const model = await import('./model.mjs');
    const creation = model.publish(window.__SMX019__.getProject(), { requiredCapabilities:['camera'] });
    const response = await fetch('/api/publish', { method:'POST', headers:{'content-type':'application/json'}, body:JSON.stringify(creation) });
    if (!response.ok) throw new Error(await response.text());
    return creation.creation_revision_id;
  });
  const denied = await context.newPage();
  await denied.goto(`${origin}/player.html?rev=${encodeURIComponent(requiredCapRevision)}&deny=camera`, { waitUntil:'networkidle' });
  await denied.waitForFunction(() => Boolean(window.__SMX019_PLAYER_ERROR__), null, { timeout:10000 });
  const deniedError = await denied.evaluate(() => window.__SMX019_PLAYER_ERROR__);
  if (deniedError.code !== 'required_capability_denied') throw new Error(`Expected required_capability_denied, got ${deniedError.code}`);

  // Storage denial stays an author-language failure and does not mutate canonical meaning.
  const noStore = await context.newPage();
  await noStore.goto(`${origin}/?deny_storage=1`, { waitUntil:'networkidle' });
  await noStore.locator('[data-action="save"]').click();
  const storageMessage = await noStore.locator('#status').innerText();
  if (!storageMessage.includes('cannot save this project')) throw new Error(`Unexpected storage failure copy: ${storageMessage}`);

  // Bounded peer-hosted integration uses the same immutable revision on both pages.
  const alice = await context.newPage();
  const bob = await context.newPage();
  await alice.goto(`${origin}/player.html?rev=${encodeURIComponent(publication.creation_revision_id)}&topology=peer&principal=alice&room=browser-slice`, { waitUntil:'networkidle' });
  await waitPlayer(alice);
  await alice.waitForFunction(() => window.__SMX019_PLAYER__.getContext().transportConnectionId?.startsWith('transport-'));
  await bob.goto(`${origin}/player.html?rev=${encodeURIComponent(publication.creation_revision_id)}&topology=peer&principal=bob&room=browser-slice`, { waitUntil:'networkidle' });
  await waitPlayer(bob);
  await bob.waitForFunction(() => window.__SMX019_PLAYER__.getContext().transportConnectionId?.startsWith('transport-'));
  const peerContexts = await Promise.all([
    alice.evaluate(() => window.__SMX019_PLAYER__.getContext()),
    bob.evaluate(() => window.__SMX019_PLAYER__.getContext())
  ]);
  if (peerContexts[0].transportConnectionId === peerContexts[1].transportConnectionId) throw new Error('Transient transport connection identity collided');
  if (peerContexts[0].authorityPrincipal !== 'alice' || peerContexts[1].authorityPrincipal !== 'alice') throw new Error('Peer authority projection is inconsistent');
  const peerStart = now();
  await bob.locator('button[data-thing-id="button"]').click();
  await Promise.all([waitLamp(alice, true), waitLamp(bob, true)]);
  const peerConvergenceMs = now() - peerStart;
  const peerRevisions = await Promise.all([
    alice.evaluate(() => window.__SMX019_PLAYER__.getCreation().creation_revision_id),
    bob.evaluate(() => window.__SMX019_PLAYER__.getCreation().creation_revision_id)
  ]);
  if (peerRevisions.some(rev => rev !== publication.creation_revision_id)) throw new Error('Peer runtime substituted published content identity');

  const storage = await page.evaluate(async () => {
    const estimate = navigator.storage?.estimate ? await navigator.storage.estimate() : {};
    return {
      local_storage:true,
      cache_storage:'caches' in window,
      service_worker:'serviceWorker' in navigator,
      storage_usage_bytes:estimate.usage ?? null,
      storage_quota_bytes:estimate.quota ?? null
    };
  });
  const packageBytes = await fileBytes(['index.html','editor.mjs','player.html','player.mjs','model.mjs','styles.css','sw.js']);
  const metrics = {
    campaign:'SMX-019',
    environment:{ browser:'chromium-playwright', node:process.version, platform:process.platform, arch:process.arch },
    result:'pass',
    creation_revision_id:publication.creation_revision_id,
    editor_load_ms:Number(editorLoadMs.toFixed(2)),
    publish_ms:Number(publishMs.toFixed(2)),
    player_load_ms:Number(playerLoadMs.toFixed(2)),
    offline_reload_ms:Number(offlineReloadMs.toFixed(2)),
    peer_convergence_ms:Number(peerConvergenceMs.toFixed(2)),
    total_campaign_ms:Number((now()-campaignStart).toFixed(2)),
    author_gesture_count:await page.evaluate(() => window.__SMX019__.getGestures()),
    author_vocabulary:['Thing','Behaviour','Connection','Stage','Timeline','Rules','Components','Together','People','Publish','Inspect'],
    protected_asset_id:publication.assets[0].asset_id,
    protected_asset_digest:publication.assets[0].revision.digest,
    storage,
    package_bytes:packageBytes,
    limits:[
      'Automated interaction evidence is not a novice human-usability or accessibility study.',
      'Disposable JavaScript host/player proves browser projection; SMX-017 separately supplies real Godot 4.7.2 browser/headless substrate evidence.',
      'Peer path is a bounded projection check; destructive reconnect/host-loss/topology evidence remains SMX-017.'
    ]
  };
  await mkdir(dirname(resultPath), { recursive:true });
  await writeFile(resultPath, `${JSON.stringify(metrics, null, 2)}\n`);
  console.log(JSON.stringify(metrics, null, 2));
} finally {
  if (browser) await browser.close();
  server.kill('SIGTERM');
}
