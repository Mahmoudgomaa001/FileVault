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
  '/static/vendor/fontawesome/webfonts/fa-brands-400.woff2',
  '/static/vendor/fontawesome/webfonts/fa-regular-400.woff2',
  '/static/vendor/fontawesome/webfonts/fa-solid-900.woff2',
  '/static/vendor/fontawesome/webfonts/fa-brands-400.ttf',
  '/static/vendor/fontawesome/webfonts/fa-regular-400.ttf',
  '/static/vendor/fontawesome/webfonts/fa-solid-900.ttf',
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
  // We only want to handle navigation requests for the offline fallback.
  if (event.request.mode === 'navigate') {
    event.respondWith(
      (async () => {
        try {
          // Try the network first.
          const networkResponse = await fetch(event.request);
          // If successful, cache the response for future offline use.
          const cache = await caches.open(CACHE_NAME);
          cache.put(event.request, networkResponse.clone());
          return networkResponse;
        } catch (error) {
          // The network failed.
          console.log('[ServiceWorker] Fetch failed; returning offline page or cached page.', error);

          const cache = await caches.open(CACHE_NAME);
          // Try to serve the page from the cache.
          const cachedResponse = await cache.match(event.request);
          if (cachedResponse) {
            return cachedResponse;
          }
          // If the page is not in the cache, serve the master offline page.
          return await cache.match(OFFLINE_URL);
        }
      })()
    );
  } else {
    // For all other requests (CSS, JS, images, etc.), use a "cache first, then network" strategy.
    // This ensures that any new static assets are cached as they are requested.
    event.respondWith(
      caches.open(CACHE_NAME).then(async (cache) => {
        const cachedResponse = await cache.match(event.request);
        if (cachedResponse) {
          return cachedResponse;
        }

        // Not in cache, go to network.
        try {
            const networkResponse = await fetch(event.request);
            // Cache the new response for future offline use.
            cache.put(event.request, networkResponse.clone());
            return networkResponse;
        } catch (error) {
            console.log('[ServiceWorker] Fetch failed for non-navigation request.', event.request.url, error);
            // When offline, this will fail, but that's expected for assets not in the cache.
            // We don't have a generic fallback for random assets, so we just let the request fail.
            // It will be caught as a failed network request in the browser.
        }
      })
    );
  }
});
