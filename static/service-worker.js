const CACHE_NAME = 'cadrex-pwa-cache-v1';
const urlsToCache = [
  '/',
  '/static/css/dashboard.css',
  '/static/logo_cadrex.png'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => response || fetch(event.request))
  );
});
