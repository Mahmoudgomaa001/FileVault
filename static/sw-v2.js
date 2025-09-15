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

// Store the file received from a native share event temporarily.
let sharedFile = null;

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

          // Store the first file for the WebRTC transfer.
          sharedFile = files[0];
          console.log(`[ServiceWorker] Stored "${sharedFile.name}" for WebRTC transfer.`);

          // Notify the client that a file is ready.
          await broadcastToClients({ type: 'file-ready-for-webrtc' });
          console.log('[ServiceWorker] Notified client that file is ready.');

          // Redirect to the main page, where the client will handle the WebRTC initiation.
          return Response.redirect('/', 303);
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

// Helper to broadcast a message to all active clients.
const broadcastToClients = async (message) => {
    const clients = await self.clients.matchAll({
        includeUncontrolled: true,
        type: 'window',
    });
    clients.forEach((client) => {
        client.postMessage(message);
    });
};

let swPeerConnection;
let dataChannel;
const CHUNK_SIZE = 64 * 1024;

function sendFile(file) {
    if (!dataChannel || dataChannel.readyState !== 'open') {
        console.error('[SW] Data channel is not open. Cannot send file.');
        return;
    }
    console.log(`[SW] Sending file: ${file.name}`);

    // 1. Send metadata
    dataChannel.send(JSON.stringify({
        name: file.name,
        size: file.size,
        type: file.type
    }));

    // 2. Send file data in chunks
    const reader = new FileReader();
    let offset = 0;

    reader.onload = () => {
        if (dataChannel.readyState === 'open') {
            dataChannel.send(reader.result);
            offset += reader.result.byteLength;
            if (offset < file.size) {
                readSlice(offset);
            } else {
                console.log('[SW] Finished sending file.');
            }
        }
    };

    const readSlice = o => {
        const slice = file.slice(o, o + CHUNK_SIZE);
        reader.readAsArrayBuffer(slice);
    };
    readSlice(0);
}

self.addEventListener('message', async event => {
    console.log('[SW] Received message from client:', event.data);
    const { type, offer, candidate } = event.data;

    if (type === 'webrtc-offer') {
        if (swPeerConnection) {
            swPeerConnection.close();
        }
        swPeerConnection = new RTCPeerConnection({
             iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
        });

        // Send ICE candidates to the client
        swPeerConnection.onicecandidate = e => {
            if (e.candidate) {
                broadcastToClients({ type: 'webrtc-ice-candidate', candidate: e.candidate });
            }
        };

        // When the connection is made, create the data channel and send the file
        swPeerConnection.onconnectionstatechange = () => {
            if (swPeerConnection.connectionState === 'connected') {
                console.log('[SW] Peer connection established.');
                dataChannel = swPeerConnection.createDataChannel('file-transfer');
                dataChannel.onopen = () => {
                    if (sharedFile) {
                        sendFile(sharedFile);
                    } else {
                        console.error('[SW] No shared file to send.');
                    }
                };
            }
        };

        await swPeerConnection.setRemoteDescription(new RTCSessionDescription(offer));
        const answer = await swPeerConnection.createAnswer();
        await swPeerConnection.setLocalDescription(answer);

        broadcastToClients({ type: 'webrtc-answer', answer: answer });
        console.log('[SW] Sent answer to client.');

    } else if (type === 'webrtc-ice-candidate' && swPeerConnection) {
        try {
            await swPeerConnection.addIceCandidate(new RTCIceCandidate(candidate));
        } catch (e) {
            console.error('[SW] Error adding received ICE candidate', e);
        }
    } else if (event.data && event.data.type === 'SHOW_NOTIFICATION') {
        self.registration.showNotification(event.data.title, {
            body: event.data.body,
            icon: '/static/favicon.svg',
            badge: '/static/favicon.svg'
        });
    }
});
