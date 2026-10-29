self.addEventListener('install',()=>self.skipWaiting());
self.addEventListener('activate',e=>e.waitUntil(self.clients.claim()));
// network only: money data is never cached
self.addEventListener('fetch',e=>e.respondWith(fetch(e.request)));
