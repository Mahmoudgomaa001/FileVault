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

self.addEventListener('install', event => {
  console.log('[ServiceWorker] Install event fired');
  event.waitUntil(
    Promise.all([
      caches.open(CACHE_NAME).then(cache => {
        console.log('[ServiceWorker] Caching app shell');
        return cache.addAll(APP_SHELL_URLS).catch(error => {
          console.error('[ServiceWorker] App shell caching failed:', error);
        });
      }),
      openDB().then(db => {
        console.log('[ServiceWorker] IndexedDB opened successfully during install.');
        db.close();
      }).catch(error => {
        console.error('[ServiceWorker] IndexedDB could not be opened during install:', error);
      })
    ]).then(() => {
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

const DB_NAME = 'share-target-db';
const DB_VERSION = 1;
const STORE_NAME = 'shared-files';

function openDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = event => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true });
      }
    };
    request.onsuccess = event => resolve(event.target.result);
    request.onerror = event => reject(event.target.error);
  });
}

async function saveFileToDB(file) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction([STORE_NAME], 'readwrite');
    const store = transaction.objectStore(STORE_NAME);
    const request = store.add({ file: file, name: file.name, timestamp: new Date() });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  if (event.request.method === 'POST' && url.pathname === '/share-receiver') {
    console.log('[ServiceWorker] Intercepted share POST request.');
    event.respondWith(
      (async () => {
        try {
          console.log('[ServiceWorker] Processing form data...');
          const formData = await event.request.formData();
          const files = formData.getAll('files');
          console.log(`[ServiceWorker] Found ${files.length} files to save.`);

          if (files.length === 0) {
            console.warn('[ServiceWorker] Share request contained no files.');
            return Response.redirect('/share', 303);
          }

          // Save each file to IndexedDB
          for (const file of files) {
            console.log(`[ServiceWorker] Saving file to IndexedDB: ${file.name}`);
            await saveFileToDB(file);
            console.log(`[ServiceWorker] Successfully saved ${file.name}`);
          }

          console.log('[ServiceWorker] All files saved. Redirecting to /share.');
          // Redirect to the share page to manage the files
          return Response.redirect('/share', 303);
        } catch (error) {
          console.error('[ServiceWorker] Error handling share POST:', error);
          // IMPORTANT: As a fallback, always redirect to the share page.
          // This prevents the browser from making a direct network request.
          return Response.redirect('/share', 303);
        }
      })()
    );
    return;
  }

  // For navigation requests, use a network-first strategy.
  if (event.request.mode === 'navigate') {
    event.respondWith(
      (async () => {
        try {
          // Try the network first.
          const networkResponse = await fetch(event.request);

          // If successful, cache the response for future offline use.
          const cache = await caches.open(CACHE_NAME);
          // Do not cache error pages
          if(networkResponse.ok) {
            cache.put(event.request, networkResponse.clone());
          }

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
  }
  // For API calls, use a network-first strategy as well, but don't fall back to offline page.
  else if (url.pathname.startsWith('/api/')) {
    event.respondWith(
        fetch(event.request).catch(() => {
            return new Response(JSON.stringify({ ok: false, error: 'offline' }), {
                headers: { 'Content-Type': 'application/json' }
            });
        })
    );
  }
  // For all other requests (CSS, JS, images, fonts), use a cache-first strategy.
  else {
    event.respondWith(
      caches.open(CACHE_NAME).then(cache => {
        return cache.match(event.request).then(cachedResponse => {
          // If we have a cached response, return it.
          if (cachedResponse) {
            return cachedResponse;
          }

          // Otherwise, fetch from the network, cache it, and then return it.
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
