// Service worker: makes the app installable and shows an offline page.
// Pages and customer files are never cached (they are private); only static assets are.
const CACHE = 'daybill-v9';
const ASSETS = ['offline.html', 'assets/logo.png', 'assets/style.css', 'assets/app.js', 'assets/qrcode.js',
  'assets/icons/icon-192.png', 'assets/icons/icon-512.png', 'assets/icons/favicon.png'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys()
    .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== location.origin) return;
  if (req.mode === 'navigate') {
    e.respondWith(fetch(req).catch(() => caches.match('offline.html')));
    return;
  }
  if (new URL(req.url).pathname.includes('/assets/')) {
    // Static files: from the cache when this exact version (?v=…) is stored, otherwise from the network.
    // An older version is used only when offline, so an update never shows the old design.
    e.respondWith(caches.open(CACHE).then((c) => c.match(req).then((hit) => hit || fetch(req).then((res) => {
      if (res.ok) c.put(req, res.clone());
      return res;
    }).catch(() => c.match(req, { ignoreSearch: true })))));
  }
});
