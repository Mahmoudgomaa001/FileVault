importScripts('/static/js/db.js');

const VERSION = 'v14'; // Updated version for share target fix
const CACHE_NAME = `filevault-cache-${VERSION}`;
const OFFLINE_URL = '/static/offline.html';

const APP_SHELL_URLS = [
  '/static/launcher.html',
  // share.html is no longer needed
  '/',
  '/b/',
  '/login',
  '/static/css/style.css',
  '/static/js/main.js',
  '/static/js/config.js',
  '/static/js/db.js',
  // share.js is no longer needed
  '/static/js/launcher.js',
  '/static/fonts.css',
  '/static/vendor/fontawesome/css/all.min.css',
  '/static/vendor/fontawesome/css/fa-shims.css',
  '/static/socket.io.min.js',
  '/static/site.webmanifest',
  '/static/favicon.svg',
  '/static/adhkar.json',
  '/static/vendor/fontawesome/webfonts/fa-brands-400.woff2',
  '/static/vendor/fontawesome/webfonts/fa-regular-400.woff2',
  '/static/vendor/fontawesome/webfonts/fa-solid-900.woff2',
  OFFLINE_URL
];

self.addEventListener('install', event => {
  console.log(`[ServiceWorker] Install event for version ${VERSION}`);
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE_NAME);
      console.log('[ServiceWorker] Caching app shell...');
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

  // --- Share Target Interception ---
  if (event.request.method === 'POST' && url.pathname === '/share-target/') {
    console.log('[ServiceWorker] Intercepting share target POST request.');
    event.respondWith(
      (async () => {
        try {
          const formData = await event.request.formData();
          const files = formData.getAll('files'); // 'files' is the name from manifest
          if (!files || files.length === 0) {
            console.log('[ServiceWorker] No files found in share data.');
            return Response.redirect('/static/launcher.html?share=empty', 303);
          }

          console.log(`[ServiceWorker] Received ${files.length} files to save.`);

          // The saveFile function is from db.js, imported via importScripts()
          for (const file of files) {
            await saveFile(file);
            console.log(`[ServiceWorker] Saved file "${file.name}" to IndexedDB.`);
          }

          // Redirect to the launcher page after saving.
          return Response.redirect('/static/launcher.html?share=success', 303);
        } catch (error) {
          console.error('[ServiceWorker] Error handling share target:', error);
          return Response.redirect('/static/launcher.html?share=error', 303);
        }
      })()
    );
    return; // Stop further processing for this request.
  }

  // Cache-first strategy for navigation
  if (event.request.mode === 'navigate') {
    event.respondWith(
      caches.open(CACHE_NAME).then(async cache => {
        try {
          const cachedResponse = await cache.match(event.request);
          if (cachedResponse) return cachedResponse;
          const networkResponse = await fetch(event.request);
          if (networkResponse.ok) {
            cache.put(event.request, networkResponse.clone());
          }
          return networkResponse;
        } catch (error) {
          console.log('[ServiceWorker] Fetch failed for navigation, returning offline page.', error);
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
