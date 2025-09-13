const VERSION = 'v13'; // Updated version to force update
const CACHE_NAME = `filevault-cache-${VERSION}`;
const OFFLINE_URL = '/static/offline.html';

// --- IndexedDB for File Storage (copied from db.js for SW context) ---
const DB_NAME = 'pwa-file-storage';
const STORE_NAME = 'files';
let db;

function initDB() {
  return new Promise((resolve, reject) => {
    if (db) return resolve(db);
    const request = self.indexedDB.open(DB_NAME, 2); // Version 2 for config store
    request.onerror = e => { console.error('SW DB error:', e.target.error); reject('SW DB error'); };
    request.onsuccess = e => { db = e.target.result; resolve(db); };
    request.onupgradeneeded = e => {
      const dbInstance = e.target.result;
      if (!dbInstance.objectStoreNames.contains('files')) {
        dbInstance.createObjectStore('files', { keyPath: 'id', autoIncrement: true });
      }
      if (!dbInstance.objectStoreNames.contains('config')) {
        dbInstance.createObjectStore('config', { keyPath: 'key' });
      }
    };
  });
}

function saveFileInDB(file) {
  return new Promise((resolve, reject) => {
    initDB().then(db => {
      const transaction = db.transaction([STORE_NAME], 'readwrite');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.add({ file: file, name: file.name, size: file.size });
      request.onsuccess = e => resolve(e.target.result);
      request.onerror = e => { console.error('SW Error saving file:', e.target.error); reject('Error saving file'); };
    });
  });
}
// --- End of DB Logic ---

const APP_SHELL_URLS = [
  '/static/launcher.html', '/static/share.html', '/', '/b/', '/login',
  '/static/css/style.css', '/static/js/main.js', '/static/js/config.js', '/static/js/db.js', '/static/js/share.js', '/static/js/launcher.js',
  '/static/fonts.css', '/static/vendor/fontawesome/css/all.min.css', '/static/vendor/fontawesome/css/fa-shims.css',
  '/static/socket.io.min.js', '/static/site.webmanifest', '/static/favicon.svg', '/static/adhkar.json',
  '/static/vendor/fontawesome/webfonts/fa-brands-400.woff2', '/static/vendor/fontawesome/webfonts/fa-regular-400.woff2', '/static/vendor/fontawesome/webfonts/fa-solid-900.woff2',
  OFFLINE_URL
];

self.addEventListener('install', event => {
  console.log(`[ServiceWorker] Install event for version ${VERSION}`);
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE_NAME);
      console.log('[ServiceWorker] Caching app shell with cache-busting...');
      // **FIX:** Use 'reload' to bypass the HTTP cache for all app shell files.
      const requests = APP_SHELL_URLS.map(url => new Request(url, { cache: 'reload' }));
      await cache.addAll(requests).catch(error => console.error('[ServiceWorker] App shell cache failed:', error));
      await self.skipWaiting();
    })()
  );
});

self.addEventListener('activate', event => {
  console.log(`[ServiceWorker] Activate event for version ${VERSION}`);
  event.waitUntil(
    (async () => {
      const cacheNames = await caches.keys();
      await Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            console.log('[ServiceWorker] Clearing old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
      await self.clients.claim();
    })()
  );
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // Robustly handle Web Share Target POST requests
  if (event.request.method === 'POST' && url.pathname === '/static/share.html') {
    event.respondWith(
      (async () => {
        try {
            const formData = await event.request.formData();
            const formData = await event.request.formData();
            const files = formData.getAll('files');
            let savedCount = 0;
            if (files && files.length > 0) {
              await initDB();
              for (const file of files) {
                await saveFileInDB(file);
              }
              savedCount = files.length;
            }
            // Add a timestamp to the redirect to ensure it's not cached
            const timestamp = Date.now();
            return Response.redirect(`/static/share.html?saved=${savedCount}&ts=${timestamp}`, 303);
        } catch (err) {
            console.error('[ServiceWorker] Error handling share POST:', err);
            return Response.redirect(`/static/share.html?saved=error&ts=${Date.now()}`, 303);
        }
      })()
    );
    return;
  }

  // The special handling for /config.json has been removed, as configuration
  // is now managed entirely in the client via IndexedDB.

  // Cache-first strategy for navigation
  if (event.request.mode === 'navigate') {
    event.respondWith(
      caches.open(CACHE_NAME).then(async cache => {
        try {
          const cachedResponse = await cache.match(event.request);
          if (cachedResponse) {
            return cachedResponse;
          }
          const networkResponse = await fetch(event.request);
          if (networkResponse.ok) {
            cache.put(event.request, networkResponse.clone());
          }
          return networkResponse;
        } catch (error) {
          console.log('[ServiceWorker] Network fetch failed for navigation, returning offline page.', error);
          return await cache.match(OFFLINE_URL);
        }
      })
    );
    return;
  }

  // Network-only for API calls
  if (url.pathname.startsWith('/api/')) {
      event.respondWith(fetch(event.request));
      return;
  }

  // Cache-first for static assets
  event.respondWith(
    caches.match(event.request).then(cachedResponse => {
      return cachedResponse || fetch(event.request).then(networkResponse => {
        if (networkResponse.ok) {
          const cache = caches.open(CACHE_NAME);
          cache.then(c => c.put(event.request, networkResponse.clone()));
        }
        return networkResponse;
      });
    })
  );
});

self.addEventListener('message', event => {
    if (event.data && event.data.type === 'SHOW_NOTIFICATION') {
        self.registration.showNotification(event.data.title, {
            body: event.data.body,
            icon: '/static/favicon.svg',
            badge: '/static/favicon.svg'
        });
    }
});
