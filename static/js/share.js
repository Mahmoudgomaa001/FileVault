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
