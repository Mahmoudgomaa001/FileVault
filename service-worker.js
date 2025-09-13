// A version for the cache. Change this to force an update.
const CACHE_VERSION = 1;
const CACHE_NAME = `pwa-uploader-cache-v${CACHE_VERSION}`;

// A list of all the files that make up the app shell.
const APP_SHELL_URLS = [
    '/',
    '/index.html',
    '/share.html',
    '/app.js',
    '/style.css',
    '/manifest.json',
    '/icon.svg'
];

// --- INSTALL: Cache the app shell ---
self.addEventListener('install', (event) => {
    console.log('[Service Worker] Install');
    // waitUntil() ensures that the service worker will not install until the
    // code inside it has successfully occurred.
    event.waitUntil((async () => {
        const cache = await caches.open(CACHE_NAME);
        console.log('[Service Worker] Caching all: app shell and content');
        await cache.addAll(APP_SHELL_URLS);
    })());
});

// --- ACTIVATE: Clean up old caches ---
self.addEventListener('activate', (event) => {
    console.log('[Service Worker] Activate');
    event.waitUntil((async () => {
        const cacheNames = await caches.keys();
        await Promise.all(
            cacheNames.map((cacheName) => {
                // If the cache name is not the current one, delete it.
                if (cacheName !== CACHE_NAME) {
                    console.log(`[Service Worker] Deleting old cache: ${cacheName}`);
                    return caches.delete(cacheName);
                }
            })
        );
    })());
});


// --- FETCH: Serve from cache or network ---
self.addEventListener('fetch', (event) => {
    // This is the logic for the Web Share Target.
    // It intercepts the POST request when files are shared.
    if (event.request.method === 'POST' && event.request.url.endsWith('/share.html')) {
        event.respondWith((async () => {
            try {
                const formData = await event.request.formData();
                const files = formData.getAll('files');
                if (files && files.length > 0) {
                    await saveFilesToIndexedDB(files);
                }
                // After saving the files, redirect the user to the share page to see them.
                return Response.redirect('/share.html', 303);
            } catch (e) {
                console.error('[Service Worker] Error handling share target POST:', e);
                // If something goes wrong, just redirect to the share page anyway.
                return Response.redirect('/share.html', 303);
            }
        })());
        return; // Important: exit the fetch handler after responding.
    }

    // For all other GET requests, use a cache-first strategy.
    event.respondWith((async () => {
        const cache = await caches.open(CACHE_NAME);
        const cachedResponse = await cache.match(event.request);
        if (cachedResponse) {
            // Return the cached response if it exists.
            return cachedResponse;
        }
        // If the resource is not in the cache, try to fetch it from the network.
        return fetch(event.request);
    })());
});


// --- IndexedDB Helper Functions ---

/**
 * Saves an array of files to the 'files' object store in IndexedDB.
 * @param {File[]} files - An array of File objects to save.
 */
async function saveFilesToIndexedDB(files) {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open('PWAUploaderDB', 1);

        request.onupgradeneeded = (event) => {
            const db = event.target.result;
            db.createObjectStore('files', { keyPath: 'id', autoIncrement: true });
        };

        request.onsuccess = (event) => {
            const db = event.target.result;
            const transaction = db.transaction(['files'], 'readwrite');
            const store = transaction.objectStore('files');

            files.forEach(file => {
                store.add({
                    file: file,
                    name: file.name,
                    size: file.size,
                    type: file.type
                });
            });

            transaction.oncomplete = () => {
                console.log('[Service Worker] Files saved to IndexedDB');
                db.close();
                resolve();
            };

            transaction.onerror = (event) => {
                console.error('[Service Worker] Error saving files to IndexedDB:', event.target.error);
                db.close();
                reject(event.target.error);
            };
        };

        request.onerror = (event) => {
            console.error('[Service Worker] IndexedDB error:', event.target.error);
            reject(event.target.error);
        };
    });
}
