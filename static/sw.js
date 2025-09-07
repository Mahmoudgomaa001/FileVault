const VERSION = 'v13';
const CACHE_NAME = `filevault-cache-${VERSION}`;

// The app shell includes all the minimal resources required to render the initial UI.
const APP_SHELL_URLS = [
  '/',
  '/static/index.html', // Explicitly cache the app shell
  '/static/app.js',     // Cache the main JS file
  '/static/adhkar.json',
  '/static/favicon.svg',
  '/static/fonts.css',
  '/static/site.webmanifest',
  '/static/socket.io.min.js',
  '/static/vendor/fontawesome/css/all.min.css',
  '/static/vendor/fontawesome/css/fa-shims.css',
  '/static/vendor/fontawesome/webfonts/fa-brands-400.ttf',
  '/static/vendor/fontawesome/webfonts/fa-brands-400.woff2',
  '/static/vendor/fontawesome/webfonts/fa-regular-400.ttf',
  '/static/vendor/fontawesome/webfonts/fa-regular-400.woff2',
  '/static/vendor/fontawesome/webfonts/fa-solid-900.ttf',
  '/static/vendor/fontawesome/webfonts/fa-solid-900.woff2'
];

// Pre-cache the app shell on install.
self.addEventListener('install', event => {
  console.log('[ServiceWorker] Install event fired');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('[ServiceWorker] Caching app shell');
        return cache.addAll(APP_SHELL_URLS).catch(error => {
          console.error('[ServiceWorker] Failed to cache app shell:', error);
        });
      })
      .then(() => self.skipWaiting()) // Activate new service worker immediately
  );
});

// Clean up old caches on activation.
self.addEventListener('activate', event => {
  console.log('[ServiceWorker] Activate event fired');
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            console.log('[ServiceWorker] Clearing old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => self.clients.claim()) // Take control of all clients
  );
});

// Handle fetch events.
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // Ignore non-HTTP/HTTPS requests
  if (!url.protocol.startsWith('http')) {
    return;
  }

  // Ignore requests to other origins, except for Socket.IO which might be on a different path
  if (event.request.url.includes('/socket.io/')) {
    return;
  }

  // API requests: Network-first, then cache for GET requests.
  if (url.pathname.startsWith('/api/')) {
    if (event.request.method === 'GET') {
      event.respondWith(
        caches.open(CACHE_NAME).then(async (cache) => {
          try {
            const networkResponse = await fetch(event.request);
            if (networkResponse.ok) {
              cache.put(event.request, networkResponse.clone());
            }
            return networkResponse;
          } catch (error) {
            const cachedResponse = await cache.match(event.request);
            if (cachedResponse) {
              return cachedResponse;
            }
            return new Response(JSON.stringify({ ok: false, error: 'offline', from: 'service-worker' }), {
              headers: { 'Content-Type': 'application/json' }
            });
          }
        })
      );
    }
    // For non-GET API requests, do not cache. Only try the network.
    return;
  }

  // Navigation requests: Try network first, but fall back to the app shell for offline.
  if (event.request.mode === 'navigate') {
    event.respondWith(
      (async () => {
        try {
          const networkResponse = await fetch(event.request);
          return networkResponse;
        } catch (error) {
          console.log('[ServiceWorker] Navigation fetch failed, returning app shell.', error);
          const cache = await caches.open(CACHE_NAME);
          // The root '/' is our app shell.
          return await cache.match('/');
        }
      })()
    );
    return;
  }

  // For all other requests (static assets), use a cache-first strategy.
  event.respondWith(
    caches.open(CACHE_NAME).then(async (cache) => {
      const cachedResponse = await cache.match(event.request);
      if (cachedResponse) {
        return cachedResponse;
      }

      // If not in cache, fetch from network, cache it, and return.
      try {
        const networkResponse = await fetch(event.request);
        if (networkResponse.ok) {
          await cache.put(event.request, networkResponse.clone());
        }
        return networkResponse;
      } catch (error) {
        console.error('[ServiceWorker] Fetch failed for a static asset:', event.request.url, error);
        // We don't have a generic fallback for assets, so we let the error propagate.
        throw error;
      }
    })
  );
});

// Handle notification clicks.
self.addEventListener('notificationclick', event => {
    console.log('[ServiceWorker] Notification click Received.');
    event.notification.close();
    event.waitUntil(
        clients.openWindow('/')
    );
});

// Handle push notifications.
self.addEventListener('message', event => {
    if (event.data && event.data.type === 'SHOW_NOTIFICATION') {
        const { title, body } = event.data;
        event.waitUntil(
            self.registration.showNotification(title, {
                body: body,
                icon: '/static/favicon.svg',
                badge: '/static/favicon.svg'
            })
        );
    }
});
