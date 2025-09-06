const VERSION = 'v11';
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

// A single function to fetch all dynamic content (pages and files) for offline use.
async function syncAllDataForOffline() {
    console.log('[ServiceWorker] Starting full offline sync.');
    const cache = await caches.open(CACHE_NAME);

    // 1. Cache all pages
    // 1. Cache all pages
    try {
        const pagesResponse = await fetch('/api/all_pages');
        if (pagesResponse.ok) {
            const data = await pagesResponse.json();
            if (data.ok && data.pages) {
                console.log(`[ServiceWorker] Caching ${data.pages.length} pages.`);
                for (const pageUrl of data.pages) {
                    try {
                        // A page might not be in the cache, or it might be stale.
                        // We will always re-fetch it to ensure it's up-to-date.
                        await cache.add(pageUrl);
                    } catch (e) {
                        console.error(`[ServiceWorker] Failed to cache individual page: ${pageUrl}`, e);
                    }
                }
            }
        }
    } catch (error) {
        console.error('[ServiceWorker] Failed to fetch page list:', error);
    }

    // 2. Cache all user files
    try {
        const filesResponse = await fetch('/api/all_files');
        if (filesResponse.ok) {
            const data = await filesResponse.json();
            if (data.ok && data.files) {
                const urlsToCache = data.files.map(relPath => `/raw?path=${encodeURIComponent(relPath)}`);
                console.log(`[ServiceWorker] Caching ${urlsToCache.length} user files.`);
                // Don't use addAll for files as a single large file failing could stop everything.
                // Instead, iterate and cache one by one.
                for (const url of urlsToCache) {
                    try {
                        // Check if the request is already in the cache. If not, fetch and cache it.
                        const cachedResponse = await cache.match(url);
                        if (!cachedResponse) {
                            await cache.add(url);
                        }
                    } catch (e) {
                        console.error(`[ServiceWorker] Failed to cache individual file: ${url}`, e);
                    }
                }
            }
        }
    } catch (error) {
        console.error('[ServiceWorker] Failed to cache user files:', error);
    }
    console.log('[ServiceWorker] Full offline sync finished.');
}

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
        // After activation, immediately start the full offline sync.
        console.log('[ServiceWorker] Activating and triggering full sync.');
        return syncAllDataForOffline();
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
                event.waitUntil(syncAllDataForOffline());
            }
          }
          return networkResponse;
        } catch (error) {
          console.log('[ServiceWorker] Fetch failed for navigation; returning from cache.', error);
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
    // For API requests, always go to the network.
    // The app's frontend should handle offline errors.
    event.respondWith(
        fetch(event.request).catch(() => {
            return new Response(JSON.stringify({ ok: false, error: 'offline', message: 'The server is unreachable.' }), {
                headers: { 'Content-Type': 'application/json' }
            });
        })
    );
  } else {
    // For all other assets, use a cache-first strategy.
    event.respondWith(
      caches.open(CACHE_NAME).then(cache => {
        return cache.match(event.request).then(cachedResponse => {
          return cachedResponse || fetch(event.request).then(networkResponse => {
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
