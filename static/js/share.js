// --- Share Page Logic (Raw Upload) ---

document.addEventListener('DOMContentLoaded', async () => {
    // Load config and DB on start
    await window.appConfigManager.loadConfig();
    await window.fileDB.initDB();

    const fileListContainer = document.getElementById('file-list');
    const noFilesMessage = document.getElementById('no-files-message');
    const fileCountSpan = document.getElementById('file-count');
    const sendLocalBtn = document.getElementById('send-local-btn');
    const sendServerBtn = document.getElementById('send-server-btn');
    const clearAllBtn = document.getElementById('clear-all-btn');
    const manualUploadInput = document.getElementById('manualUploadInput');
    const uploadArea = document.getElementById('uploadArea');
    const progressContainer = document.getElementById('progress-container');

    async function renderFileList() {
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
        const hasFiles = files.length > 0;
        if(sendLocalBtn) sendLocalBtn.disabled = !hasFiles;
        if(sendServerBtn) sendServerBtn.disabled = !hasFiles;
        if(clearAllBtn) clearAllBtn.disabled = !hasFiles;
    }

    async function handleNewFiles(files) {
        if (!files || files.length === 0) return;
        for (const file of files) { await window.fileDB.saveFile(file); }
        showToast(`Saved ${files.length} file(s) locally.`, 'success');
        renderFileList();
    }

    async function uploadSingleFileRaw(item, baseUrl, apiToken) {
        const { id, file } = item;
        const row = createProgressElement(file.name, `up-${id}`);
        if(progressContainer) progressContainer.appendChild(row);

        const fileBuffer = await file.arrayBuffer();

        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            const uploadUrl = new URL('/api/upload', baseUrl).href;
            xhr.open('POST', uploadUrl, true);
            xhr.setRequestHeader('Content-Type', 'application/octet-stream');
            xhr.setRequestHeader('X-File-Name', file.name);
            xhr.setRequestHeader('Authorization', `Bearer ${apiToken}`);

            xhr.upload.addEventListener('progress', e => {
                if (e.lengthComputable) {
                    const percent = (e.loaded / e.total) * 100;
                    updateProgress(row, { percent });
                }
            });

            xhr.onload = () => {
                if (xhr.status >= 200 && xhr.status < 300) {
                    markProgressComplete(row, true);
                    resolve({ success: true });
                } else {
                    const errorMsg = JSON.parse(xhr.responseText || '{}').error || `HTTP ${xhr.status}`;
                    markProgressComplete(row, false);
                    reject(new Error(errorMsg));
                }
            };
            xhr.onerror = () => {
                markProgressComplete(row, false);
                reject(new Error('Network Error'));
            };
            xhr.send(fileBuffer);
        });
    }

    async function startUpload(destinationType) {
        const config = window.appConfigManager.getConfig();
        const url = destinationType === 'local' ? config.local_url : config.server_url;
        const apiToken = await window.fileDB.getConfigValue('api_token');

        if (!url) return showToast(`'${destinationType}' URL not configured.`, 'error');
        if (!apiToken) return showToast('API Token not set up.', 'error');

        const filesToUpload = await window.fileDB.getFiles();
        if (filesToUpload.length === 0) return;

        sendLocalBtn.disabled = true;
        sendServerBtn.disabled = true;
        clearAllBtn.disabled = true;

        let allSucceeded = true;
        for (const fileData of filesToUpload) {
            try {
                await uploadSingleFileRaw({ id: fileData.id, file: fileData.file }, url, apiToken);
            } catch (e) {
                allSucceeded = false;
                showToast(`Upload failed for ${fileData.name}: ${e.message}`, 'error');
                break;
            }
        }

        if (allSucceeded) {
            await window.fileDB.clearFiles();
            showToast('All files uploaded successfully!', 'success');
        }
        await renderFileList();
    }

    // Event Listeners
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
    if (sendLocalBtn) sendLocalBtn.addEventListener('click', () => startUpload('local'));
    if (sendServerBtn) sendServerBtn.addEventListener('click', () => startUpload('server'));

    // Initial Load & Server-Assisted Queuing
    const urlParams = new URLSearchParams(window.location.search);
    const pendingId = urlParams.get('pending_id');
    if (pendingId) {
        showToast('Shared files received. Saving locally...', 'info');
        fetchAndSavePendingFiles(pendingId);
        history.replaceState(null, '', window.location.pathname);
    } else {
        renderFileList();
    }
});

async function fetchAndSavePendingFiles(pendingId) {
    try {
        const response = await fetch(`/api/get-pending-files?id=${pendingId}`);
        const data = await response.json();
        if (data.ok && data.files) {
            for (const fileData of data.files) {
                const byteString = atob(fileData.data);
                const ab = new ArrayBuffer(byteString.length);
                const ia = new Uint8Array(ab);
                for (let i = 0; i < byteString.length; i++) { ia[i] = byteString.charCodeAt(i); }
                const blob = new Blob([ab], { type: fileData.mimetype });
                const file = new File([blob], fileData.name, { type: fileData.mimetype });
                await window.fileDB.saveFile(file);
            }
            showToast(`${data.files.length} file(s) saved locally.`, 'success');
            document.location.reload(); // Easiest way to refresh the list
        } else {
            showToast(data.error || 'Could not retrieve shared files.', 'error');
        }
    } catch (error) {
        showToast('Error fetching shared files.', 'error');
    }
}

// UI helper functions
function createProgressElement(filename, id) { const div = document.createElement('div'); div.className = 'progress-item'; div.dataset.uploadId = id; div.innerHTML = `<div class="progress-header"><div class="progress-filename">${filename}</div><span class="progress-percent">0%</span></div><div class="progress-bar"><div class="progress-fill" style="width:0%"></div></div>`; return div; }
function updateProgress(element, data) { if (!element) return; element.querySelector('.progress-fill').style.width = `${data.percent}%`; element.querySelector('.progress-percent').textContent = `${Math.round(data.percent)}%`; }
function markProgressComplete(element, success) { if (!element) return; element.classList.add(success ? 'completed' : 'error'); setTimeout(() => { element.style.opacity = '0'; setTimeout(() => element.remove(), 300); }, 1500); }
function showToast(message, type = 'info') { const c = document.getElementById('toastContainer'); if (!c) return; const t = document.createElement('div'); t.className = `toast ${type}`; const i = { success: 'fa-check-circle', error: 'fa-times-circle', warning: 'fa-exclamation-triangle', info: 'fa-info-circle' }[type] || 'fa-info-circle'; t.innerHTML = `<i class="fas ${i}"></i><div class="toast-message">${message}</div>`; c.appendChild(t); setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 300); }, 3000); }
