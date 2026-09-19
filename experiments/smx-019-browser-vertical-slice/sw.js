const SHELL = 'smx019-shell-v1';
const SHELL_FILES = ['/', '/index.html', '/player.html', '/styles.css', '/editor.mjs', '/player.mjs', '/model.mjs'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(SHELL).then(cache => cache.addAll(SHELL_FILES)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api/creation/')) {
    event.respondWith(fetch(event.request).then(response => {
      const copy = response.clone();
      caches.open('smx019-creations-v1').then(cache => cache.put(event.request, copy));
      return response;
    }).catch(async () => (await caches.open('smx019-creations-v1')).match(event.request)));
    return;
  }
  const shellKey = SHELL_FILES.includes(url.pathname) ? url.pathname : event.request;
  event.respondWith(caches.match(shellKey).then(cached => cached ?? fetch(event.request)));
});
