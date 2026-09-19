import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';
import { WebSocketServer, WebSocket } from 'ws';
import { validatePublished } from './model.mjs';

const root = fileURLToPath(new URL('.', import.meta.url));
const port = Number(process.env.SMX019_PORT ?? process.argv[2] ?? 8891);
const publications = new Map();
let nextConn = 1;
const rooms = new Map();
const mime = {
  '.html':'text/html; charset=utf-8', '.mjs':'text/javascript; charset=utf-8', '.js':'text/javascript; charset=utf-8',
  '.css':'text/css; charset=utf-8', '.json':'application/json; charset=utf-8'
};

function json(res, status, body) {
  const data = JSON.stringify(body);
  res.writeHead(status, { 'content-type':'application/json; charset=utf-8', 'content-length':Buffer.byteLength(data), 'cache-control':'no-store' });
  res.end(data);
}

async function bodyJson(req, max = 1024 * 1024) {
  const chunks = [];
  let size = 0;
  for await (const chunk of req) {
    size += chunk.length;
    if (size > max) throw Object.assign(new Error('Publication is too large for this research harness.'), { status:413 });
    chunks.push(chunk);
  }
  return JSON.parse(Buffer.concat(chunks).toString('utf8'));
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host ?? '127.0.0.1'}`);
  try {
    if (req.method === 'POST' && url.pathname === '/api/publish') {
      const creation = await bodyJson(req);
      validatePublished(creation, {
        supportedFeatures:['things','behaviours','connections','timeline','definitions','network'],
        grantedCapabilities:creation.capabilities?.required ?? []
      });
      const existing = publications.get(creation.creation_revision_id);
      if (existing && JSON.stringify(existing) !== JSON.stringify(creation)) return json(res, 409, { message:'That published revision already refers to different immutable data.' });
      publications.set(creation.creation_revision_id, structuredClone(creation));
      return json(res, 200, { creation_revision_id:creation.creation_revision_id });
    }
    if (req.method === 'GET' && url.pathname.startsWith('/api/creation/')) {
      const revision = decodeURIComponent(url.pathname.slice('/api/creation/'.length));
      const creation = publications.get(revision);
      if (!creation) return json(res, 404, { message:'Published revision not found.' });
      return json(res, 200, creation);
    }
    if (req.method !== 'GET' && req.method !== 'HEAD') return json(res, 405, { message:'Method not allowed.' });
    let pathname = decodeURIComponent(url.pathname);
    if (pathname === '/') pathname = '/index.html';
    const safe = normalize(pathname).replace(/^([.][.][/\\])+/, '').replace(/^[/\\]+/, '');
    const file = join(root, safe);
    if (!file.startsWith(root)) return json(res, 403, { message:'Forbidden.' });
    const data = await readFile(file);
    res.writeHead(200, { 'content-type':mime[extname(file)] ?? 'application/octet-stream', 'cache-control':'no-cache' });
    if (req.method === 'HEAD') res.end(); else res.end(data);
  } catch (error) {
    if (error?.code === 'ENOENT') return json(res, 404, { message:'Not found.' });
    json(res, error?.status ?? 400, { code:error?.code ?? 'request_failed', message:error?.message ?? 'Request failed.' });
  }
});

const wss = new WebSocketServer({ noServer:true, maxPayload:64 * 1024 });

function roomFor(name, revision) {
  const key = `${name}\u0000${revision}`;
  if (!rooms.has(key)) rooms.set(key, { key, name, revision, clients:new Set(), authority:null });
  return rooms.get(key);
}

function send(client, message) {
  if (client.ws.readyState === WebSocket.OPEN) client.ws.send(JSON.stringify(message));
}

function announceAuthority(room) {
  const principal = room.authority?.principal ?? null;
  for (const client of room.clients) send(client, { type:'authority', authority_principal:principal });
}

wss.on('connection', (ws, request, meta) => {
  const client = { ws, conn_id:`transport-${nextConn++}`, principal:meta.principal, room:meta.room };
  meta.room.clients.add(client);
  if (!meta.room.authority) meta.room.authority = client;
  send(client, { type:'welcome', conn_id:client.conn_id, authority_principal:meta.room.authority.principal, creation_revision_id:meta.room.revision });
  announceAuthority(meta.room);

  ws.on('message', raw => {
    let message;
    try { message = JSON.parse(raw.toString('utf8')); } catch { return; }
    if (message.creation_revision_id !== meta.room.revision) return;
    if (message.type === 'intent') {
      if (!meta.room.authority) return;
      send(meta.room.authority, {
        type:'intent', thing_id:String(message.thing_id ?? ''), sender_principal:client.principal,
        sender_conn_id:client.conn_id, creation_revision_id:meta.room.revision
      });
      return;
    }
    if (message.type === 'state' && meta.room.authority === client) {
      const clean = { type:'state', things:message.things, creation_revision_id:meta.room.revision };
      for (const peer of meta.room.clients) send(peer, clean);
    }
  });

  ws.on('close', () => {
    meta.room.clients.delete(client);
    if (meta.room.authority === client) meta.room.authority = [...meta.room.clients][0] ?? null;
    announceAuthority(meta.room);
    if (meta.room.clients.size === 0) rooms.delete(meta.room.key);
  });
});

server.on('upgrade', (request, socket, head) => {
  const url = new URL(request.url, `http://${request.headers.host ?? '127.0.0.1'}`);
  if (url.pathname !== '/peer') return socket.destroy();
  const revision = url.searchParams.get('rev') ?? '';
  if (!publications.has(revision)) return socket.destroy();
  const room = roomFor(url.searchParams.get('room') ?? 'smx019', revision);
  const principal = url.searchParams.get('principal') ?? 'anonymous';
  wss.handleUpgrade(request, socket, head, ws => wss.emit('connection', ws, request, { room, principal }));
});

server.listen(port, '127.0.0.1', () => {
  console.log(JSON.stringify({ event:'smx019-server-ready', port }));
});
