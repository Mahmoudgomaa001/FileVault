const VERSION = 'v11';
const CACHE_NAME = `filevault-cache-${VERSION}`;
const OFFLINE_URL = '/static/offline.html';
const APP_SHELL_URLS = [
  OFFLINE_URL,
  '/static/fonts.css',
  '/static/vendor/fontawesome/css/all.min.css',
  '/static/vendor/fontawesome/css/fa-shims.css',
  '/static/socket.io.min.js',
  '/static/site.webmanifest',
  '/static/favicon.svg',
  '/static/adhkar.json',
  '/static/vendor/fontawesome/webfonts/fa-brands-400.ttf',
  '/static/vendor/fontawesome/webfonts/fa-brands-400.woff2',
  '/static/vendor/fontawesome/webfonts/fa-regular-400.ttf',
  '/static/vendor/fontawesome/webfonts/fa-regular-400.woff2',
  '/static/vendor/fontawesome/webfonts/fa-solid-900.ttf',
  '/static/vendor/fontawesome/webfonts/fa-solid-900.woff2',
];

self.addEventListener('install', event => {
  console.log('[ServiceWorker] Install event fired');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('[ServiceWorker] Caching app shell and offline page');
        return cache.addAll(APP_SHELL_URLS).catch(error => {
          console.error('[ServiceWorker] Failed to cache app shell:', error);
        });
      })
      .then(() => self.skipWaiting())
  );
});

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
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  if (event.request.method === 'POST' && url.pathname === '/share-receiver') {
    event.respondWith(Response.redirect('/share'));
    event.waitUntil(
      (async function () {
        const formData = await event.request.formData();
        const client = await self.clients.get(event.resultingClientId);
        client.postMessage({ files: formData.getAll('files') });
      })()
    );
    return;
  }

  if (event.request.mode === 'navigate') {
    event.respondWith(
      (async () => {
        try {
          const networkResponse = await fetch(event.request);
          // If successful, cache the response for future offline use.
          const cache = await caches.open(CACHE_NAME);
          if (networkResponse.ok) {
            cache.put(event.request, networkResponse.clone());
          }
          return networkResponse;
        } catch (error) {
          console.log('[ServiceWorker] Fetch failed; trying cache...', error);
          const cache = await caches.open(CACHE_NAME);
          const cachedResponse = await cache.match(event.request);
          if (cachedResponse) {
            return cachedResponse;
          }
          // If the page is not in the cache, serve the master offline page.
          console.log('[ServiceWorker] Page not in cache; returning offline page.');
          return await cache.match(OFFLINE_URL);
        }
      })()
    );
  } else if (url.pathname.startsWith('/api/')) {
    // For API calls, it's network-first, but we don't cache or serve offline content.
    // The offline.html page will handle API failures gracefully.
    event.respondWith(
      fetch(event.request).catch(() => {
        return new Response(JSON.stringify({ ok: false, error: 'offline' }), {
          headers: { 'Content-Type': 'application/json' }
        });
      })
    );
  } else {
    // For all other requests (CSS, JS, images), use a cache-first strategy.
    event.respondWith(
      caches.open(CACHE_NAME).then(async (cache) => {
        const cachedResponse = await cache.match(event.request);
        if (cachedResponse) {
          return cachedResponse;
        }
        const networkResponse = await fetch(event.request);
        if (networkResponse && networkResponse.status === 200) {
          cache.put(event.request, networkResponse.clone());
        }
        return networkResponse;
      })
    );
  }
});

self.addEventListener('notificationclick', event => {
    console.log('[ServiceWorker] Notification click Received.');
    event.notification.close();
    event.waitUntil(
        clients.openWindow('/')
    );
});

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
