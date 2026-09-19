import { chromium } from 'playwright';
import http from 'node:http';
import os from 'node:os';
import fs from 'node:fs';
import path from 'node:path';

const ARTIFACT = path.resolve('artifacts/smx022-browser-results.json');
const PROTECTED_FIELDS = ['digest','source_identity','source_metadata','audio_or_media_semantics','provenance','licence_attribution','derivation_lineage'];
const median = values => { const s=[...values].sort((a,b)=>a-b); return s[Math.floor(s.length/2)]; };
const asset = rev => ({
  asset_id:'asset:000001', revision:`assetrev:000001:${rev}`, digest:`digest-${rev}`,
  source_identity:{kind:'imported',stable_source_id:'source:000001'},
  source_metadata:{name:'clip.wav',byte_length:4097,media_type:'audio/wav'},
  audio_or_media_semantics:{channels:2,sample_rate_hz:48000,loop:false},
  provenance:{origin:'fixture',capture_id:'cap:000001'},
  licence_attribution:{licence:'CC0-1.0',credit:'fixture'},
  derivation_lineage:{parents:[],operation:'source'}
});

const pageSource = `<!doctype html><meta charset="utf-8"><title>SMX-022 browser store probe</title>`;
const server = http.createServer((req,res)=>{res.writeHead(200,{'content-type':'text/html','cache-control':'no-store'});res.end(pageSource)});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const origin=`http://127.0.0.1:${server.address().port}/`;

const browser=await chromium.launch({headless:true});
const context=await browser.newContext();
let page=await context.newPage();
await page.goto(origin);

async function evalPage(fn,arg){ return page.evaluate(fn,arg); }
async function seed(){
  await evalPage(async a=>{
    const asset=a;
    await new Promise(resolve=>{const d=indexedDB.deleteDatabase('smx022');d.onsuccess=d.onerror=d.onblocked=()=>resolve();});
    const db=await new Promise((resolve,reject)=>{const r=indexedDB.open('smx022',1);r.onupgradeneeded=()=>{r.result.createObjectStore('meta');r.result.createObjectStore('records');r.result.createObjectStore('filler')};r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error)});
    const done=tx=>new Promise((resolve,reject)=>{tx.oncomplete=resolve;tx.onabort=()=>reject(tx.error||new Error('abort'));tx.onerror=()=>{}});
    const tx=db.transaction(['meta','records','filler'],'readwrite',{durability:'strict'});tx.objectStore('meta').put('r0','head');tx.objectStore('records').put(asset,'asset:000001');const f=tx.objectStore('filler');const payload='x'.repeat(1024);for(let i=0;i<4000;i++)f.put(payload,i);await done(tx);db.close();
    const root=await navigator.storage.getDirectory();try{await root.removeEntry('state.json')}catch{}const h=await root.getFileHandle('state.json',{create:true});const w=await h.createWritable();await w.write(JSON.stringify({revision:'r0',asset}));await w.close();
  },asset(0));
}
async function readIdb(){ return evalPage(async ()=>{
  const db=await new Promise((resolve,reject)=>{const r=indexedDB.open('smx022',1);r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error)});
  const req=r=>new Promise((resolve,reject)=>{r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error)});const done=tx=>new Promise((resolve,reject)=>{tx.oncomplete=resolve;tx.onabort=()=>reject(tx.error||new Error('abort'));tx.onerror=()=>{}});
  const tx=db.transaction(['meta','records'],'readonly');const head=await req(tx.objectStore('meta').get('head'));const rec=await req(tx.objectStore('records').get('asset:000001'));const durability=tx.durability;await done(tx);db.close();return {head,asset_revision:rec.revision,durability,fields:Object.keys(rec).sort()};
});}
async function abortIdb(){ await evalPage(async a=>{
  const db=await new Promise((resolve,reject)=>{const r=indexedDB.open('smx022',1);r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error)});const tx=db.transaction(['meta','records'],'readwrite',{durability:'strict'});tx.objectStore('records').put(a,'asset:000001');tx.objectStore('meta').put('r1','head');tx.abort();await new Promise(resolve=>{tx.onabort=resolve;tx.oncomplete=resolve});db.close();
},asset(1)); }
async function interruptIdb(){
  await evalPage(a=>{
    const r=indexedDB.open('smx022',1);r.onsuccess=()=>{const db=r.result;const tx=db.transaction(['meta','records','filler'],'readwrite',{durability:'strict'});tx.objectStore('records').put(a,'asset:000001');tx.objectStore('meta').put('r1','head');const f=tx.objectStore('filler');const payload='y'.repeat(8192);for(let i=4000;i<18000;i++)f.put(payload,i);window.__smx022_tx=tx;window.__smx022_db=db;};
  },asset(1));
  await page.waitForTimeout(10); await page.close(); page=await context.newPage(); await page.goto(origin);
}
async function commitIdb(){ return evalPage(async a=>{
  const db=await new Promise((resolve,reject)=>{const r=indexedDB.open('smx022',1);r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error)});const done=tx=>new Promise((resolve,reject)=>{tx.oncomplete=resolve;tx.onabort=()=>reject(tx.error||new Error('abort'));tx.onerror=()=>{}});const tx=db.transaction(['meta','records'],'readwrite',{durability:'strict'});tx.objectStore('records').put(a,'asset:000001');tx.objectStore('meta').put('r1','head');const durability=tx.durability;await done(tx);db.close();return durability;
},asset(1));}
async function readOpfs(){ return evalPage(async ()=>{const root=await navigator.storage.getDirectory();const h=await root.getFileHandle('state.json');return JSON.parse(await (await h.getFile()).text())}); }
async function interruptOpfs(){
  await evalPage(async a=>{const root=await navigator.storage.getDirectory();const h=await root.getFileHandle('state.json');const w=await h.createWritable();await w.write(JSON.stringify({revision:'r1',asset:a,padding:'z'.repeat(4*1024*1024)}));window.__smx022_writer=w;return true},asset(1));
  await page.close(); page=await context.newPage(); await page.goto(origin);
}
async function commitOpfs(){ await evalPage(async a=>{const root=await navigator.storage.getDirectory();const h=await root.getFileHandle('state.json');const w=await h.createWritable();await w.write(JSON.stringify({revision:'r1',asset:a}));await w.close()},asset(1)); }
async function bench(){ return evalPage(async ()=>{
  const open=()=>new Promise((resolve,reject)=>{const r=indexedDB.open('smx022',1);r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error)});const req=r=>new Promise((resolve,reject)=>{r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error)});const done=tx=>new Promise((resolve,reject)=>{tx.oncomplete=resolve;tx.onabort=()=>reject(tx.error||new Error('abort'));tx.onerror=()=>{}});const db=await open();let gets=[],alls=[],commits=[];for(let i=0;i<15;i++){let t=performance.now();let tx=db.transaction('filler','readonly');await req(tx.objectStore('filler').get(2000));await done(tx);gets.push(performance.now()-t);t=performance.now();tx=db.transaction('filler','readonly');await req(tx.objectStore('filler').getAll());await done(tx);alls.push(performance.now()-t);t=performance.now();tx=db.transaction('meta','readwrite',{durability:'strict'});tx.objectStore('meta').put(`bench-${i}`,'bench');await done(tx);commits.push(performance.now()-t)}db.close();const root=await navigator.storage.getDirectory();const h=await root.getFileHandle('bench.bin',{create:true});const bytes=new Uint8Array(64*1024);let writes=[],reads=[];for(let i=0;i<15;i++){let t=performance.now();const w=await h.createWritable();await w.write(bytes);await w.close();writes.push(performance.now()-t);t=performance.now();await (await h.getFile()).arrayBuffer();reads.push(performance.now()-t)}let persist_request;try{persist_request=await navigator.storage.persist()}catch(e){persist_request=`${e.name}:${e.message}`}return {idb:{gets,alls,commits},opfs:{writes,reads},storage:{persisted:await navigator.storage.persisted(),persist_request,estimate:await navigator.storage.estimate(),user_agent:navigator.userAgent}};
}); }

await seed();const initialIdb=await readIdb();const initialOpfs=await readOpfs();await abortIdb();const afterAbort=await readIdb();await seed();await interruptIdb();const afterIdbInterrupt=await readIdb();await seed();await interruptOpfs();const afterOpfsInterrupt=await readOpfs();const idbDurability=await commitIdb();await commitOpfs();const committedIdb=await readIdb();const committedOpfs=await readOpfs();const perf=await bench();

const complete = fields => PROTECTED_FIELDS.every(k=>fields.includes(k));
if(afterAbort.head!=='r0'||!afterAbort.asset_revision.endsWith(':0'))throw new Error('IDB abort leaked a partial revision');
if(!([['r0','0'],['r1','1']].some(([h,r])=>afterIdbInterrupt.head===h&&afterIdbInterrupt.asset_revision.endsWith(`:${r}`))))throw new Error('IDB interruption field-mixed revisions');
if(afterOpfsInterrupt.revision!=='r0'||!afterOpfsInterrupt.asset.revision.endsWith(':0'))throw new Error('OPFS unclosed write became visible');
if(committedIdb.head!=='r1'||!committedIdb.asset_revision.endsWith(':1'))throw new Error('IDB commit missing');
if(committedOpfs.revision!=='r1'||!committedOpfs.asset.revision.endsWith(':1'))throw new Error('OPFS commit missing');
if(!complete(Object.keys(committedOpfs.asset)))throw new Error('protected media bundle incomplete');

const browserVersion=browser.version();const result={
  contract:'splashmx.smx022-browser-results/1',captured_at_utc:new Date().toISOString().replace(/\.\d{3}Z$/,'Z'),
  runtime:{name:'Node.js',version:process.version,build_id:process.env.GITHUB_SHA||'local'},browser:{name:'Chromium',version:browserVersion},
  environment:{os:`${os.type()} ${os.release()}`,arch:os.arch(),hardware:{cpu:os.cpus()[0]?.model||'unknown',gpu:'headless Chromium software/CI rendering',memory_bytes:os.totalmem()}},
  initial:{indexeddb:initialIdb,opfs:initialOpfs},
  indexeddb:{reported_durability:idbDurability,after_abort:afterAbort,after_page_interruption:afterIdbInterrupt,committed:committedIdb,single_get_ms_median:median(perf.idb.gets),get_all_4000_ms_median:median(perf.idb.alls),strict_commit_ms_median:median(perf.idb.commits)},
  opfs:{after_page_interruption:afterOpfsInterrupt,committed:committedOpfs,write_close_64k_ms_median:median(perf.opfs.writes),read_64k_ms_median:median(perf.opfs.reads)},storage:perf.storage
};
fs.mkdirSync(path.dirname(ARTIFACT),{recursive:true});fs.writeFileSync(ARTIFACT,JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result,null,2));
await context.close();await browser.close();server.close();
