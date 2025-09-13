// --- Main Application Logic ---

document.addEventListener('DOMContentLoaded', () => {
    // This part runs on BOTH index.html and share.html

    // Register the service worker
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/service-worker.js')
            .then((registration) => {
                console.log('Service Worker registered with scope:', registration.scope);
            }).catch((error) => {
                console.error('Service Worker registration failed:', error);
            });
    }

    // --- Logic for index.html ---
    if (document.getElementById('setup-modal')) {
        const mainContent = document.getElementById('main-content');
        const setupModal = document.getElementById('setup-modal');
        const setupForm = document.getElementById('setup-form');
        const settingsBtn = document.getElementById('settings-btn');

        const localIpInput = document.getElementById('local-ip');
        const serverUrlInput = document.getElementById('server-url');

        function showMainContent(localIp, serverUrl) {
            mainContent.innerHTML = `
                <div class="button-container">
                    <a href="${localIp}" class="action-btn">Go to Local</a>
                    <a href="${serverUrl}" class="action-btn">Go to Server</a>
                </div>
            `;
        }

        function showSetupModal() {
            const localIp = localStorage.getItem('localIp') || '';
            const serverUrl = localStorage.getItem('serverUrl') || '';
            localIpInput.value = localIp;
            serverUrlInput.value = serverUrl;
            setupModal.hidden = false;
        }

        setupForm.addEventListener('submit', (event) => {
            event.preventDefault();
            const localIp = localIpInput.value.trim();
            const serverUrl = serverUrlInput.value.trim();

            if (localIp && serverUrl) {
                localStorage.setItem('localIp', localIp);
                localStorage.setItem('serverUrl', serverUrl);
                setupModal.hidden = true;
                showMainContent(localIp, serverUrl);
            }
        });

        settingsBtn.addEventListener('click', () => {
            showSetupModal();
        });

        const savedLocalIp = localStorage.getItem('localIp');
        const savedServerUrl = localStorage.getItem('serverUrl');

        if (savedLocalIp && savedServerUrl) {
            showMainContent(savedLocalIp, savedServerUrl);
        } else {
            showSetupModal();
        }
    }


    // --- Logic for share.html ---
    if (window.location.pathname.endsWith('share.html')) {
        const fileList = document.getElementById('file-list');
        const noFilesMessage = document.getElementById('no-files-message');
        const statusMessage = document.getElementById('status-message');
        const sendLocalBtn = document.getElementById('send-local-btn');
        const sendServerBtn = document.getElementById('send-server-btn');
        const clearAllBtn = document.getElementById('clear-all-btn');

        const DB_NAME = 'PWAUploaderDB';
        const DB_VERSION = 1;
        const STORE_NAME = 'files';

        function openDB() {
            return new Promise((resolve, reject) => {
                const request = indexedDB.open(DB_NAME, DB_VERSION);
                request.onerror = () => reject("Error opening DB");
                request.onsuccess = () => resolve(request.result);
                request.onupgradeneeded = (event) => {
                    const db = event.target.result;
                    db.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true });
                };
            });
        }

        async function getAllFiles() {
            const db = await openDB();
            return new Promise((resolve) => {
                const transaction = db.transaction(STORE_NAME, 'readonly');
                const store = transaction.objectStore(STORE_NAME);
                const request = store.getAll();
                request.onsuccess = () => resolve(request.result);
                transaction.oncomplete = () => db.close();
            });
        }

        async function deleteFileById(id) {
            const db = await openDB();
            return new Promise((resolve) => {
                const transaction = db.transaction(STORE_NAME, 'readwrite');
                const store = transaction.objectStore(STORE_NAME);
                store.delete(id);
                transaction.oncomplete = () => {
                    db.close();
                    resolve();
                };
            });
        }

        async function clearAllFiles() {
            const db = await openDB();
            return new Promise((resolve) => {
                const transaction = db.transaction(STORE_NAME, 'readwrite');
                const store = transaction.objectStore(STORE_NAME);
                store.clear();
                transaction.oncomplete = () => {
                    db.close();
                    resolve();
                };
            });
        }

        function formatBytes(bytes) {
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }

        async function displayFiles() {
            const files = await getAllFiles();
            fileList.innerHTML = '';
            if (files.length === 0) {
                noFilesMessage.hidden = false;
                sendLocalBtn.disabled = true;
                sendServerBtn.disabled = true;
                clearAllBtn.disabled = true;
            } else {
                noFilesMessage.hidden = true;
                sendLocalBtn.disabled = false;
                sendServerBtn.disabled = false;
                clearAllBtn.disabled = false;
                files.forEach(fileData => {
                    const li = document.createElement('li');
                    li.dataset.id = fileData.id;
                    li.innerHTML = `
                        <span class="file-info">
                            ${fileData.name}
                            <span class="file-size">(${formatBytes(fileData.size)})</span>
                        </span>
                        <button class="remove-file-btn" title="Remove file">&times;</button>
                    `;
                    fileList.appendChild(li);
                });
            }
        }

        async function uploadFiles(targetUrl) {
            const files = await getAllFiles();
            if (files.length === 0) {
                statusMessage.textContent = 'No files to upload.';
                return;
            }
            if (!targetUrl || targetUrl === 'null') {
                statusMessage.textContent = 'Upload URL is not configured. Please set it on the home page.';
                statusMessage.style.color = 'red';
                return;
            }

            statusMessage.textContent = `Uploading ${files.length} file(s)...`;
            statusMessage.style.color = 'inherit';

            const formData = new FormData();
            files.forEach(fileData => {
                formData.append('files', fileData.file, fileData.name);
            });

            try {
                // We assume the target server has an /upload endpoint
                const response = await fetch(`${targetUrl}/upload`, {
                    method: 'POST',
                    body: formData,
                });

                if (response.ok) {
                    statusMessage.textContent = 'Upload successful!';
                    statusMessage.style.color = 'green';
                    await clearAllFiles();
                    await displayFiles();
                } else {
                    const errorText = await response.text();
                    throw new Error(`Server responded with ${response.status}: ${errorText}`);
                }
            } catch (error) {
                statusMessage.textContent = `Upload failed: ${error.message}`;
                statusMessage.style.color = 'red';
                console.error('Upload error:', error);
            }
        }

        sendLocalBtn.addEventListener('click', () => {
            const localIp = localStorage.getItem('localIp');
            uploadFiles(localIp);
        });

        sendServerBtn.addEventListener('click', () => {
            const serverUrl = localStorage.getItem('serverUrl');
            uploadFiles(serverUrl);
        });

        clearAllBtn.addEventListener('click', async () => {
            if (confirm('Are you sure you want to clear all pending files?')) {
                await clearAllFiles();
                await displayFiles();
                statusMessage.textContent = 'All files cleared.';
            }
        });

        fileList.addEventListener('click', async (event) => {
            if (event.target.classList.contains('remove-file-btn')) {
                const li = event.target.closest('li');
                const fileId = parseInt(li.dataset.id, 10);
                await deleteFileById(fileId);
                await displayFiles();
                statusMessage.textContent = `File removed.`;
            }
        });

        displayFiles();
    }
});
