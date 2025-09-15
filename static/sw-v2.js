importScripts('/static/js/db.js');

const VERSION = 'v16'; // Incrementing version to ensure SW updates
const CACHE_NAME = `filevault-cache-${VERSION}`;
const OFFLINE_URL = '/static/offline.html';

const APP_SHELL_URLS = [
  '/static/launcher.html',
  '/',
  '/b/',
  '/login',
  '/static/css/style.css',
  '/static/js/main.js',
  '/static/js/config.js',
  '/static/js/db.js',
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

let sharedFile = null;

self.addEventListener('install', event => {
  console.log(`[ServiceWorker] Install event for version ${VERSION}`);
  event.waitUntil(self.skipWaiting());
});

self.addEventListener('activate', event => {
  console.log(`[ServiceWorker] Activate event for version ${VERSION}`);
  event.waitUntil(
    (async () => {
      const cacheNames = await caches.keys();
      await Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
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

  if (event.request.method === 'POST' && url.pathname === '/share-target/') {
    event.respondWith(
      (async () => {
        const formData = await event.request.formData();
        const files = formData.getAll('files');
        if (files && files.length > 0) {
          sharedFile = files[0];
          const clients = await self.clients.matchAll({ includeUncontrolled: true, type: 'window' });
          if (clients && clients.length > 0) {
            clients[0].postMessage({ type: 'share-file-ready', file: sharedFile });
            return new Response('Share processed by active client.', { status: 200 });
          } else {
            await saveFile(sharedFile);
            return Response.redirect('/static/launcher.html?share=saved-offline', 303);
          }
        }
        return Response.redirect('/static/launcher.html?share=empty', 303);
      })()
    );
    return;
  }

  // Standard cache-first for other requests
  event.respondWith(
    caches.match(event.request).then(response => {
      return response || fetch(event.request);
    })
  );
});

self.addEventListener('message', event => {
  // This listener is for messages from the client page,
  // but for this flow, the SW only sends messages, it doesn't need to receive any.
  console.log('[SW] Received message:', event.data);
});
