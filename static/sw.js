const VERSION = 'v9';
const CACHE_NAME = `filevault-cache-${VERSION}`;
const OFFLINE_URL = 'static/offline.html';
const APP_SHELL_URLS = [
  '/',
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
  OFFLINE_URL
];

async function cacheAllUserData() {
    console.log('[ServiceWorker] Starting to cache all user data.');
    try {
        const response = await fetch('/api/all_files');
        if (!response.ok) {
            console.error('[ServiceWorker] Failed to fetch file list for caching.');
            return;
        }
        const data = await response.json();
        if (data.ok && data.files) {
            const cache = await caches.open(CACHE_NAME);
            const urlsToCache = data.files.map(relPath => `/raw?path=${encodeURIComponent(relPath)}`);
            console.log(`[ServiceWorker] Caching ${urlsToCache.length} user files.`);
            // Use a loop with try-catch to not fail the whole batch if one file fails
            for (const url of urlsToCache) {
                try {
                    await cache.add(url);
                } catch (e) {
                    console.error(`[ServiceWorker] Failed to cache individual file: ${url}`, e);
                }
            }
        }
    } catch (error) {
        console.error('[ServiceWorker] Error caching all user data:', error);
    }
}

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
      .then(() => {
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
          if (cacheName !== CACHE_NAME) {
            console.log('[ServiceWorker] Clearing old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => {
      return self.clients.claim();
    }).then(() => {
        // After activation, immediately start caching user data.
        return cacheAllUserData();
    })
  );
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  if (event.request.mode === 'navigate') {
    event.respondWith(
      (async () => {
        try {
          const networkResponse = await fetch(event.request);
          if (networkResponse.ok) {
            const cache = await caches.open(CACHE_NAME);
            cache.put(event.request, networkResponse.clone());
            // If main page is loaded successfully online, trigger a background sync
            if (url.pathname === '/' || url.pathname.startsWith('/b/')) {
                event.waitUntil(cacheAllUserData());
            }
          }
          return networkResponse;
        } catch (error) {
          console.log('[ServiceWorker] Fetch failed; returning offline page or cached page.', error);
          const cache = await caches.open(CACHE_NAME);
          const cachedResponse = await cache.match(event.request);
          if (cachedResponse) {
            return cachedResponse;
          }
          return await cache.match(OFFLINE_URL);
        }
      })()
    );
  } else if (url.pathname.startsWith('/api/')) {
    event.respondWith(
        fetch(event.request).catch(() => {
            return new Response(JSON.stringify({ ok: false, error: 'offline' }), {
                headers: { 'Content-Type': 'application/json' }
            });
        })
    );
  } else {
    event.respondWith(
      caches.open(CACHE_NAME).then(cache => {
        return cache.match(event.request).then(cachedResponse => {
          if (cachedResponse) {
            return cachedResponse;
          }
          return fetch(event.request).then(networkResponse => {
            if (networkResponse.ok) {
              cache.put(event.request, networkResponse.clone());
            }
            return networkResponse;
          });
        });
      })
    );
  }
});
