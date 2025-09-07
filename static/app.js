'use strict';

const App = {
    // --- STATE ---
    state: {
        isAuthed: false,
        user: null,
        currentPath: '',
        files: [],
        stats: {},
        isLoading: true,
        toast: { message: '', type: '', visible: false },
        login: {
            token: null,
            qr_b64: null,
            isPolling: false,
        },
        sharedFiles: [],
    },

    // --- DOM Elements ---
    el: null, // Main app container

    // --- API HELPERS ---
    async api(url, options = {}) {
        try {
            const response = await fetch(url, options);
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ error: `HTTP error! Status: ${response.status}` }));
                throw new Error(errorData.error || `HTTP error! Status: ${response.status}`);
            }
            if (response.status === 204) return null; // No Content
            return await response.json();
        } catch (error) {
            console.error('API Error:', error);
            this.showToast(error.message, 'error');
            throw error;
        }
    },

    // --- ROUTER ---
    async router() {
        const path = window.location.pathname;
        console.log(`Routing to: ${path}`);

        // If not authenticated, force to login page, unless it's a valid auth-related path
        if (!this.state.isAuthed && !['/login', '/unlock/'].some(p => path.startsWith(p)) && !path.startsWith('/scan/')) {
            history.replaceState({}, '', '/login');
            this.state.currentPath = '/login';
        } else {
            this.state.currentPath = path;
        }

        this.state.isLoading = true;
        this.render(); // Render with loading state

        // Fetch data based on the new path
        if (this.state.isAuthed) {
            if (this.state.currentPath.startsWith('/b/')) {
                const browsePath = this.state.currentPath.substring(3) || this.state.user.folder;
                try {
                    const data = await this.api(`/api/browse?path=${browsePath}`);
                    if (data.ok) {
                        this.state.files = data.entries;
                        this.state.stats = data.stats;
                    }
                } catch (e) {
                    this.state.files = []; this.state.stats = {};
                }
            } else if (this.state.currentPath === '/share') {
                 try {
                    const data = await this.api('/api/share_info');
                    if (data.ok) {
                        this.state.sharedFiles = data.files;
                    }
                } catch(e) {
                    this.state.sharedFiles = [];
                }
            }
        } else {
            // Unauthenticated routes
            if (this.state.currentPath.startsWith('/login')) {
                await this.initLoginPage();
            } else {
                this.stopPolling();
            }
        }

        this.state.isLoading = false;
        this.render(); // Re-render with the new data
    },

    // --- RENDER FUNCTIONS ---
    renderHeader() {
        if (!this.state.isAuthed) return ''; // No header on login/unlock pages
        return `
            <header class="header">
                <div class="header-content">
                    <a class="logo" href="/" title="My Files">
                        <i class="fas fa-shield-alt"></i><span>FileVault</span>
                    </a>
                    <nav class="nav-menu">
                        <div class="user-badge">${this.state.user?.icon || "📁"} ${this.state.user?.folder || ""}</div>
                        <button id="theme-toggle" class="btn btn-secondary btn-icon" title="Toggle Theme"><i class="fas fa-moon"></i></button>
                        <a href="/logout" class="btn btn-danger btn-icon" title="Logout"><i class="fas fa-sign-out-alt"></i></a>
                    </nav>
                </div>
            </header>
        `;
    },

    renderView() {
        const path = this.state.currentPath;
        if (this.state.isLoading) {
            return '<h1>Loading...</h1>';
        }

        if (!this.state.isAuthed) {
            if (path.startsWith('/unlock/')) return this.renderUnlockPage();
            return this.renderLoginPage();
        }

        if (path.startsWith('/b/')) {
            return this.renderFileBrowser();
        }
        if (path === '/share') {
            return this.renderSharePage();
        }

        // Default to file browser if authed and no other route matches
        history.replaceState({}, '', `/b/${this.state.user.folder}`);
        return this.renderFileBrowser();
    },

    renderLoginPage() {
        // This function is now just for rendering, data fetching is in the router
        const { qr_b64 } = this.state.login;
        return `
            <div class="card" style="max-width: 520px; margin: 2rem auto; text-align: center;">
                <h1>Scan to Login</h1>
                <p style="color: var(--text-muted); margin-bottom: 1rem;">Scan from a logged-in device to access your files here.</p>
                <div id="qr-container" style="padding: 16px; background: #fff; border-radius: 12px; margin-bottom: 1rem; min-height: 280px; display: flex; align-items: center; justify-content: center;">
                    ${qr_b64
                        ? `<img src="data:image/png;base64,${qr_b64}" alt="QR Code" style="image-rendering:pixelated; image-rendering:crisp-edges;" />`
                        : `<h2><i class="fas fa-spinner fa-spin"></i> Generating QR Code...</h2>`
                    }
                </div>
                <p style="color:var(--text-muted);">Or create a new account:</p>
                <button id="login-default" class="btn btn-secondary" style="margin-top: 0.5rem;">Create or Continue with a New Account</button>
            </div>
        `;
    },

    async initLoginPage() {
        if (this.state.login.isPolling) return;

        this.state.login.isPolling = true;
        try {
            const data = await this.api('/api/login_init');
            if (data.ok) {
                this.state.login.token = data.token;
                this.state.login.qr_b64 = data.b64;
                this.render(); // Re-render with QR code
                this.pollForLogin();
            }
        } catch (e) {
            this.state.login.isPolling = false;
        }
    },

    pollForLogin() {
        if (!this.state.login.token || !this.state.login.isPolling) return;

        const poll = async () => {
            if (!this.state.login.isPolling) return;

            try {
                const data = await this.api(`/check/${this.state.login.token}`);
                if (data.authenticated) {
                    this.state.login.isPolling = false;
                    this.showToast('Login successful!', 'success');
                    this.init(); // Re-initialize the entire app
                } else {
                    setTimeout(poll, 1500);
                }
            } catch (e) {
                 setTimeout(poll, 3000);
            }
        };
        setTimeout(poll, 1000);
    },

    stopPolling() {
        this.state.login.isPolling = false;
        this.state.login.token = null;
        this.state.login.qr_b64 = null;
    },

    renderUnlockPage() {
        const pathParts = this.state.currentPath.split('/');
        const folder = pathParts[2] || '';
        const urlParams = new URLSearchParams(window.location.search);
        const nextUrl = urlParams.get('next') || `/b/${folder}`;

        return `
            <div class="card" style="max-width: 520px; margin: 2rem auto;">
                <h1><i class="fas fa-lock" style="margin-right: 0.5rem;"></i>Unlock Account</h1>
                <p style="color: var(--text-muted); margin-bottom: 1rem;">The account "<strong>${folder}</strong>" is private. Please enter the password.</p>
                <form id="unlock-form" data-folder="${folder}" data-next="${nextUrl}">
                    <input type="password" id="password-input" class="form-input" placeholder="Password" required style="margin-bottom: 1rem;">
                    <button type="submit" class="btn btn-primary">Unlock</button>
                </form>
            </div>
        `;
    },

    renderFileCard(item) {
        const isDir = item.is_dir;
        // Simplified icon logic for now
        let icon = 'fa-file';
        if (isDir) {
            icon = 'fa-folder';
        } else if (item.mime.startsWith('image/')) {
            icon = 'fa-file-image';
        } else if (item.mime.startsWith('video/')) {
            icon = 'fa-file-video';
        } else if (item.mime.startsWith('audio/')) {
            icon = 'fa-file-audio';
        } else if (item.mime === 'application/pdf') {
            icon = 'fa-file-pdf';
        }

        // In a list view, all cards have the same structure
        return `
            <div class="file-card" data-rel="${item.rel}" data-name="${item.name}" data-is-dir="${isDir ? 1 : 0}">
                <div class="file-preview" style="width: 48px; height: 48px; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                    <i class="fas ${icon}" style="font-size: 1.5rem; color: var(--text-secondary);"></i>
                </div>
                <div class="file-info" style="flex: 1; min-width: 0; display:flex; flex-direction: column; justify-content: center;">
                    <div class="file-name" style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${item.name}</div>
                    <div class="file-meta" style="font-size: 0.75rem; color: var(--text-muted);">${item.size_h} &bull; ${item.mtime_h}</div>
                </div>
                <div class="file-actions" style="display:flex; gap: 0.5rem;">
                    ${isDir
                        ? `<a href="/b/${item.rel}" class="btn btn-secondary btn-icon" title="Open"><i class="fas fa-folder-open"></i></a>`
                        : `<a href="${item.download_url}" class="btn btn-primary btn-icon" title="Download"><i class="fas fa-download"></i></a>`
                    }
                    <button class="btn btn-danger btn-icon" data-action="delete" data-rel="${item.rel}" title="Delete"><i class="fas fa-trash"></i></button>
                </div>
            </div>
        `;
    },

    renderSharePage() {
        const files = this.state.sharedFiles || [];
        const filesHTML = files.map(f => `<div class="card">${f.name}</div>`).join('');

        return `
            <div class="card">
                <h1>Shared Files</h1>
                ${files.length > 0 ? `
                    <p>You have shared ${files.length} file(s). These will be saved to your main folder.</p>
                    <div id="shareFileList" style="margin: 1rem 0;">${filesHTML}</div>
                    <div style="display: flex; gap: 0.5rem;">
                        <button class="btn btn-primary" data-action="commit-share"><i class="fas fa-save"></i> Save All Files</button>
                        <button class="btn btn-danger" data-action="clear-shares"><i class="fas fa-trash"></i> Clear All</button>
                    </div>
                ` : `
                    <p>No pending files to share. You can close this page.</p>
                `}
            </div>
        `;
    },

    renderFileBrowser() {
        if (this.state.isLoading) {
            return `<div class="card"><h2><i class="fas fa-spinner fa-spin"></i> Loading files...</h2></div>`;
        }

        const filesHTML = this.state.files && this.state.files.length > 0
            ? this.state.files.map(item => this.renderFileCard(item)).join('')
            : '<div class="card" style="text-align: center; color: var(--text-muted);">No files here. Upload something!</div>';

        return `
            <div class="toolbar">
                <div class="toolbar-row">
                    <div class="search-box">
                        <input id="searchInput" class="search-input" placeholder="Search..." />
                        <i class="fas fa-search search-icon"></i>
                    </div>
                    <button class="btn btn-secondary" data-action="new-folder"><i class="fas fa-folder-plus"></i> New Folder</button>
                </div>
            </div>

            <div class="upload-section" style="margin-top: 1rem;">
              <div class="upload-area" id="uploadArea" style="border: 2px dashed var(--primary); border-radius: .75rem; padding: 1.5rem 1rem; text-align: center; cursor:pointer;">
                <input type="file" id="uploadInput" class="upload-input" multiple style="display:none;" />
                <div class="upload-icon"><i class="fas fa-cloud-upload-alt" style="font-size: 2rem; color: var(--primary);"></i></div>
                <div class="upload-text" style="font-weight: 700;">Drop files or click here to upload</div>
              </div>
              <div class="progress-container" id="progressContainer" style="margin-top: 1rem; display: flex; flex-direction: column; gap: 0.5rem;"></div>
            </div>

            <div class="file-grid list-view" id="fileGrid" style="display: flex; flex-direction: column; gap: 0.5rem; margin-top: 1rem;">
                ${filesHTML}
            </div>
        `;
    },

    renderSharePage() { return '<div class="card"><h1>Share Page</h1></div>'; },
    renderUnlockPage() { return '<div class="card"><h1>Unlock Page</h1></div>'; },

    renderToastContainer() {
        return `<div class="toast-container" id="toastContainer"></div>`;
    },

    render() {
        if (!this.el) return;
        const viewHTML = this.renderView();
        const headerHTML = this.renderHeader();

        this.el.innerHTML = `
            ${headerHTML}
            <div class="container" id="app-container">
                ${viewHTML}
            </div>
            ${this.renderToastContainer()}
            <div id="modal-container"></div>
        `;

        // After rendering, if the file browser is visible, init its specific handlers
        if (this.state.isAuthed && this.state.currentPath.startsWith('/b/')) {
            this.initUploadHandlers();
        }
    },

    openModal(content) {
        const modalContainer = document.getElementById('modal-container');
        if (!modalContainer) return;

        modalContainer.innerHTML = `
            <div class="modal active" style="display: flex; align-items: center; justify-content: center; position: fixed; inset: 0; background: rgba(0,0,0,.8); -webkit-backdrop-filter:blur(10px); backdrop-filter:blur(10px); z-index:2000;">
                ${content}
            </div>
        `;

        modalContainer.querySelector('.modal').addEventListener('click', (e) => {
            if (e.target === e.currentTarget) {
                this.closeModal();
            }
        });

        document.addEventListener('keydown', this.handleEscKey);
    },

    closeModal() {
        const modalContainer = document.getElementById('modal-container');
        if (modalContainer) modalContainer.innerHTML = '';
        document.removeEventListener('keydown', this.handleEscKey);
    },

    handleEscKey(e) {
        if (e.key === 'Escape') {
            App.closeModal();
        }
    },

    applyTheme(theme, fromInit = false) {
        document.documentElement.classList.remove('light', 'barbie');
        if (theme && theme !== 'dark') {
            document.documentElement.classList.add(theme);
        }

        const btn = document.getElementById('theme-toggle');
        if (btn) {
            const icon = btn.querySelector('i');
            if (theme === 'light') icon.className = 'fas fa-sun';
            else if (theme === 'barbie') icon.className = 'fas fa-heart';
            else icon.className = 'fas fa-moon';
        }
        this.state.theme = theme;

        if (!fromInit) {
            localStorage.setItem('theme', theme);
            if(this.state.isAuthed) {
                this.api('/api/prefs', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ key: 'theme', value: theme })
                }).catch(e => console.warn("Failed to save theme preference to backend", e));
            }
        }
    },

    toggleTheme() {
        const themes = ['dark', 'light', 'barbie'];
        const currentTheme = this.state.theme || 'dark';
        const nextTheme = themes[(themes.indexOf(currentTheme) + 1) % themes.length];
        this.applyTheme(nextTheme);
    },

    showToast(message, type = 'info', duration = 3000) {
        const container = document.getElementById('toastContainer');
        if (!container) {
            console.warn('Toast container not found');
            return;
        }
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        const icon = { success: 'fa-check-circle', error: 'fa-times-circle', warning: 'fa-exclamation-triangle', info: 'fa-info-circle' }[type] || 'fa-info-circle';
        toast.innerHTML = `<i class="fas ${icon}"></i><div class="toast-message">${message}</div>`;
        container.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    },

    openPreviewModal(rel) {
        const file = this.state.files.find(f => f.rel === rel);
        if (!file) return;

        let previewContent = '';
        const mime = file.mime || '';

        if (mime.startsWith('image/')) {
            previewContent = `<img src="${file.raw_url}" style="max-width: 100%; max-height: 80vh; object-fit: contain;">`;
        } else if (mime.startsWith('video/')) {
            previewContent = `<video src="${file.raw_url}" controls autoplay style="max-width: 100%; max-height: 80vh;"></video>`;
        } else if (mime.startsWith('audio/')) {
            previewContent = `<audio src="${file.raw_url}" controls autoplay></audio>`;
        } else {
            previewContent = `<div class="card" style="padding: 2rem; text-align: center;">No preview available for this file type.</div>`;
        }

        const modalHTML = `
            <div class="modal-content" style="max-width: 90vw; width: auto; max-height: 90vh; overflow: hidden; display: flex; flex-direction: column; background: var(--bg-secondary); border-radius: 0.75rem;">
                <div class="modal-header" style="padding: 0.75rem 1rem; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center;">
                    <div class="modal-title" style="font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${file.name}</div>
                    <button class="modal-close" data-action="close-modal" style="background: none; border: none; font-size: 1.5rem; cursor: pointer; color: var(--text-primary); padding: 0 .5rem;">&times;</button>
                </div>
                <div class="modal-body" style="padding: 1rem; flex-grow: 1; display: flex; align-items: center; justify-content: center; background: var(--bg-primary);">
                    ${previewContent}
                </div>
                <div class="modal-footer" style="padding: 0.75rem 1rem; border-top: 1px solid var(--border); display: flex; gap: 0.5rem; justify-content: flex-end;">
                     <a href="${file.download_url}" class="btn btn-primary"><i class="fas fa-download"></i> Download</a>
                </div>
            </div>
        `;

        this.openModal(modalHTML);
    },

    // --- EVENT LISTENERS & INIT ---
    bindEvents() {
        window.addEventListener('popstate', () => this.router());

        // Clicks
        this.el.addEventListener('click', e => {
            const target = e.target;
            const anchor = target.closest('a');
            const button = target.closest('button');
            const card = target.closest('.file-card');

            if (anchor && anchor.origin === window.location.origin && anchor.pathname !== '/logout') {
                e.preventDefault();
                history.pushState({}, '', anchor.href);
                this.router();
                return;
            }

            if (button) {
                const action = button.dataset.action;
                const rel = button.dataset.rel;

                if (action === 'delete') {
                    e.stopPropagation();
                    if (confirm(`Are you sure you want to delete "${rel}"?`)) {
                        this.api('/api/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ files: [rel] }) })
                            .then(res => { if (res.ok) { this.showToast('Item deleted.', 'success'); this.router(); } });
                    }
                } else if (action === 'new-folder') {
                    const folderName = prompt('Enter new folder name:');
                    if (folderName) {
                        const currentBrowsePath = this.state.currentPath.startsWith('/b/') ? this.state.currentPath.substring(3) : this.state.user.folder;
                        this.api('/api/mkdir', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ dest: currentBrowsePath, name: folderName }) })
                            .then(res => { if (res.ok) { this.showToast('Folder created.', 'success'); this.router(); } });
                    }
                } else if (button.id === 'login-default') {
                    this.api('/api/login_with_default', { method: 'POST' }).then(res => { if (res.ok) this.init(); });
                } else if (action === 'close-modal') {
                    this.closeModal();
                } else if (button.id === 'theme-toggle') {
                    this.toggleTheme();
                } else if (action === 'commit-share') {
                    const file_ids = (this.state.sharedFiles || []).map(f => f.id);
                    const destination = this.state.user.folder; // Save to root of user's folder
                    this.api('/api/commit_share', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ ids: file_ids, destination: destination })
                    }).then(res => {
                        if (res.ok) {
                            this.showToast(`${res.committed.length} file(s) saved!`, 'success');
                            history.pushState({}, '', `/b/${destination}`);
                            this.router();
                        }
                    });
                } else if (action === 'clear-shares') {
                    if (confirm('Are you sure you want to clear all shared files?')) {
                        this.api('/api/clear_shares', { method: 'POST' }).then(res => {
                            if (res.ok) {
                                this.showToast('Shared files cleared.', 'info');
                                this.state.sharedFiles = [];
                                this.render(); // just re-render the empty view
                            }
                        });
                    }
                }
            }

            if (card && !button && !anchor) {
                const isDir = card.dataset.isDir === '1';
                if (!isDir) {
                    this.openPreviewModal(card.dataset.rel);
                } else {
                    history.pushState({}, '', `/b/${card.dataset.rel}`);
                    this.router();
                }
            }
        });

        // Form Submissions
        this.el.addEventListener('submit', e => {
            if (e.target.id === 'unlock-form') {
                e.preventDefault();
                const form = e.target;
                const folder = form.dataset.folder;
                const password = form.querySelector('#password-input').value;
                const nextUrl = form.dataset.next;

                this.api(`/api/unlock/${folder}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password }) })
                    .then(res => {
                        if (res.ok) {
                            this.showToast('Unlocked!', 'success');
                            this.init().then(() => {
                                history.pushState({}, '', nextUrl);
                                this.router();
                            });
                        }
                    }).catch(err => console.error("Unlock failed", err));
            }
        });
    },

    initUploadHandlers() {
        const uploadArea = document.getElementById('uploadArea');
        const uploadInput = document.getElementById('uploadInput');
        if (!uploadArea || !uploadInput) return;

        uploadArea.addEventListener('click', () => uploadInput.click());

        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            uploadArea.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            });
            document.body.addEventListener(eventName, (e) => { // Prevent browser from opening dropped file
                e.preventDefault();
                e.stopPropagation();
            });
        });

        uploadArea.addEventListener('dragenter', () => uploadArea.style.borderColor = 'var(--success)');
        uploadArea.addEventListener('dragleave', () => uploadArea.style.borderColor = 'var(--primary)');

        uploadArea.addEventListener('drop', (e) => {
            uploadArea.style.borderColor = 'var(--primary)';
            const files = e.dataTransfer.files;
            if (files.length) {
                this.handleFilesForUpload(files);
            }
        });

        uploadInput.addEventListener('change', (e) => {
            const files = e.target.files;
            if (files.length) {
                this.handleFilesForUpload(files);
            }
            uploadInput.value = '';
        });
    },

    handleFilesForUpload(files) {
        const fileList = Array.from(files);
        fileList.forEach(file => this.uploadFile(file));
    },

    uploadFile(file) {
        const progressContainer = document.getElementById('progressContainer');
        const uploadId = `upload-${Date.now()}-${Math.random()}`;
        const progressElement = document.createElement('div');
        progressElement.className = 'progress-item';
        progressElement.dataset.uploadId = uploadId;
        progressElement.innerHTML = `
            <div style="display: flex; align-items: center; gap: 1rem; padding: 0.5rem; background: var(--bg-tertiary); border-radius: 0.5rem;">
                <div style="flex-grow: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 0.8rem;">${file.name}</div>
                <div class="progress-percent" style="width: 4ch; font-size: 0.8rem;">0%</div>
                <div class="progress-bar" style="width: 100px; height: 8px; background: var(--bg-primary); border-radius: 4px; overflow: hidden;">
                    <div class="progress-fill" style="width: 0%; height: 100%; background: var(--primary); transition: width 0.2s;"></div>
                </div>
            </div>
        `;
        progressContainer.appendChild(progressElement);

        const formData = new FormData();
        const currentBrowsePath = this.state.currentPath.startsWith('/b/') ? this.state.currentPath.substring(3) : this.state.user.folder;
        formData.append('dest', currentBrowsePath);
        formData.append('file', file);

        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/api/upload', true);

        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                const percentComplete = Math.round((e.loaded / e.total) * 100);
                progressElement.querySelector('.progress-percent').textContent = `${percentComplete}%`;
                progressElement.querySelector('.progress-fill').style.width = `${percentComplete}%`;
            }
        });

        xhr.addEventListener('load', () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                this.showToast(`Uploaded: ${file.name}`, 'success');
                setTimeout(() => progressElement.remove(), 2000);
                this.router(); // Refresh file list
            } else {
                const error = JSON.parse(xhr.responseText || '{}').error || 'Upload failed';
                this.showToast(error, 'error');
                progressElement.querySelector('.progress-fill').style.backgroundColor = 'var(--danger)';
            }
        });

        xhr.addEventListener('error', () => {
            this.showToast(`Upload failed for ${file.name}`, 'error');
            progressElement.querySelector('.progress-fill').style.backgroundColor = 'var(--danger)';
        });

        xhr.send(formData);
    },

    async init() {
        console.log("Initializing app...");
        this.el = document.getElementById('app');
        if (!this.el) {
            console.error("App container #app not found!");
            return;
        }

        this.handleEscKey = this.handleEscKey.bind(this);
        this.state.isLoading = true;
        this.render();

        try {
            const me = await this.api('/api/me');
            if (me.ok) {
                this.state.isAuthed = true;
                this.state.user = me;
            }
        } catch (e) {
            this.state.isAuthed = false;
        } finally {
            this.state.isLoading = false;
        }

        // Apply theme early so UI is correct on first paint
        const savedTheme = localStorage.getItem('theme') || this.state.user?.prefs?.theme || 'dark';
        this.applyTheme(savedTheme, true);

        await this.router(); // Initial route is now async
        this.bindEvents();
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
