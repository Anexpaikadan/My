// Aishwarya Club PWA Service Worker v2
const CACHE = 'aasc-v3';

self.addEventListener('install', function(e) {
  self.skipWaiting();
});

self.addEventListener('activate', function(e) {
  e.waitUntil(self.clients.claim());
});

// Cache assets
self.addEventListener('fetch', function(e) {
  if (e.request.method !== 'GET') return;
  if (e.request.url.includes('/assets/')) {
    e.respondWith(
      caches.match(e.request).then(function(cached) {
        return cached || fetch(e.request).then(function(resp) {
          var clone = resp.clone();
          caches.open(CACHE).then(function(c) { c.put(e.request, clone); });
          return resp;
        });
      })
    );
  }
});

// Push notification handler
self.addEventListener('push', function(e) {
  var data = {};
  try { data = e.data.json(); } catch(err) { data = {title:'Aishwarya Club', body: e.data ? e.data.text() : 'New update!'}; }

  var title   = data.title || 'Aishwarya Arts & Sports Club';
  var options = {
    body:    data.body    || 'You have a new notification',
    icon:    data.icon    || '/assets/icons/app/icon-192.png',
    badge:   data.badge   || '/assets/icons/app/icon-192.png',
    image:   data.image   || undefined,
    data:    { url: data.url || '/' },
    vibrate: [200, 100, 200],
    requireInteraction: false,
    actions: data.actions || []
  };

  e.waitUntil(self.registration.showNotification(title, options));
});

// Notification click — open the URL
self.addEventListener('notificationclick', function(e) {
  e.notification.close();
  var url = (e.notification.data && e.notification.data.url) ? e.notification.data.url : '/';
  e.waitUntil(
    clients.matchAll({type:'window', includeUncontrolled:true}).then(function(cls) {
      for (var i = 0; i < cls.length; i++) {
        if (cls[i].url.includes(self.location.origin) && 'focus' in cls[i]) {
          cls[i].navigate(url);
          return cls[i].focus();
        }
      }
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});
