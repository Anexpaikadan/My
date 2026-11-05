// v8 — service worker (must stay in the main folder so it covers every page)
self.addEventListener('install',()=>self.skipWaiting());
self.addEventListener('activate',e=>e.waitUntil(self.clients.claim()));
// network only: money data is never cached
self.addEventListener('fetch',e=>e.respondWith(fetch(e.request)));
