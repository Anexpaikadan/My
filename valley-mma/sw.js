// Service worker: makes the app installable and shows an offline page.
// Pages are never cached (they hold member data); only static files are.
const CACHE = 'vmma-v5';
const ASSETS = ['offline.html', 'assets/style.css?v=4', 'assets/app.js?v=5', 'assets/vendor/bootstrap.min.css',
  'assets/vendor/bootstrap.bundle.min.js', 'assets/vendor/bootstrap-icons.min.css', 'assets/icons/icon-192.png', 'assets/avatar.svg'];

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
    e.respondWith(caches.open(CACHE).then((c) => c.match(req).then((hit) => hit || fetch(req).then((res) => {
      if (res.ok) c.put(req, res.clone());
      return res;
    }))));
  }
});
