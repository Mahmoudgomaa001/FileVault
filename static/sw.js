const CACHE_NAME = 'filevault-cache-v6';
const OFFLINE_URL = 'static/offline.html';
const APP_SHELL_URLS = [
  // The root '/' is intentionally omitted. It's cached on first visit via the 'navigate' fetch handler.
  // Precaching it can fail if the user is not logged in, as it would redirect.
  '/static/fonts.css',
  '/static/vendor/fontawesome/css/all.min.css',
  '/static/vendor/fontawesome/css/fa-shims.css',
  '/static/socket.io.min.js',
  '/static/site.webmanifest',
  '/static/favicon.svg',
  OFFLINE_URL
];

self.addEventListener('install', event => {
  console.log('[ServiceWorker] Install event fired');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('[ServiceWorker] Caching app shell and offline page');
        return cache.addAll(APP_SHELL_URLS);
      })
      .then(() => {
        // Force the waiting service worker to become the active service worker.
        return self.skipWaiting();
      })
  );
});

self.addEventListener('activate', event => {
  console.log('[ServiceWorker] Activate event fired');
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          // Delete old caches
          if (cacheName !== CACHE_NAME) {
            console.log('[ServiceWorker] Clearing old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => {
      // Tell the active service worker to take control of the page immediately.
      return self.clients.claim();
    })
  );
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // For API and Socket.IO requests, always go to the network and do not cache.
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/socket.io/')) {
    event.respondWith(fetch(event.request));
    return;
  }

  // For navigation requests, use a network-first strategy.
  if (event.request.mode === 'navigate') {
    event.respondWith(
      (async () => {
        try {
          const networkResponse = await fetch(event.request);
          const cache = await caches.open(CACHE_NAME);
          cache.put(event.request, networkResponse.clone());
          return networkResponse;
        } catch (error) {
          console.log('[ServiceWorker] Navigate fetch failed, trying cache.', error);
          const cache = await caches.open(CACHE_NAME);
          const cachedResponse = await cache.match(event.request);
          return cachedResponse || await cache.match(OFFLINE_URL);
        }
      })()
    );
    return;
  }

  // For all other requests (static assets), use a cache-first strategy.
  event.respondWith(
    caches.open(CACHE_NAME).then(cache => {
      return cache.match(event.request).then(cachedResponse => {
        if (cachedResponse) {
          return cachedResponse;
        }

        return fetch(event.request).then(networkResponse => {
          // Clone the response because it's a stream and can only be consumed once.
          const responseToCache = networkResponse.clone();
          cache.put(event.request, responseToCache);
          return networkResponse;
        }).catch(error => {
          console.error('[ServiceWorker] Asset fetch failed:', error);
          // For static assets, we don't return an offline page, just let the request fail.
          throw error;
        });
      });
    })
  );
});
