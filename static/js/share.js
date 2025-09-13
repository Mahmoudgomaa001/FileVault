// --- Share Page Logic ---

document.addEventListener('DOMContentLoaded', async () => {
    // Ensure config is loaded before we do anything else
    if (window.appConfigManager) {
        await window.appConfigManager.loadConfig();
    }

    const fileListContainer = document.getElementById('file-list');
    const noFilesMessage = document.getElementById('no-files-message');
    const fileCountSpan = document.getElementById('file-count');
    const sendLocalBtn = document.getElementById('send-local-btn');
    const sendServerBtn = document.getElementById('send-server-btn');
    const clearAllBtn = document.getElementById('clear-all-btn');
    const manualUploadInput = document.getElementById('manualUploadInput');
    const uploadArea = document.getElementById('uploadArea');
    const progressContainer = document.getElementById('progress-container');

    let activeXHRs = new Map();

    /**
     * Renders the list of files from IndexedDB into the UI.
     */
    async function renderFileList() {
        const files = await window.fileDB.getFiles();
        fileListContainer.innerHTML = '';

        if (files.length === 0) {
            if (noFilesMessage) noFilesMessage.style.display = 'block';
            fileListContainer.appendChild(noFilesMessage);
        } else {
            if (noFilesMessage) noFilesMessage.style.display = 'none';
            files.forEach(fileData => {
                const fileCard = document.createElement('div');
                fileCard.className = 'card file-list-item';
                fileCard.innerHTML = `
                    <div class="file-info">
                        <span class="file-name">${fileData.name}</span>
                        <span class="file-size">(${(fileData.size / 1024 / 1024).toFixed(2)} MB)</span>
                    </div>
                    <button class="btn btn-danger btn-sm" data-id="${fileData.id}" title="Remove from queue"><i class="fas fa-times"></i></button>
                `;
                fileCard.querySelector('button').addEventListener('click', async (e) => {
                    e.stopPropagation();
                    const id = parseInt(e.currentTarget.dataset.id, 10);
                    await window.fileDB.deleteFile(id);
                    showToast('File removed from queue.', 'info');
                    renderFileList();
                });
                fileListContainer.appendChild(fileCard);
            });
        }

        if(fileCountSpan) fileCountSpan.textContent = files.length;
        const hasFiles = files.length > 0;
        if (sendLocalBtn) sendLocalBtn.disabled = !hasFiles;
        if (sendServerBtn) sendServerBtn.disabled = !hasFiles;
        if (clearAllBtn) clearAllBtn.disabled = !hasFiles;
    }

    /**
     * Handles new files from either manual upload or Web Share.
     */
    async function handleNewFiles(files) {
        if (!files || files.length === 0) return;
        showToast(`Adding ${files.length} file(s) to the queue...`, 'info');
        for (const file of files) {
            await window.fileDB.saveFile(file);
        }
        showToast('Files are saved locally and ready to send.', 'success');
        renderFileList();
    }

    /**
     * Uploader logic adapted from main.js
     */
    function uploadSingleFile(item, baseUrl) {
        const { id, file } = item;
        const uploadId = `up-${id}`;

        const row = createProgressElement(file.name, uploadId);
        if(progressContainer) progressContainer.appendChild(row);

        const form = new FormData();
        // The destination on the server is the root of the user's folder
        const dest = (APP_CONFIG.current_folder || '');
        form.append('dest', dest);
        form.append('file', file, file.name);

        const xhr = new XMLHttpRequest();
        activeXHRs.set(uploadId, xhr);

        const start = Date.now();
        xhr.upload.addEventListener('progress', e => {
            if (e.lengthComputable) {
                const percent = (e.loaded / e.total) * 100;
                const seconds = Math.max(0.25, (Date.now() - start) / 1000);
                const speed = e.loaded / seconds;
                const eta = (e.total - e.loaded) / Math.max(speed, 1);
                updateProgress(row, { percent, speed, eta });
            }
        });

        return new Promise((resolve, reject) => {
            xhr.addEventListener('load', () => {
                activeXHRs.delete(uploadId);
                try {
                    if (xhr.status >= 200 && xhr.status < 300) {
                        markProgressComplete(row, true);
                        resolve({ success: true, id });
                    } else {
                        const j = JSON.parse(xhr.responseText || '{}');
                        markProgressComplete(row, false);
                        showToast(`Upload failed for ${file.name}: ${j.error || 'Unknown error'}`, 'error');
                        reject({ success: false, error: j.error || `HTTP ${xhr.status}` });
                    }
                } catch (e) {
                    markProgressComplete(row, false);
                    showToast(`Upload failed for ${file.name}`, 'error');
                    reject({ success: false, error: 'Parse error' });
                }
            });
            xhr.addEventListener('error', () => {
                activeXHRs.delete(uploadId);
                markProgressComplete(row, false);
                showToast(`Network error during upload of ${file.name}`, 'error');
                reject({ success: false, error: 'Network error' });
            });
            xhr.addEventListener('abort', () => {
                activeXHRs.delete(uploadId);
                row.remove();
                reject({ success: false, error: 'Aborted' });
            });

            // Construct the full URL for the upload
            const uploadUrl = new URL(URLS.api_upload, baseUrl).href;
            xhr.open('POST', uploadUrl);
            // We need to make sure auth context is sent if the server uses cookies
            xhr.withCredentials = true;
            xhr.send(form);
        });
    }

    async function startUpload(destinationType) {
        const config = window.appConfigManager.getConfig();
        const url = destinationType === 'local' ? config.local_url : config.server_url;
        const btn = destinationType === 'local' ? sendLocalBtn : sendServerBtn;

        if (!url) {
            showToast(`${destinationType === 'local' ? 'Local' : 'Server'} URL is not configured.`, 'error');
            return;
        }

        const filesToUpload = await window.fileDB.getFiles();
        if (filesToUpload.length === 0) return;

        if(btn) btn.disabled = true;
        if(progressContainer) progressContainer.innerHTML = '';

        let successfulUploads = 0;
        for (const fileData of filesToUpload) {
            try {
                // The object from DB has {id, name, size, file}
                await uploadSingleFile({id: fileData.id, file: fileData.file}, url);
                successfulUploads++;
            } catch (uploadError) {
                console.error('An upload failed, stopping queue.', uploadError);
                showToast('An error occurred. Some files were not uploaded.', 'error');
                break; // Stop on first error
            }
        }

        // Clear only if all files were uploaded successfully
        if (successfulUploads === filesToUpload.length) {
            showToast('All files uploaded successfully!', 'success');
            await window.fileDB.clearFiles();
        } else {
            showToast(`${successfulUploads} of ${filesToUpload.length} files uploaded. Please try again.`, 'warning');
        }

        renderFileList(); // Re-render the list (will be empty if all succeeded)
        if(btn) btn.disabled = false;
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
        if (confirm('Are you sure you want to clear all pending files?')) {
            await window.fileDB.clearFiles();
            renderFileList();
            showToast('All pending files have been cleared.', 'success');
        }
    });
    if (sendLocalBtn) sendLocalBtn.addEventListener('click', () => startUpload('local'));
    if (sendServerBtn) sendServerBtn.addEventListener('click', () => startUpload('server'));

    // --- Init ---
    await window.fileDB.initDB();
    await renderFileList();
});

// --- Progress UI (copied from main.js and adapted) ---
function createProgressElement(filename, id) {
    const div = document.createElement('div');
    div.className = 'progress-item';
    div.dataset.uploadId = id;
    div.innerHTML = `<div class="progress-header"><div class="progress-info"><div class="progress-filename">${filename}</div><div class="progress-stats"><span class="stat-speed">0 B/s</span><span class="stat-eta">Starting…</span></div></div><div class="progress-actions"><span class="progress-percent">0%</span></div></div><div class="progress-bar"><div class="progress-fill" style="width:0%"></div></div>`;
    return div;
}
function formatSpeed(bps) { if (!bps || !isFinite(bps)) return "0 B/s"; const u = ['B/s', 'KB/s', 'MB/s', 'GB/s']; let i = 0, s = bps; while (s >= 1024 && i < u.length - 1) { s /= 1024; i++; } return `${s.toFixed(i ? 1 : 0)} ${u[i]}`; }
function formatETA(sec) { if (!isFinite(sec) || sec <= 0) return '...'; if (sec < 60) return `${Math.round(sec)}s`; const m = Math.floor(sec / 60), s = Math.round(sec % 60); return `${m}m ${s}s`; }
function updateProgress(element, data) { if (!element) return; element.querySelector('.progress-fill').style.width = `${data.percent}%`; element.querySelector('.progress-percent').textContent = `${Math.round(data.percent)}%`; element.querySelector('.stat-speed').textContent = formatSpeed(data.speed); element.querySelector('.stat-eta').textContent = data.percent >= 100 ? 'Done' : formatETA(data.eta); }
function markProgressComplete(element, success) { if (!element) return; element.classList.add(success ? 'completed' : 'error'); setTimeout(() => { element.style.opacity = '0'; setTimeout(() => element.remove(), 300); }, 1500); }
function showToast(message, type = 'info') { const c = document.getElementById('toastContainer'); if (!c) return; const t = document.createElement('div'); t.className = `toast ${type}`; const i = { success: 'fa-check-circle', error: 'fa-times-circle', warning: 'fa-exclamation-triangle', info: 'fa-info-circle' }[type] || 'fa-info-circle'; t.innerHTML = `<i class="fas ${i}"></i><div class="toast-message">${message}</div>`; c.appendChild(t); setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 300); }, 3000); }
