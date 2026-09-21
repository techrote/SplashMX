import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import process from 'node:process';

const env = {...process.env, PYTHONPATH: process.env.PYTHONPATH || 'src'};
const server = spawn('python', ['tests/production/smx036_browser_fixture.py'], {env, stdio: ['ignore', 'pipe', 'pipe']});
let stderr = '';
server.stderr.on('data', (chunk) => { stderr += chunk.toString(); });
const baseURL = await new Promise((resolve, reject) => {
  let buffered = '';
  const timer = setTimeout(() => reject(new Error(`SMX036 server timeout: ${stderr}`)), 15000);
  server.stdout.on('data', (chunk) => {
    buffered += chunk.toString();
    const match = buffered.match(/SMX036 READY (http:\/\/[^\s]+)/);
    if (match) { clearTimeout(timer); resolve(match[1]); }
  });
  server.on('exit', (code) => { clearTimeout(timer); reject(new Error(`SMX036 server exited ${code}: ${stderr}`)); });
});

const browser = await chromium.launch({headless: true});
try {
  const page = await browser.newPage();
  await page.goto(baseURL, {waitUntil: 'domcontentloaded'});
  await page.getByRole('button', {name: 'Load'}).click();
  await page.waitForFunction(() => document.querySelector('#status').textContent.startsWith('Ready: sha256:'));
  const ready = await page.getByRole('status').textContent();
  const goodRevision = await page.locator('#active').getAttribute('data-revision');
  if (!goodRevision?.startsWith('sha256:')) throw new Error(`active CreationRevisionId missing after ${ready}`);

  await page.locator('#locator').fill('unsupported');
  await page.getByRole('button', {name: 'Load'}).click();
  await page.waitForFunction(() => document.querySelector('#status').textContent.includes('publication.unsupported_feature'));
  const afterFailure = await page.locator('#active').getAttribute('data-revision');
  if (afterFailure !== goodRevision) throw new Error('failed preparation replaced the active creation');

  const state = await (await page.request.get(`${baseURL}/api/state`)).json();
  if (state.state.active.creation_revision_id !== goodRevision) throw new Error('server active state changed after failed preparation');
  console.log(JSON.stringify({ok: true, creation_revision_id: goodRevision, failed_load_preserved_active: true}));
} finally {
  await browser.close();
  server.kill('SIGTERM');
}
