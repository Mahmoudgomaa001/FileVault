// --- Share Page Logic (Simplified) ---

document.addEventListener('DOMContentLoaded', async () => {
    // This page is now only for viewing and managing the local file queue.
    // The actual upload happens inside the main application.

    const fileListContainer = document.getElementById('file-list');
    const noFilesMessage = document.getElementById('no-files-message');
    const fileCountSpan = document.getElementById('file-count');
    const clearAllBtn = document.getElementById('clear-all-btn');
    const manualUploadInput = document.getElementById('manualUploadInput');
    const uploadArea = document.getElementById('uploadArea');

    /**
     * Renders the list of files from IndexedDB into the UI.
     */
    async function renderFileList(files) {
        if (!window.fileDB) return;
        // Allow passing files directly to prevent re-querying the DB
        const filesToRender = files || await window.fileDB.getFiles();
        fileListContainer.innerHTML = ''; // Clear existing list

        if (filesToRender.length === 0) {
            if (noFilesMessage) noFilesMessage.style.display = 'block';
            fileListContainer.appendChild(noFilesMessage);
        } else {
            if (noFilesMessage) noFilesMessage.style.display = 'none';
            filesToRender.forEach(fileData => {
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

        if(fileCountSpan) fileCountSpan.textContent = filesToRender.length;
        if (clearAllBtn) clearAllBtn.disabled = filesToRender.length === 0;
    }

    /**
     * Handles new files from either manual upload or Web Share.
     */
    async function handleNewFiles(files) {
        if (!files || files.length === 0) return;
        showToast(`Adding ${files.length} file(s) to the local queue...`, 'info');
        for (const file of files) {
            await window.fileDB.saveFile(file);
        }
        showToast('Files are saved locally and ready to upload from the main app.', 'success');
        renderFileList();
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
        if (confirm('Are you sure you want to clear all pending files? This cannot be undone.')) {
            await window.fileDB.clearFiles();
            renderFileList();
            showToast('All pending files have been cleared.', 'success');
        }
    });

    // --- Init ---
    if (window.fileDB) {
        await window.fileDB.initDB();
        const files = await window.fileDB.getFiles();
        showToast(`DEBUG: Share page loaded, found ${files.length} files in DB.`, 'info');
        await renderFileList(files); // Pass files to avoid re-querying
    }

    if (window.appConfigManager) {
        const config = await window.appConfigManager.loadConfig();
        const openAppBtn = document.getElementById('open-app-btn');
        if (openAppBtn && config.local_url) {
            openAppBtn.href = config.local_url;
        } else if (openAppBtn && config.server_url) {
            // Fallback to server url if local isn't set
            openAppBtn.href = config.server_url;
        } else if(openAppBtn) {
            // If no urls, point back to launcher
            openAppBtn.href = '/static/launcher.html';
            openAppBtn.textContent = 'Open Launcher to Configure';
        }
    }

    // --- New logic to handle server-assisted file queuing ---
    const urlParams = new URLSearchParams(window.location.search);
    const pendingId = urlParams.get('pending_id');

    if (pendingId) {
        showToast('Shared files received. Saving locally...', 'info');
        fetchAndSavePendingFiles(pendingId);
        // Clean up the URL
        history.replaceState(null, '', window.location.pathname);
    }
});

async function fetchAndSavePendingFiles(pendingId) {
    try {
        const response = await fetch(`/api/get-pending-files?id=${pendingId}`);
        const data = await response.json();

        if (data.ok && data.files && data.files.length > 0) {
            let savedCount = 0;
            for (const fileData of data.files) {
                // Convert base64 back to a Blob, then to a File
                const byteString = atob(fileData.data);
                const ab = new ArrayBuffer(byteString.length);
                const ia = new Uint8Array(ab);
                for (let i = 0; i < byteString.length; i++) {
                    ia[i] = byteString.charCodeAt(i);
                }
                const blob = new Blob([ab], { type: fileData.mimetype });
                const file = new File([blob], fileData.name, { type: fileData.mimetype });

                await window.fileDB.saveFile(file);
                savedCount++;
            }
            showToast(`${savedCount} file(s) successfully saved locally.`, 'success');
            // Refresh the file list in the UI
            document.dispatchEvent(new Event('DOMContentLoaded'));
        } else {
            showToast(data.error || 'Could not retrieve shared files.', 'error');
        }
    } catch (error) {
        console.error('Failed to fetch pending files:', error);
        showToast('An error occurred while fetching shared files.', 'error');
    }
}

function showToast(message, type = 'info') { const c = document.getElementById('toastContainer'); if (!c) return; const t = document.createElement('div'); t.className = `toast ${type}`; const i = { success: 'fa-check-circle', error: 'fa-times-circle', warning: 'fa-exclamation-triangle', info: 'fa-info-circle' }[type] || 'fa-info-circle'; t.innerHTML = `<i class="fas ${i}"></i><div class="toast-message">${message}</div>`; c.appendChild(t); setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 300); }, 3000); }
