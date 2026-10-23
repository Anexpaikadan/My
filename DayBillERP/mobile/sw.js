// DayBill Mobile — keeps the app itself on the phone so it opens with no
// signal (van). Data always comes fresh from DayBill / the relay.
const CACHE = "daybill-mobile-v750";
const FILES = ["./", "index.html", "van.html", "app.css", "app.js", "config.js", "vendor/qrcode.js",
               "manifest.webmanifest", "icon-192.png", "icon-512.png"];
self.addEventListener("install", e => {
  // one file that does not load (e.g. an old saved redirect of the site) must not stop the others
  e.waitUntil(caches.open(CACHE)
    .then(c => Promise.all(FILES.map(f => c.add(new Request(f, { cache: "reload" })).catch(() => null))))
    .then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET" || u.pathname.includes("/api") || u.pathname.endsWith(".php")) return;
  e.respondWith(fetch(e.request).then(r => {
    const copy = r.clone(); caches.open(CACHE).then(c => c.put(e.request, copy)); return r;
  }).catch(() => caches.match(e.request).then(r => r || caches.match("index.html"))));
});
