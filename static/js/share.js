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
    async function renderFileList() {
        if (!window.fileDB) return;
        const files = await window.fileDB.getFiles();
        fileListContainer.innerHTML = ''; // Clear existing list

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
        if (clearAllBtn) clearAllBtn.disabled = files.length === 0;
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
        await renderFileList();
    }

    // Diagnostic code for share target
    const urlParams = new URLSearchParams(window.location.search);
    const savedCount = urlParams.get('saved');
    if (savedCount) {
        if (savedCount === 'error') {
            showToast('Service worker encountered an error saving files.', 'error');
        } else {
            showToast(`${savedCount} file(s) received and saved locally.`, 'info');
        }
        history.replaceState(null, '', window.location.pathname);
    }
});

function showToast(message, type = 'info') { const c = document.getElementById('toastContainer'); if (!c) return; const t = document.createElement('div'); t.className = `toast ${type}`; const i = { success: 'fa-check-circle', error: 'fa-times-circle', warning: 'fa-exclamation-triangle', info: 'fa-info-circle' }[type] || 'fa-info-circle'; t.innerHTML = `<i class="fas ${i}"></i><div class="toast-message">${message}</div>`; c.appendChild(t); setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 300); }, 3000); }
