# PWA Review Bundle

This file contains the concatenated source code for all PWA-related features for review.

---

## `static/launcher.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FileVault Launcher</title>
    <link rel="stylesheet" href="/static/css/style.css?v=final">
    <link rel="manifest" href="/static/site.webmanifest" />
    <style>
        body {
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background-color: var(--bg-primary);
            color: var(--text-primary);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        }
        .launcher {
            text-align: center;
        }
        .launcher h1 {
            font-size: 2.5rem;
            display: flex;
            align-items: center;
            gap: 1rem;
        }
        .btn-launcher {
            display: block;
            width: 100%;
            padding: 1.5rem;
            font-size: 1.5rem;
            margin-top: 1.5rem;
            border-radius: 0.75rem;
            text-decoration: none;
            border: none;
            cursor: pointer;
        }
        .btn-launcher.local {
            background-color: var(--primary);
            color: white;
        }
        .btn-launcher.server {
            background-color: var(--secondary);
            color: white;
        }
        .btn-launcher:disabled {
            background-color: var(--bg-secondary);
            color: var(--text-muted);
            cursor: not-allowed;
        }
        #settingsBtn {
            margin-top: 2rem;
            background: none;
            border: none;
            color: var(--text-muted);
            cursor: pointer;
            font-size: 1rem;
        }
    </style>
</head>
<body>
    <div class="launcher">
        <h1><img src="/static/favicon.svg" alt="FileVault Logo" width="64" height="64"> FileVault</h1>
        <p style="font-size: 1.1rem; color: var(--text-secondary);">Your offline PWA launcher.</p>
        <a href="#" id="goLocalBtn" class="btn btn-launcher local" disabled>Connect to Local</a>
        <a href="#" id="goServerBtn" class="btn btn-launcher server" disabled>Connect to Server</a>
        <button id="settingsBtn"><i class="fas fa-cog"></i> Settings</button>
    </div>

    <!-- App Settings Modal (copied from base.html) -->
    <div class="modal" id="appSettingsModal">
      <div class="modal-content">
        <div class="modal-header">
          <h3 class="modal-title">App Settings</h3>
          <button class="modal-close" onclick="closeModal('appSettingsModal')" aria-label="Close">&times;</button>
        </div>
        <div class="modal-body">
          <p>Manually set the URLs used by the application.</p>
          <div class="form-group">
            <label class="form-label" for="localUrlInput">Local IP URL</label>
            <input type="text" id="localUrlInput" class="form-input" placeholder="e.g., http://192.168.1.10:5000">
          </div>
          <div class="form-group" style="margin-top: 1rem;">
            <label class="form-label" for="serverUrlInput">Server URL</label>
            <input type="text" id="serverUrlInput" class="form-input" placeholder="e.g., https://your-server.com">
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" onclick="closeModal('appSettingsModal')">Cancel</button>
          <button class="btn btn-primary" id="saveAppSettingsBtn">Save</button>
        </div>
      </div>
    </div>

    <div id="toastContainer"></div>
    <script>
        // Minimal modal/toast logic for this page
        function openModal(id){ document.getElementById(id).classList.add('active'); }
        function closeModal(id){ document.getElementById(id).classList.remove('active'); }
        function showToast(message, type = 'info') { const c = document.getElementById('toastContainer'); if (!c) return; const t = document.createElement('div'); t.className = `toast ${type}`; t.innerHTML = `<div class="toast-message">${message}</div>`; c.appendChild(t); setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 300); }, 3000); }
    </script>
    <script src="/static/js/db.js?v=final"></script>
    <script src="/static/js/config.js?v=final"></script>
    <script src="/static/js/launcher.js?v=final"></script>
</body>
</html>
```

---

## `static/share.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Share Files - FileVault</title>
    <link rel="stylesheet" href="/static/css/style.css?v=final">
    <link rel="stylesheet" href="/static/vendor/fontawesome/css/all.min.css" />
    <link rel="manifest" href="/static/site.webmanifest" />
    <meta name="theme-color" content="#0F172A" />
</head>
<body>
    <div class="container" style="padding-top: 2rem;">
        <div class="card" id="mainContainer">
            <h1 style="display: flex; align-items: center; gap: .75rem;"><img src="/static/favicon.svg" alt="" width="40" height="40"> Shared Files</h1>
            <p>Files shared or uploaded to the app are stored locally on your device. You can now close this page and open the main FileVault application to upload them.</p>

            <!-- Manual File Upload -->
            <div class="upload-section" style="margin-top: 1rem; border-style: dashed;">
                <div class="upload-area" id="uploadArea">
                <input type="file" id="manualUploadInput" class="upload-input" multiple>
                <div class="upload-icon"><i class="fas fa-file-upload"></i></div>
                <div class="upload-text">Drop files or tap here to add to the queue</div>
                </div>
            </div>

            <!-- File List -->
            <h2 style="margin-top: 2rem;">Pending Files (<span id="file-count">0</span>)</h2>
            <div id="file-list" class="file-list-container" style="margin-top: 1rem;">
                <div id="no-files-message" class="card" style="text-align:center; color:var(--text-muted);">No files are currently pending.</div>
            </div>

            <!-- Action Buttons -->
            <div style="display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 1.5rem;">
                <button class="btn btn-primary" id="send-local-btn" disabled><i class="fas fa-network-wired"></i> Send to Local (Raw)</button>
                <button class="btn btn-secondary" id="send-server-btn" disabled><i class="fas fa-server"></i> Send to Server (Raw)</button>
                <button class="btn btn-danger" id="clear-all-btn" disabled><i class="fas fa-trash"></i> Clear All</button>
            </div>
            <!-- Upload Progress -->
            <div id="progress-container" class="progress-container-share" style="margin-top: 1rem;"></div>
        </div>
    </div>

    <div id="toastContainer"></div>

    <script src="/static/js/config.js?v=final"></script>
    <script src="/static/js/db.js?v=final"></script>
    <script src="/static/js/share.js?v=final"></script>
</body>
</html>
```

---

## `static/sw-v2.js`

```javascript
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

  // The service worker no longer intercepts the share POST request.
  // It is now handled by the server at the /share-receiver endpoint,
  // which then redirects to the static share page.

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
```

---

## `static/js/db.js`

```javascript
// --- IndexedDB for File Storage ---

const DB_NAME = 'pwa-file-storage';
const FILE_STORE = 'files';
const CONFIG_STORE = 'config';
let db;

/**
 * Initializes the IndexedDB database.
 * @returns {Promise<IDBDatabase>} A promise that resolves with the database object.
 */
function initDB() {
  return new Promise((resolve, reject) => {
    if (db) {
      return resolve(db);
    }
    // Increment version to 2 to trigger onupgradeneeded for new store
    const request = indexedDB.open(DB_NAME, 2);

    request.onerror = (event) => {
      console.error('Database error:', event.target.error);
      reject('Database error');
    };

    request.onsuccess = (event) => {
      db = event.target.result;
      console.log('Database opened successfully.');
      resolve(db);
    };

    request.onupgradeneeded = (event) => {
      const dbInstance = event.target.result;
      if (!dbInstance.objectStoreNames.contains(FILE_STORE)) {
        dbInstance.createObjectStore(FILE_STORE, { keyPath: 'id', autoIncrement: true });
        console.log('Object store "files" created.');
      }
      if (!dbInstance.objectStoreNames.contains(CONFIG_STORE)) {
        // This store will hold key-value pairs, e.g., { key: 'api_token', value: '...' }
        dbInstance.createObjectStore(CONFIG_STORE, { keyPath: 'key' });
        console.log('Object store "config" created.');
      }
    };
  });
}

/**
 * Saves or updates a configuration value in the config store.
 * @param {string} key - The key for the config value (e.g., 'api_token').
 * @param {*} value - The value to store.
 * @returns {Promise<void>}
 */
function saveConfigValue(key, value) {
    return new Promise((resolve, reject) => {
        initDB().then(db => {
            const transaction = db.transaction([CONFIG_STORE], 'readwrite');
            const store = transaction.objectStore(CONFIG_STORE);
            const request = store.put({ key: key, value: value });
            request.onsuccess = () => resolve();
            request.onerror = (event) => reject('Error saving config value: ' + event.target.error);
        });
    });
}

/**
 * Retrieves a configuration value from the config store.
 * @param {string} key - The key of the config value to retrieve.
 * @returns {Promise<*>} A promise that resolves with the stored value or undefined.
 */
function getConfigValue(key) {
    return new Promise((resolve, reject) => {
        initDB().then(db => {
            const transaction = db.transaction([CONFIG_STORE], 'readonly');
            const store = transaction.objectStore(CONFIG_STORE);
            const request = store.get(key);
            request.onsuccess = (event) => {
                resolve(event.target.result ? event.target.result.value : undefined);
            };
            request.onerror = (event) => reject('Error getting config value: ' + event.target.error);
        });
    });
}

/**
 * Saves a file to the IndexedDB.
 * @param {File} file - The file object to save.
 * @returns {Promise<number>} A promise that resolves with the ID of the saved file.
 */
function saveFile(file) {
  return new Promise((resolve, reject) => {
    initDB().then(db => {
      const transaction = db.transaction([FILE_STORE], 'readwrite');
      const store = transaction.objectStore(FILE_STORE);
      const request = store.add({ file: file, name: file.name, size: file.size });

      request.onsuccess = (event) => {
        resolve(event.target.result);
      };

      request.onerror = (event) => {
        console.error('Error saving file:', event.target.error);
        reject('Error saving file');
      };
    });
  });
}

/**
 * Retrieves all files from the IndexedDB.
 * @returns {Promise<Array<object>>} A promise that resolves with an array of file objects.
 */
function getFiles() {
  return new Promise((resolve, reject) => {
    initDB().then(db => {
      const transaction = db.transaction([FILE_STORE], 'readonly');
      const store = transaction.objectStore(FILE_STORE);
      const request = store.getAll();

      request.onsuccess = (event) => {
        resolve(event.target.result);
      };

      request.onerror = (event) => {
        console.error('Error getting files:', event.target.error);
        reject('Error getting files');
      };
    });
  });
}

/**
 * Deletes a file from IndexedDB by its ID.
 * @param {number} id - The ID of the file to delete.
 * @returns {Promise<void>}
 */
function deleteFile(id) {
  return new Promise((resolve, reject) => {
    initDB().then(db => {
      const transaction = db.transaction([FILE_STORE], 'readwrite');
      const store = transaction.objectStore(FILE_STORE);
      const request = store.delete(id);

      request.onsuccess = () => {
        resolve();
      };
      request.onerror = (event) => {
        reject('Error deleting file: ' + event.target.error);
      };
    });
  });
}


/**
 * Clears all files from the IndexedDB object store.
 * @returns {Promise<void>}
 */
function clearFiles() {
  return new Promise((resolve, reject) => {
    initDB().then(db => {
      const transaction = db.transaction([FILE_STORE], 'readwrite');
      const store = transaction.objectStore(FILE_STORE);
      const request = store.clear();

      request.onsuccess = () => {
        console.log('All files cleared from IndexedDB.');
        resolve();
      };

      request.onerror = (event) => {
        console.error('Error clearing files:', event.target.error);
        reject('Error clearing files');
      };
    });
  });
}

window.fileDB = {
  initDB,
  saveFile,
  getFiles,
  deleteFile,
  clearFiles,
  saveConfigValue,
  getConfigValue
};
```

---

## `static/js/config.js`

```javascript
// --- Configuration Management using IndexedDB ---

// In-memory cache of the config
let appConfig = {
  local_url: '',
  server_url: ''
};

/**
 * Loads configuration (local_url, server_url) from IndexedDB.
 * This is the single source of truth for PWA configuration.
 * @returns {Promise<object>} A promise that resolves with the configuration object.
 */
async function loadConfig() {
  try {
    // db.js must be loaded before this file.
    if (!window.fileDB) throw new Error("fileDB is not available.");

    await window.fileDB.initDB();
    const local_url = await window.fileDB.getConfigValue('local_url');
    const server_url = await window.fileDB.getConfigValue('server_url');

    appConfig = {
        local_url: local_url || '',
        server_url: server_url || ''
    };
    console.log('Configuration loaded from IndexedDB:', appConfig);
    return appConfig;
  } catch (error) {
    console.error('Could not load configuration from IndexedDB:', error);
    // Return default empty config on failure
    return appConfig;
  }
}

/**
 * Returns the currently loaded configuration from the in-memory cache.
 * @returns {object} The application configuration.
 */
function getConfig() {
  return appConfig;
}

/**
 * Saves the configuration object to IndexedDB.
 * @param {object} newConfig - The configuration object to save. Must have local_url and server_url.
 * @returns {Promise<void>}
 */
async function saveConfig(newConfig) {
    try {
        if (!window.fileDB) throw new Error("fileDB is not available.");
        await window.fileDB.initDB();

        // Use Promise.all to save both values concurrently.
        await Promise.all([
            window.fileDB.saveConfigValue('local_url', newConfig.local_url || ''),
            window.fileDB.saveConfigValue('server_url', newConfig.server_url || '')
        ]);

        // Update the in-memory config object
        appConfig = { ...appConfig, ...newConfig };
        console.log('Configuration saved to IndexedDB:', appConfig);
    } catch (error) {
        console.error('Failed to save config to IndexedDB:', error);
        throw error; // Re-throw so the caller knows it failed
    }
}

// Expose functions to the global scope
window.appConfigManager = {
  loadConfig,
  getConfig,
  saveConfig
};
```

---

## `static/js/launcher.js`

```javascript
document.addEventListener('DOMContentLoaded', async () => {
    const goLocalBtn = document.getElementById('goLocalBtn');
    const goServerBtn = document.getElementById('goServerBtn');
    const settingsBtn = document.getElementById('settingsBtn');
    const saveAppSettingsBtn = document.getElementById('saveAppSettingsBtn');
    const localUrlInput = document.getElementById('localUrlInput');
    const serverUrlInput = document.getElementById('serverUrlInput');

    let apiToken = null;
    let config = {};

    async function updateButtonLinks() {
        if (!apiToken) {
            showToast('API Token not found. Please set one up in the main app settings.', 'warning');
        }

        // The "Connect to Server" button is a simple link, but we can also use the token for a seamless login.
        if (config.server_url) {
            const loginUrl = new URL('/login', config.server_url);
            if (apiToken) loginUrl.searchParams.set('token', apiToken);
            goServerBtn.href = loginUrl.href;
            goServerBtn.disabled = false;
        } else {
            goServerBtn.href = '#';
            goServerBtn.disabled = true;
        }

        // The "Connect to Local" button passes all the necessary config and tokens.
        if (config.local_url) {
            const loginUrl = new URL('/login_and_sync', config.local_url);
            if (apiToken) loginUrl.searchParams.set('token', apiToken);
            if (config.server_url) loginUrl.searchParams.set('remote_server_url', config.server_url);
            // Pass the local URL itself so the main app knows its own address
            loginUrl.searchParams.set('local_url', config.local_url);

            goLocalBtn.href = loginUrl.href;
            goLocalBtn.disabled = !apiToken;
        } else {
            goLocalBtn.href = '#';
            goLocalBtn.disabled = true;
        }
    }

    async function initialize() {
        try {
            await window.fileDB.initDB();
            apiToken = await window.fileDB.getConfigValue('api_token');
            config = await window.appConfigManager.loadConfig();
            await updateButtonLinks();
        } catch (e) {
            console.error("Failed to initialize launcher:", e);
            showToast('Could not load configuration or token.', 'error');
        }
    }

    if (settingsBtn) {
        settingsBtn.addEventListener('click', () => {
            const currentConfig = window.appConfigManager.getConfig();
            if (localUrlInput) localUrlInput.value = currentConfig.local_url;
            if (serverUrlInput) serverUrlInput.value = currentConfig.server_url;
            openModal('appSettingsModal');
        });
    }

    if (saveAppSettingsBtn) {
        saveAppSettingsBtn.addEventListener('click', async () => {
            const newConfig = {
                local_url: localUrlInput ? localUrlInput.value.trim() : '',
                server_url: serverUrlInput ? serverUrlInput.value.trim() : ''
            };
            await window.appConfigManager.saveConfig(newConfig);
            config = newConfig; // Update in-memory config
            await updateButtonLinks();
            showToast('Settings saved!', 'success');
            closeModal('appSettingsModal');
        });
    }

    initialize();
});
```

---

## `static/js/share.js`

```javascript
// --- Share Page Logic (Server-Assisted, Token-Authenticated) ---

document.addEventListener('DOMContentLoaded', async () => {
    // This page is now only for viewing and managing the local file queue.
    // The actual upload happens inside the main application.

    const fileListContainer = document.getElementById('file-list');
    const noFilesMessage = document.getElementById('no-files-message');
    const fileCountSpan = document.getElementById('file-count');
    const clearAllBtn = document.getElementById('clear-all-btn');
    const manualUploadInput = document.getElementById('manualUploadInput');
    const uploadArea = document.getElementById('uploadArea');

    async function renderFileList() {
        if (!window.fileDB) return;
        const files = await window.fileDB.getFiles();
        fileListContainer.innerHTML = '';
        if (files.length === 0) {
            if(noFilesMessage) noFilesMessage.style.display = 'block';
        } else {
            if(noFilesMessage) noFilesMessage.style.display = 'none';
            files.forEach(fileData => {
                const fileCard = document.createElement('div');
                fileCard.className = 'card file-list-item';
                fileCard.innerHTML = `<div class="file-info"><span class="file-name">${fileData.name}</span><span class="file-size">(${(fileData.size / 1024 / 1024).toFixed(2)} MB)</span></div><button class="btn btn-danger btn-sm" data-id="${fileData.id}" title="Remove"><i class="fas fa-times"></i></button>`;
                fileCard.querySelector('button').addEventListener('click', async (e) => {
                    await window.fileDB.deleteFile(parseInt(e.currentTarget.dataset.id, 10));
                    renderFileList();
                });
                fileListContainer.appendChild(fileCard);
            });
        }
        if(fileCountSpan) fileCountSpan.textContent = files.length;
        if (clearAllBtn) clearAllBtn.disabled = files.length === 0;
    }

    async function handleNewFiles(files) {
        if (!files || files.length === 0) return;
        for (const file of files) { await window.fileDB.saveFile(file); }
        showToast(`Saved ${files.length} file(s) locally.`, 'success');
        renderFileList();
    }

    async function fetchAndSaveMyPendingFiles() {
        showToast('Checking for shared files...', 'info');
        try {
            const apiToken = await window.fileDB.getConfigValue('api_token');
            if (!apiToken) {
                // This can happen if the user shares before generating a token.
                // The /share-receiver would have shown a login page.
                showToast('Please log in and generate a token in the main app before sharing.', 'warning');
                return;
            }

            const response = await fetch('/api/get-pending-files', {
                headers: { 'Authorization': `Bearer ${apiToken}` }
            });

            if (!response.ok) {
                throw new Error(`Server responded with ${response.status}`);
            }

            const data = await response.json();
            if (data.ok && data.files && data.files.length > 0) {
                let savedCount = 0;
                for (const fileData of data.files) {
                    const byteString = atob(fileData.data);
                    const ab = new ArrayBuffer(byteString.length);
                    const ia = new Uint8Array(ab);
                    for (let i = 0; i < byteString.length; i++) { ia[i] = byteString.charCodeAt(i); }
                    const blob = new Blob([ab], { type: fileData.mimetype });
                    const file = new File([blob], fileData.name, { type: fileData.mimetype });
                    await window.fileDB.saveFile(file);
                    savedCount++;
                }
                showToast(`${savedCount} shared file(s) have been saved locally.`, 'success');
                renderFileList();
            } else if (data.error) {
                showToast(`Could not retrieve files: ${data.error}`, 'error');
            }
        } catch (error) {
            console.error('Failed to fetch pending files:', error);
            showToast('An error occurred while checking for shared files.', 'error');
        }
    }

    // --- Event Listeners ---
    if (manualUploadInput) manualUploadInput.addEventListener('change', e => { handleNewFiles(e.target.files); e.target.value = ''; });
    if (uploadArea) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(ev => uploadArea.addEventListener(ev, e => { e.preventDefault(); e.stopPropagation(); }));
        uploadArea.addEventListener('dragenter', () => uploadArea.classList.add('dragover'));
        uploadArea.addEventListener('dragleave', () => uploadArea.classList.remove('dragover'));
        uploadArea.addEventListener('drop', e => { uploadArea.classList.remove('dragover'); handleNewFiles(e.dataTransfer.files); });
        uploadArea.addEventListener('click', () => manualUploadInput.click());
    }
    if (clearAllBtn) clearAllBtn.addEventListener('click', async () => {
        if (confirm('Are you sure?')) {
            await window.fileDB.clearFiles();
            renderFileList();
        }
    });

    // --- Init ---
    await window.fileDB.initDB();

    const urlParams = new URLSearchParams(window.location.search);
    const error = urlParams.get('error');
    const success = urlParams.get('success');

    if (error) {
        if (error === 'login_required') {
            showToast('Please log into the main app first, then try sharing again.', 'error');
        } else {
            showToast('An account error occurred. Please log in again.', 'error');
        }
    } else if (success) {
        // If the redirect from the server was successful, we now fetch the files
        fetchAndSaveMyPendingFiles();
    }

    // Always render whatever is currently in the DB
    await renderFileList();

    // Clean up the URL
    history.replaceState(null, '', window.location.pathname);
});

function showToast(message, type = 'info') { const c = document.getElementById('toastContainer'); if (!c) return; const t = document.createElement('div'); t.className = `toast ${type}`; const i = { success: 'fa-check-circle', error: 'fa-times-circle', warning: 'fa-exclamation-triangle', info: 'fa-info-circle' }[type] || 'fa-info-circle'; t.innerHTML = `<i class="fas ${i}"></i><div class="toast-message">${message}</div>`; c.appendChild(t); setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 300); }, 3000); }
```

---

## `static/js/main.js` (Relevant Sections)

```javascript
// ... existing uploadSingleFile function ...
function uploadSingleFile(item, destOverride = null, baseUrl = null){
  const {file, id} = item;
  const container = document.getElementById('progressContainer');
  const row = createProgressElement(file.name, id);
  container?.appendChild(row);

  const form = new FormData();
  form.append('dest', destOverride !== null ? destOverride : (window.currentPath || ''));
  form.append('file', file, file.name);

  const xhr = new XMLHttpRequest();
  activeXHRs.set(id, xhr);

  const start = Date.now();
  xhr.upload.addEventListener('progress', e=>{
    if(e.lengthComputable){
      const percent = (e.loaded/e.total) * 100;
      const seconds = Math.max(0.25, (Date.now()-start)/1000);
      const speed = e.loaded/seconds;
      const eta = (e.total-e.loaded) / Math.max(speed, 1);
      updateProgress(row, {percent, speed, eta});
    }
  });
  xhr.addEventListener('load', ()=>{
    activeXHRs.delete(id);
    try {
      const j = JSON.parse(xhr.responseText || '{}');
      if(xhr.status >= 200 && xhr.status < 300 && j.ok){
        markProgressComplete(row, true);
        showToast(`Uploaded: ${file.name}`, 'success');
      } else {
        markProgressComplete(row, false);
        showToast(`Failed: ${file.name}`, 'error');
      }
    } catch(e){
      if(xhr.status >= 200 && xhr.status < 300){
        markProgressComplete(row, true);
        showToast(`Uploaded: ${file.name}`, 'success');
      } else {
        markProgressComplete(row, false);
        showToast(`Failed: ${file.name}`, 'error');
      }
    }
  });
  xhr.addEventListener('error', ()=>{
    activeXHRs.delete(id);
    markProgressComplete(row, false);
    showToast(`Failed: ${file.name}`, 'error');
  });
  xhr.addEventListener('abort', ()=>{
    activeXHRs.delete(id);
    row.remove();
  });

  const uploadUrl = baseUrl ? new URL('/api/upload', baseUrl).href : URLS.api_upload;
  xhr.open('POST', uploadUrl);
  xhr.send(form);
}

// ...

// --- PENDING SHARE UPLOADS ---
async function uploadPendingFiles(destinationType) {
    // When on the local instance, we get the URLs from the APP_CONFIG object
    // that was populated via the redirect from the launcher.
    const url = destinationType === 'local' ? APP_CONFIG.local_url : APP_CONFIG.remote_server_url;
    const localBtn = document.getElementById('pendingUploadLocalBtn');
    const serverBtn = document.getElementById('pendingUploadServerBtn');
    const dismissBtn = document.getElementById('pendingDismissBtn');

    if (!url) {
        showToast(`Upload failed: ${destinationType} URL is not configured.`, 'error');
        return;
    }

    const pendingFiles = await window.fileDB.getFiles();
    if (pendingFiles.length === 0) return;

    showToast(`Uploading ${pendingFiles.length} shared file(s) to ${destinationType}...`, 'info');
    localBtn.disabled = true;
    serverBtn.disabled = true;
    dismissBtn.disabled = true;

    const container = document.getElementById('progressContainer');
    if(container) container.innerHTML = '';

    let allSucceeded = true;
    for (const fileData of pendingFiles) {
        try {
            // The original uploader uses `window.currentPath`. We must override it
            // to send to the user's root folder, and provide the correct base URL.
            await uploadSingleFile({ file: fileData.file, id: `pending-${fileData.id}` }, '', url);
        } catch (e) {
            allSucceeded = false;
            showToast(`Upload failed for ${fileData.name}.`, 'error');
            break;
        }
    }

    if (allSucceeded) {
        await window.fileDB.clearFiles();
        showToast('All pending files uploaded successfully!', 'success');
        document.getElementById('pendingUploadBanner').style.display = 'none';
    } else {
        showToast('Some files could not be uploaded. Please try again.', 'warning');
    }

    localBtn.disabled = false;
    serverBtn.disabled = false;
    dismissBtn.disabled = false;
    checkForPendingShares();
}

async function checkForPendingShares() {
    if (!window.fileDB) { return; }
    await window.fileDB.initDB();

    // If this page was loaded with remote details, it means we are the "local"
    // instance and need to fetch the pending file list from the remote server.
    if (APP_CONFIG.remote_server_url && APP_CONFIG.remote_api_token) {
        showToast('Checking for remotely shared files...', 'info');
        try {
            const response = await fetch(new URL('/api/get-pending-files', APP_CONFIG.remote_server_url).href, {
                headers: { 'Authorization': `Bearer ${APP_CONFIG.remote_api_token}` }
            });
            const data = await response.json();
            if (data.ok && data.files && data.files.length > 0) {
                showToast(`Found ${data.files.length} remote files. Saving locally...`, 'success');
                for (const fileData of data.files) {
                    const byteString = atob(fileData.data);
                    const ab = new ArrayBuffer(byteString.length);
                    const ia = new Uint8Array(ab);
                    for (let i = 0; i < byteString.length; i++) { ia[i] = byteString.charCodeAt(i); }
                    const blob = new Blob([ab], { type: fileData.mimetype });
                    const file = new File([blob], fileData.name, { type: fileData.mimetype });
                    await window.fileDB.saveFile(file);
                }
            }
        } catch (e) {
            showToast('Failed to sync remote files.', 'error');
            console.error('Remote sync failed:', e);
        }
    }

    const pendingFiles = await window.fileDB.getFiles();

    const banner = document.getElementById('pendingUploadBanner');
    const bannerText = document.getElementById('pendingUploadText');
    const localBtn = document.getElementById('pendingUploadLocalBtn');
    const serverBtn = document.getElementById('pendingUploadServerBtn');
    const dismissBtn = document.getElementById('pendingDismissBtn');

    if (!banner || !bannerText || !localBtn || !serverBtn || !dismissBtn) return;

    if (pendingFiles.length > 0) {
        bannerText.textContent = `You have ${pendingFiles.length} file(s) ready to upload.`;
        banner.style.display = 'flex';

        localBtn.onclick = () => uploadPendingFiles('local');
        serverBtn.onclick = () => uploadPendingFiles('server');
        dismissBtn.onclick = () => { banner.style.display = 'none'; };
    } else {
        banner.style.display = 'none';
    }
}
```

---

## `templates/base.html` (Relevant Sections)

```html
<!-- Pending Share Upload Banner -->
<div class="pending-upload-banner" id="pendingUploadBanner" style="display: none;">
<div class="pending-upload-content">
    <i class="fas fa-inbox"></i>
    <span id="pendingUploadText">You have pending files to upload.</span>
    <div class="pending-upload-actions">
    <button class="btn btn-success" id="pendingUploadLocalBtn"><i class="fas fa-network-wired"></i> To Local</button>
    <button class="btn btn-primary" id="pendingUploadServerBtn"><i class="fas fa-server"></i> To Server</button>
    <button class="btn btn-secondary" id="pendingDismissBtn">Later</button>
    </div>
</div>
</div>

<script>
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/static/sw-v2.js').then(registration => {
        console.log('ServiceWorker v2 registration successful with scope: ', registration.scope);
      }, err => {
        console.log('ServiceWorker v2 registration failed: ', err);
      });
    });
  }
</script>
<link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}?v=final">

<script>
  const APP_CONFIG = {
    current_rel: "{{ current_rel|default('', true) }}",
    current_folder: {{ session.get('folder', '')|tojson|default('""') }},
    dhikr_list: {{ dhikr_list|tojson|default('[]') }},
    remote_server_url: "{{ request.args.get('remote_server_url') or '' }}",
    remote_api_token: "{{ request.args.get('remote_api_token') or '' }}",
    local_url: "{{ request.args.get('local_url') or '' }}"
  };
</script>
<script src="{{ url_for('static', filename='js/db.js') }}?v=final"></script>
<script src="{{ url_for('static', filename='js/config.js') }}?v=final"></script>
<script src="{{ url_for('static', filename='js/main.js') }}?v=final"></script>
```

---

## `app.py` (Relevant Sections)

```python
# In-memory store for pending shared files
pending_file_shares: dict[str, list] = {}

# ...

@app.route("/share-receiver", methods=["POST"])
def share_receiver():
    # This endpoint is hit from the online origin. It needs to know which user
    # this share belongs to. It uses the existing session cookie for that.
    if not is_authed():
        # If user isn't logged into the main app, we can't associate the share.
        # Redirect to the share page with an error flag.
        return redirect(url_for("static", filename="share.html", error="login_required"))

    user_folder = session.get("folder")
    if not user_folder:
        # This case should not happen if is_authed() is true, but as a fallback:
        return redirect(url_for("static", filename="share.html", error="account_error"))

    files = request.files.getlist("files")
    if not files or not any(f.filename for f in files):
        return redirect(url_for("static", filename="share.html"))

    # Store files in memory as base64 encoded strings, keyed by the user's folder
    stored_files = pending_file_shares.get(user_folder, [])
    for f in files:
        if f and f.filename:
            try:
                file_bytes = f.read()
                b64_encoded = base64.b64encode(file_bytes).decode('utf-8')
                stored_files.append({
                    "name": f.filename,
                    "mimetype": f.mimetype or "application/octet-stream",
                    "data": b64_encoded
                })
            except Exception as e:
                print(f"[share-receiver] Failed to read or encode file {f.filename}: {e}")

    if not stored_files:
         return redirect(url_for("static", filename="share.html"))

    pending_file_shares[user_folder] = stored_files

    # Redirect to the static share page. The JS on that page will fetch the files.
    return redirect(url_for("static", filename="share.html", success="true"))

@app.route("/api/get-pending-files")
def api_get_pending_files():
    # This endpoint is now authenticated by the API token of the user making the request
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"ok": False, "error": "Missing auth token"}), 401

    token = auth_header.split(" ", 1)[1]
    user = get_user_by_token(token)
    if not user:
        return jsonify({"ok": False, "error": "Invalid auth token"}), 401

    user_folder = user.get("folder")

    # Pop the files from memory for this user. This is a one-time retrieval.
    files_data = pending_file_shares.pop(user_folder, None)

    if files_data is None:
        # It's not an error to have no pending files. Return an empty list.
        return jsonify({"ok": True, "files": []})

    return jsonify({"ok": True, "files": files_data})

@app.route('/login_and_sync')
def login_and_sync():
    # This special login route is for the local server instance.
    # It receives the API token for login and the remote server's details
    # so it can fetch pending files from the remote origin's queue.
    api_token = request.args.get('token')
    remote_server_url = request.args.get('remote_server_url')
    local_url = request.args.get('local_url')

    user = get_user_by_token(api_token)
    if not user:
        return redirect(url_for("login", error="Invalid token provided for sync."))

    # Log the user in and set up the session for this origin
    session["authed"] = True
    session["folder"] = user.get("folder")
    session["icon"] = user.get("icon") or get_user_icon(user.get("folder"))

    # Redirect to the main browse page, passing the remote details along
    # The browse page template will then pick these up and pass to main.js
    return redirect(url_for("browse",
                            subpath=session.get("folder", ""),
                            remote_server_url=remote_server_url,
                            remote_api_token=api_token,
                            local_url=local_url))
```

---

## `site.webmanifest`

```json
{
  "name": "FileVault",
  "short_name": "FileVault",
  "scope": "/",
  "start_url": "/static/launcher.html",
  "display": "standalone",
  "background_color": "#ffe6f2",
  "theme_color": "#ff4fa3",
  "icons": [
    {
      "src": "/static/favicon.svg",
      "sizes": "any",
      "type": "image/svg+xml"
    }
  ],
  "share_target": {
    "action": "/share-receiver",
    "method": "POST",
    "enctype": "multipart/form-data",
    "params": {
      "files": [
        {
          "name": "files",
          "accept": ["*/*"]
        }
      ]
    }
  }
}
```

---

## `requirements.txt`

```
Flask
Flask-SocketIO
requests
qrcode
gunicorn
eventlet
Pillow
Flask-Cors
pyOpenSSL
```
