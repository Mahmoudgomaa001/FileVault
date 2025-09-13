// ACCOUNTS (admin)
  async function openAccounts(){
    try {
      const r = await fetch(URLS.api_accounts, {cache:'no-store'});
      const j = await r.json();
      if(!j.ok){ showToast(j.error || 'Failed to load accounts', 'error'); return; }

      const items = (j.accounts || []).map(a => {
        const badge = a.is_default ? '<span style="font-size:.75rem; background:var(--success); color:white; padding:.125rem .375rem; border-radius:.375rem; margin-left:.5rem;">default</span>' : '';
        const privacy = a.public ? '<span style="color:var(--text-muted); font-size:.8rem;">public</span>' : '<span style="color:var(--warning); font-size:.8rem;">private</span>';
        return `
          <div class="card accounts-card" style="display:flex; align-items:center; justify-content:space-between; gap:.5rem;">
            <div style="min-width:0;">
              <div style="font-weight:700; overflow:hidden; text-overflow:ellipsis;">${safeHTML(a.folder)} ${badge}</div>
              <div style="color:var(--text-muted); font-size:.8rem;">${privacy}</div>
            </div>
            <div class="account-actions">
              <button class="btn btn-primary" onclick="switchAccount('${a.folder.replace(/'/g,"\\'")}', true)"><i class="fas fa-right-left"></i> Switch</button>
              <button class="btn btn-secondary" onclick="openRenameModal('${a.folder.replace(/'/g,"\\'")}')"><i class="fas fa-pencil-alt"></i> Rename</button>
              <button class="btn btn-secondary" onclick="openTransferAdmin('${a.folder.replace(/'/g,"\\'")}')"><i class="fas fa-key"></i> Transfer Admin</button>
            </div>
          </div>`;
      }).join('') || '<div class="card" style="color:var(--text-muted);">No accounts yet.</div>';

      document.getElementById('accountsBody').innerHTML = `
        <div style="margin-bottom:.5rem; color:var(--text-secondary);">Switching also sets it as default for this device.</div>
        ${items}
      `;

      // Button binds
      document.getElementById('accCreateBtn')?.addEventListener('click', createAccountAndSwitch);

      openModal('accountsModal');
    } catch(e){
      showToast('Failed to load accounts', 'error');
    }
  }
  document.getElementById('accountsBtn')?.addEventListener('click', openAccounts);

  async function createAccountAndSwitch(){
    const name = (document.getElementById('accCreateNameInput')?.value || '').trim();
    try {
      const r = await fetch(URLS.api_accounts_create, {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({name, make_default:true})
      });
      const j = await r.json();
      if(j.ok){
        closeModal('accountsModal');
        showToast('Account created and switched', 'success');
        setTimeout(()=> window.location = j.browse_url, 300);
      } else {
        showToast(j.error || 'Failed to create', 'error');
      }
    } catch(e){
      showToast('Failed to create', 'error');
    }
  }

  async function switchAccount(folder, makeDefault=true){
    try {
      const r = await fetch(URLS.api_accounts_switch, {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({folder, make_default: makeDefault})
      });
      const j = await r.json();
      if(j.ok){
        closeModal('accountsModal');
        showToast('Switched', 'success');
        setTimeout(()=> window.location = j.browse_url, 200);
      } else {
        showToast(j.error || 'Failed to switch', 'error');
      }
    } catch(e){
      showToast('Failed to switch', 'error');
    }
  }

  // TRANSFER ADMIN (QR)
  async function openTransferAdmin(folder){
    try {
      const r = await fetch(URLS.api_accounts_transfer_admin_start, {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({folder})
      });
      const j = await r.json();
      if(j.ok){
        document.getElementById('transferTitle').textContent = `Transfer Admin: ${folder}`;
        document.getElementById('transferBody').innerHTML = `
          <div class="qr-box"><img src="data:image/png;base64,${j.b64}" alt="QR" style="image-rendering:pixelated; image-rendering:crisp-edges;"/></div>
          <div class="row" style="justify-content:space-between; margin-top:.75rem;">
            <div style="font-size:.85rem; color:var(--text-secondary); word-break:break-all;" id="transferLink">${j.url}</div>
            <button class="btn btn-secondary" id="transferCopyBtn"><i class="fas fa-link"></i> Copy</button>
          </div>
          <div style="margin-top:.5rem; color:var(--text-muted); font-size:.85rem;">
            Scan this QR from the new device to become the admin of this account. The scanning device will be logged in and set as default.
          </div>
        `;
        document.getElementById('transferCopyBtn')?.addEventListener('click', ()=> copyLink(j.url));
        openModal('transferAdminModal');
      } else {
        showToast(j.error || 'Failed to start transfer', 'error');
      }
    } catch(e){
      showToast('Failed to start transfer', 'error');
    }
  }

    function openRenameModal(oldName) {
        document.getElementById('renameAccountOldName').textContent = oldName;
        document.getElementById('renameAccountHiddenOldName').value = oldName;
        document.getElementById('renameAccountInput').value = '';
        openModal('renameAccountModal');
        setTimeout(()=> document.getElementById('renameAccountInput').focus(), 50);
    }

    async function confirmRename() {
        const oldName = document.getElementById('renameAccountHiddenOldName').value;
        const newName = document.getElementById('renameAccountInput').value.trim();

        if (!newName) {
            showToast('Please enter a new name.', 'warning');
            return;
        }

        try {
            const r = await fetch(URLS.api_accounts_rename, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ old_name: oldName, new_name: newName })
            });
            const j = await r.json();
            if (j.ok) {
                showToast('Account renamed!', 'success');
                closeModal('renameAccountModal');
                openAccounts();
                if (APP_CONFIG.current_folder === oldName) {
                    setTimeout(()=> window.location.href = window.location.pathname.replace('/b/' + oldName, '/b/' + newName), 300);
                }
            } else {
                showToast(j.error || 'Rename failed.', 'error');
            }
        } catch (e) {
            showToast('An error occurred during rename.', 'error');
        }
    }

    'use strict';

    let selectModeActive = false;
    let selectedFiles = new Set();
    let lastSelectedIndex = -1;

    function handleSelectionChange(){
        selectedFiles = new Set(Array.from(document.querySelectorAll('.file-select-checkbox:checked')).map(cb => cb.dataset.rel));

        document.querySelectorAll('.file-card').forEach(card => {
            const cb = card.querySelector('.file-select-checkbox');
            if(cb && selectedFiles.has(cb.dataset.rel)){
                card.classList.add('selected');
                cb.checked = true;
            } else {
                card.classList.remove('selected');
                if(cb) cb.checked = false;
            }
        });

        const bulkToolbar = document.getElementById('bulkActionsToolbar');
        if (bulkToolbar) {
            if(selectedFiles.size > 0){
                bulkToolbar.style.display = 'flex';
                document.getElementById('selectionCount').textContent = `${selectedFiles.size} selected`;
            } else {
                bulkToolbar.style.display = 'none';
                if (selectModeActive) {
                    toggleSelectMode(false);
                }
            }
        }
    }

    function toggleSelectMode(forceState) {
        selectModeActive = (forceState === undefined) ? !selectModeActive : forceState;
        document.body.classList.toggle('select-mode', selectModeActive);
        document.getElementById('selectModeBtn')?.classList.toggle('active', selectModeActive);

        if (!selectModeActive) {
            // Clear selection when exiting mode
            document.querySelectorAll('.file-select-checkbox:checked').forEach(cb => {
                cb.checked = false;
            });
            handleSelectionChange();
        }
    }

    function selectAll() {
        document.querySelectorAll('.file-card:not([style*="display: none"]) .file-select-checkbox').forEach(cb => {
            cb.checked = true;
        });
        handleSelectionChange();
    }

    function deselectAll() {
        document.querySelectorAll('.file-card .file-select-checkbox').forEach(cb => {
            cb.checked = false;
        });
        handleSelectionChange();
    }

    // Dhikr data

function changeDhikr() {
  const dhikrEl = document.getElementById('dhikrArabic');
  if (!dhikrEl) return;

  if (Array.isArray(APP_CONFIG.dhikr_list) && APP_CONFIG.dhikr_list.length > 0) {
    const randomDhikr = APP_CONFIG.dhikr_list[Math.floor(Math.random() * APP_CONFIG.dhikr_list.length)];

    dhikrEl.style.animation = 'none';
    // Using a very short timeout to allow the browser to apply the 'none' animation state
    // before re-applying the new animation.
    setTimeout(() => {
      if(dhikrEl) dhikrEl.textContent = randomDhikr.dhikr;
      dhikrEl.style.animation = 'fadeInText 0.5s ease';
    }, 10);
  }
}

setInterval(changeDhikr, 30000);


  // THEME + PREFS

  const root = document.documentElement;

  async function savePref(key, value){
    try { await fetch(URLS.api_prefs, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({key, value})}); } catch(e){}
  }

  function updateThemeBtnIcon(t){
    const btn = document.getElementById('themeBtn');
    if(!btn) return;
    btn.innerHTML = t === 'barbie' ? '<i class="fas fa-heart"></i>'
                  : t === 'light' ? '<i class="fas fa-sun" style=" color: yellow; "></i>'
                  : '<i class="fas fa-moon"></i>';
  }

  function applyTheme(t, opts={save:true}){
    root.classList.remove('light','barbie');
    if(t && t !== 'dark') root.classList.add(t);
    if(opts.save){
      try { localStorage.setItem('theme', t); } catch(e){}
      savePref('theme', t);
    }
    updateThemeBtnIcon(t || 'dark');
  }

  function getStartupTheme(){
    try { const t = localStorage.getItem('theme'); if(t) return t; } catch(e){}
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  }

  function toggleTheme(){
    const seq = ['dark','light','barbie'];
    const cur = root.classList.contains('barbie') ? 'barbie'
              : root.classList.contains('light') ? 'light'
              : (localStorage.getItem('theme') || 'dark');
    const next = seq[(seq.indexOf(cur) + 1) % seq.length];
    applyTheme(next, {save:true});
  }

  document.getElementById('themeBtn')?.addEventListener('click', toggleTheme);

  (async ()=>{
    try {
      const r = await fetch(URLS.api_prefs);
      const j = await r.json();
      const saved = j?.prefs?.theme;
      if(saved){ applyTheme(saved, {save:false}); }
      else { applyTheme(getStartupTheme(), {save:false}); }
    } catch(e){
      applyTheme(getStartupTheme(), {save:false});
    }
  })();

     // TOASTS
    function showToast(message, type='info'){
      const container = document.getElementById('toastContainer'); if(!container) return;
      const toast = document.createElement('div'); toast.className = `toast ${type}`;
      const icon = {success:'fa-check-circle', error:'fa-times-circle', warning:'fa-exclamation-triangle', info:'fa-info-circle'}[type] || 'fa-info-circle';
      toast.innerHTML = `<i class="fas ${icon}"></i><div class="toast-message">${message}</div>`;
      container.appendChild(toast);
      setTimeout(()=>{ toast.style.opacity='0'; setTimeout(()=>toast.remove(), 300); }, 3000);
      changeDhikr();
    }

    // MODALS
    function openModal(id){ const m = document.getElementById(id); if(m){ m.classList.add('active'); } }
    function closeModal(id){
      const m = document.getElementById(id);
      if(m){
        m.classList.remove('active');

        // Remove keyboard event listener when preview modal is closed
        if (id === 'previewModal') {
          document.removeEventListener('keydown', handlePreviewKeydown);
        }
      }
    }
    document.addEventListener('click', (e)=>{ if(e.target.classList.contains('modal')) e.target.classList.remove('active'); });
    document.addEventListener('keydown', (e)=>{
      // Check if the preview modal is active and has its own keydown handler
      const previewModalActive = document.getElementById('previewModal')?.classList.contains('active');

      // If we're in the preview modal, let the specific handler manage keyboard events
      if (previewModalActive && (e.key === 'ArrowLeft' || e.key === 'ArrowRight' || e.key === 'Escape')) {
        // Don't process these keys in the global handler when preview is active
        return;
      }

      if (e.key === 'a' && (e.ctrlKey || e.metaKey)) {
        if (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'TEXTAREA') {
            return;
        }
        e.preventDefault();
        if (!selectModeActive) {
            toggleSelectMode(true);
        }
        document.querySelectorAll('.file-card:not([style*="display: none"]) .file-select-checkbox').forEach(cb => {
            cb.checked = true;
        });
        handleSelectionChange();
      }

      if(e.key === 'Escape'){
        if (selectModeActive) {
            toggleSelectMode(false);
        } else {
            document.querySelectorAll('.modal.active').forEach(m=>{
              closeModal(m.id);
            });
        }
      }
    });

    // VIEW MODE + PREF
    let currentView = localStorage.getItem('fileView') || 'list';
    async function setView(view){
      currentView = view; localStorage.setItem('fileView', view);
      const grid = document.getElementById('fileGrid'); if(grid){ grid.classList.toggle('list-view', view === 'list'); }
      document.querySelectorAll('.view-btn').forEach(btn => btn.classList.toggle('active', btn.dataset.view === view));
      applySort();
      savePref('view', view);
    }

    // SEARCH
    function searchFiles(){
      const q = (document.getElementById('searchInput')?.value || '').toLowerCase();
      document.querySelectorAll('.file-card').forEach(card=>{
        const name = (card.dataset.name || '').toLowerCase();
        card.style.display = name.includes(q) ? '' : 'none';
      });
    }

    // SORTING
    function getSortPrefs(){
      return {
        by: localStorage.getItem('sortBy') || 'date',
        dir: localStorage.getItem('sortDir') || 'desc',
        foldersFirst: localStorage.getItem('foldersFirst') !== 'false'
      };
    }
    function setSortPrefs(by, dir, foldersFirst){
      if(by) localStorage.setItem('sortBy', by);
      if(dir) localStorage.setItem('sortDir', dir);
      if(typeof foldersFirst === 'boolean') localStorage.setItem('foldersFirst', String(foldersFirst));
    }
    function applySort(){
      const grid = document.getElementById('fileGrid'); if(!grid) return;
      const prefs = getSortPrefs();
      const cards = Array.from(grid.children).filter(el => el.classList?.contains('file-card'));
      const withIndex = cards.map((el, idx) => ({el, idx}));
      const cmp = (a, b) => {
        const ad = a.el.dataset, bd = b.el.dataset;
        const aDir = ad.isDir === '1', bDir = bd.isDir === '1';
        if(prefs.foldersFirst && aDir !== bDir) return aDir ? -1 : 1;

        let av, bv;
        switch(prefs.by){
          case 'size': av = parseInt(ad.size || '0', 10); bv = parseInt(bd.size || '0', 10); break;
          case 'type': av = (ad.mime || '').toLowerCase(); bv = (bd.mime || '').toLowerCase(); break;
          case 'date': av = parseInt(ad.mtime || '0', 10); bv = parseInt(bd.mtime || '0', 10); break;
          case 'name':
          default: av = (ad.name || '').toLowerCase(); bv = (bd.name || '').toLowerCase(); break;
        }
        let result = 0;
        if(av < bv) result = -1;
        else if(av > bv) result = 1;
        else result = a.idx - b.idx;
        return prefs.dir === 'asc' ? result : -result;
      };
      withIndex.sort(cmp);
      withIndex.forEach(({el}) => grid.appendChild(el));
      const sortBy = document.getElementById('sortBy'); if(sortBy) sortBy.value = prefs.by;
      const sortDir = document.getElementById('sortDir'); if(sortDir) sortDir.dataset.dir = prefs.dir, sortDir.innerHTML = prefs.dir === 'asc' ? '<i class="fas fa-arrow-up-wide-short"></i>' : '<i class="fas fa-arrow-down-wide-short"></i>';
      const ff = document.getElementById('foldersFirst'); if(ff) ff.checked = prefs.foldersFirst;
    }

    // UPLOADS
    const activeXHRs = new Map();

    function initUploadArea(){
      const area = document.getElementById('uploadArea');
      const input = document.getElementById('uploadInput');
      if(!area || !input) return;

      ['dragenter','dragover','dragleave','drop'].forEach(ev=>{
        area.addEventListener(ev, e=>{ e.preventDefault(); e.stopPropagation(); }, false);
        document.addEventListener(ev, e=>{ e.preventDefault(); e.stopPropagation(); }, false);
      });
      area.addEventListener('dragenter', ()=> area.classList.add('dragover'));
      area.addEventListener('dragleave', ()=> area.classList.remove('dragover'));
      area.addEventListener('drop', e=>{
        area.classList.remove('dragover');
        const files = e.dataTransfer.files; if(files?.length) handleNewFiles(files);
      });

      input.addEventListener('change', e=>{
        const files = e.target.files; if(files?.length){ handleNewFiles(files); }
        input.value = '';
      }, false);
    }

    function handleNewFiles(files){
      const arr = Array.from(files || []);
      if(!arr.length) return;
      const container = document.getElementById('progressContainer');
      if(container) container.innerHTML = '';
      for(const f of arr){
        const id = `up-${Date.now()}-${Math.random().toString(36).slice(2)}`;
        uploadSingleFile({file:f, id});
      }
    }

    function createProgressElement(filename, id){
      const div = document.createElement('div');
      div.className = 'progress-item';
      div.dataset.uploadId = id;
      div.innerHTML = `
        <div class="progress-header">
          <div class="progress-info">
            <div class="progress-filename">${filename}</div>
            <div class="progress-stats"><span class="stat-speed">0 B/s</span><span class="stat-eta">Starting…</span></div>
          </div>
          <div class="progress-actions">
            <span class="progress-percent">0%</span>
            <button class="progress-cancel" title="Cancel upload"><i class="fas fa-times"></i></button>
          </div>
        </div>
        <div class="progress-bar"><div class="progress-fill" style="width:0%"></div></div>
      `;
      div.querySelector('.progress-cancel').addEventListener('click', ()=> cancelUpload(id));
      return div;
    }

    function formatSpeed(bps){
      if(!bps || !isFinite(bps)) return "0 B/s";
      const units = ['B/s','KB/s','MB/s','GB/s']; let u=0; let s=bps;
      while(s>=1024 && u<units.length-1){ s/=1024; u++; }
      return `${s.toFixed(u?1:0)} ${units[u]}`;
    }
    function formatETA(sec){
      if(!isFinite(sec) || sec<=0) return '...';
      if(sec<60) return `${Math.round(sec)}s`;
      const m = Math.floor(sec/60), s=Math.round(sec%60);
      return `${m}m ${s}s`;
    }

    function updateProgress(element, data){
      if(!element) return;
      element.querySelector('.progress-fill').style.width = `${data.percent}%`;
      element.querySelector('.progress-percent').textContent = `${Math.round(data.percent)}%`;
      element.querySelector('.stat-speed').textContent = formatSpeed(data.speed);
      element.querySelector('.stat-eta').textContent = data.percent >= 100 ? 'Done' : formatETA(data.eta);
    }
    function markProgressComplete(element, success){
      if(!element) return;
      element.classList.add(success ? 'completed' : 'error');
      const btn = element.querySelector('.progress-cancel'); if(btn){ btn.disabled = true; btn.style.opacity = .5; }
      setTimeout(()=>{ element.remove(); }, 900);
    }

    function uploadSingleFile(item){
      const {file, id} = item;
      const container = document.getElementById('progressContainer');
      const row = createProgressElement(file.name, id);
      container?.appendChild(row);

      const form = new FormData();
      form.append('dest', window.currentPath || '');
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

      xhr.open('POST', URLS.api_upload);
      xhr.send(form);
    }

    function cancelUpload(id){
      const xhr = activeXHRs.get(id);
      if(xhr){ xhr.abort(); activeXHRs.delete(id); }
      const el = document.querySelector(`[data-upload-id="${id}"]`);
      if(el){ el.remove(); }
    }

    // SHARE / COPY
    function copyLink(url){
      try {
        if(navigator.clipboard){
          navigator.clipboard.writeText(url)
            .then(() => showToast('Link copied!', 'success'))
            .catch(err => {
              console.error('Clipboard API error:', err);
              fallbackCopy();
            });
        } else {
          fallbackCopy();
        }

        function fallbackCopy() {
          try {
            const i = document.createElement('input');
            i.value = url;
            i.style.position = 'fixed';
            i.style.opacity = '0';
            document.body.appendChild(i);
            i.select();
            const successful = document.execCommand('copy');
            document.body.removeChild(i);

            if (successful) {
              showToast('Link copied!', 'success');
            } else {
              showToast('Failed to copy link', 'error');
            }
          } catch (err) {
            console.error('Fallback copy error:', err);
            showToast('Failed to copy link', 'error');
          }
        }
      } catch (e) {
        console.error('Copy error:', e);
        showToast('Failed to copy link', 'error');
      }
    }

    // PREVIEW (pointerup to avoid double-tap; throttle duplicates)
    let lastPreviewAt = 0;
    let _pvTextCache = '';
    function handleCardOpenEvent(e){
      const card = e.target.closest('.file-card'); if(!card) return;

      if (e.target.closest('.file-actions')) return;

      if (selectModeActive) {
        const allCards = Array.from(document.querySelectorAll('.file-card:not([style*="display: none"])'));
        const currentIndex = allCards.indexOf(card);
        const checkbox = card.querySelector('.file-select-checkbox');
        if (!checkbox) return;

        if (e.shiftKey && lastSelectedIndex !== -1) {
            const start = Math.min(lastSelectedIndex, currentIndex);
            const end = Math.max(lastSelectedIndex, currentIndex);
            // First, uncheck everything to handle complex shift-click scenarios
            allCards.forEach(c => {
                const cb = c.querySelector('.file-select-checkbox');
                if(cb) cb.checked = false;
            });
            // Then, check the items in the range
            allCards.forEach((c, index) => {
                if (index >= start && index <= end) {
                    const cb = c.querySelector('.file-select-checkbox');
                    if(cb) cb.checked = true;
                }
            });
        } else {
            checkbox.checked = !checkbox.checked;
        }

        lastSelectedIndex = currentIndex;
        handleSelectionChange();
        return;
      }

      const now = Date.now();
      if(now - lastPreviewAt < 250) return;
      lastPreviewAt = now;

      const isDir = card.dataset.isDir === '1';
      const rel = card.dataset.rel, name = card.dataset.name, mime = card.dataset.mime, raw = card.dataset.raw, dl = card.dataset.dl;
      if(isDir){ window.location = URLS.browse + "/" + rel; }
      else { openPreview(rel, name, mime, raw, dl); }
    }

    let selectedDestination = '';
    function renderFolderTree(nodes, level = 0) {
        let html = '';
        for (const node of nodes) {
            html += `
                <div class="folder-tree-item" data-path="${node.path}" style="padding-left: ${level * 20}px;">
                    <i class="fas fa-folder"></i> ${node.name}
                </div>
            `;
            if (node.children && node.children.length > 0) {
                html += renderFolderTree(node.children, level + 1);
            }
        }
        return html;
    }
    async function openMoveModal() {
        if (selectedFiles.size === 0) {
            showToast('Please select files to move.', 'warning');
            return;
        }
        openModal('moveModal');
        const folderTreeDiv = document.getElementById('folderTree');
        folderTreeDiv.innerHTML = 'Loading...';

        try {
            const response = await fetch(URLS.api_folders);
            const data = await response.json();
            if (data.ok) {
                folderTreeDiv.innerHTML = renderFolderTree(data.tree);
                selectedDestination = ''; // Reset selection
                document.getElementById('confirmMoveBtn').disabled = true;

                document.querySelectorAll('.folder-tree-item').forEach(item => {
                    item.addEventListener('click', (e) => {
                        e.stopPropagation();
                        const destinationPath = item.dataset.path;
                        for (const sourcePath of selectedFiles) {
                            if (sourcePath === destinationPath || destinationPath.startsWith(sourcePath + '/')) {
                                showToast('Cannot move a folder into itself.', 'error');
                                item.classList.add('invalid');
                                setTimeout(()=> item.classList.remove('invalid'), 500);
                                return;
                            }
                        }
                        document.querySelectorAll('.folder-tree-item').forEach(i => i.classList.remove('selected'));
                        item.classList.add('selected');
                        selectedDestination = destinationPath;
                        document.getElementById('confirmMoveBtn').disabled = false;
                    });
                });
            } else {
                folderTreeDiv.innerHTML = `Error: ${data.error || 'Could not load folders.'}`;
            }
        } catch (error) {
            folderTreeDiv.innerHTML = 'Error loading folders.';
        }
    }
    async function confirmMove() {
        if (selectedDestination === '' || selectedDestination === null) {
            showToast('Please select a destination folder.', 'warning');
            return;
        }

        const sources = Array.from(selectedFiles);
        try {
            const r = await fetch(URLS.api_move, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sources, destination: selectedDestination })
            });
            const j = await r.json();
            if (j.ok) {
                showToast('Items moved successfully!', 'success');
                if(j.errors && j.errors.length > 0){
                    j.errors.forEach(err => showToast(`Error moving ${err.path}: ${err.error}`, 'error'));
                }
                // The socket events will handle the removal of old cards and addition of new ones.
                // We just need to clear the selection.
                toggleSelectMode(false); // This will clear selection and hide toolbar
            } else {
                showToast(j.error || 'Move failed.', 'error');
            }
        } catch (e) {
            showToast('An error occurred during the move.', 'error');
        }
        closeModal('moveModal');
    }
    async function confirmBulkDelete() {
        if (selectedFiles.size === 0) { return; }
        if (!confirm(`Are you sure you want to delete ${selectedFiles.size} item(s)?`)) { return; }

        const sources = Array.from(selectedFiles);
        try {
            const r = await fetch(URLS.api_delete, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ files: sources })
            });
            const j = await r.json();
            if (j.ok) {
                showToast(`${j.deleted.length} item(s) deleted.`, 'success');
                toggleSelectMode(false); // This will clear selection and hide toolbar
            } else {
                showToast(j.error || 'Delete failed.', 'error');
            }
        } catch (e) {
            showToast('An error occurred during deletion.', 'error');
        }
    }


    async function bulkDownload() {
        if (selectedFiles.size === 0) { return; }
        const sources = Array.from(selectedFiles);
        try {
            const r = await fetch(URLS.api_download_zip, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ files: sources })
            });

            if (r.ok) {
                const blob = await r.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                a.download = r.headers.get('Content-Disposition')?.split('filename=')[1]?.replace(/"/g, '') || 'download.zip';
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                a.remove();
            } else {
                const j = await r.json();
                showToast(j.error || 'Download failed.', 'error');
            }
        } catch (e) {
            showToast('An error occurred during download.', 'error');
        }
    }

    async function bulkDownloadIndividual() {
        if (selectedFiles.size === 0) { return; }
        const sources = Array.from(selectedFiles);
        for (const rel of sources) {
            const card = document.querySelector(`.file-card[data-rel="${rel}"]`);
            if (card && card.dataset.isDir !== '1') {
                const downloadUrl = card.dataset.dl;
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = downloadUrl;
                a.download = card.dataset.name;
                document.body.appendChild(a);
                a.click();
                a.remove();
            }
        }
    }

    function initBulkActions(){
        document.getElementById('selectModeBtn')?.addEventListener('click', toggleSelectMode);
        document.getElementById('bulkMoveBtn')?.addEventListener('click', openMoveModal);
        document.getElementById('confirmMoveBtn')?.addEventListener('click', confirmMove);
        document.getElementById('bulkDeleteBtn')?.addEventListener('click', confirmBulkDelete);
        document.getElementById('bulkDownloadBtn')?.addEventListener('click', bulkDownload);
        document.getElementById('bulkDownloadIndividualBtn')?.addEventListener('click', bulkDownloadIndividual);
        document.getElementById('cancelSelectionBtn')?.addEventListener('click', () => toggleSelectMode(false));
        document.getElementById('selectAllBtn')?.addEventListener('click', selectAll);
        document.getElementById('deselectAllBtn')?.addEventListener('click', deselectAll);
    }

    function initFileGrid() {
        const grid = document.getElementById('fileGrid');
        if (!grid) return;

        grid.addEventListener('click', (e) => {
            // We are using a simple click handler now.
            // The logic to differentiate between selection and opening is inside handleCardOpenEvent.
            const card = e.target.closest('.file-card');
            if (card) {
                handleCardOpenEvent(e);
            }
        });

        document.getElementById('pvPrevBtn')?.addEventListener('click', () => navigateToFile('prev'));
        document.getElementById('pvNextBtn')?.addEventListener('click', () => navigateToFile('next'));
    }


    // PREVIEW modal
    let currentFileIndex = -1;
    let filesList = [];

    function isTextLike(mime){
      if(!mime) return false;
      mime = mime.toLowerCase();
      return mime.startsWith('text/') || ['application/json','application/xml','application/javascript','application/x-javascript'].includes(mime);
    }

    function loadFilesList() {
      // Get all file cards from the grid
      const fileCards = document.querySelectorAll('.file-card');
      filesList = [];

      fileCards.forEach(card => {
        if(card.dataset.isDir !== '1') { // Only include files, not directories
          filesList.push({
            rel: card.dataset.rel,
            name: card.dataset.name,
            mime: card.dataset.mime,
            raw: card.dataset.raw,
            dl: card.dataset.dl
          });
        }
      });
    }



// The buggy global keydown listener below was removed to fix a TypeError.
// It was attempting to access properties on `pvModal` which could be null
// on pages where the preview modal does not exist (e.g., the login page),
// causing a "Cannot read properties of null (reading 'classList')" error.
// The correct keyboard handling for the preview modal is managed by the
// `handlePreviewKeydown` function, which is dynamically added and removed.


    function openPreview(rel, name, mime, rawUrl, downloadUrl){
      console.log('Opening preview for:', name);

      // Always reload the files list to ensure it's up to date
      loadFilesList();
      console.log('Files list loaded, length:', filesList.length);

      // Find current file index
      currentFileIndex = filesList.findIndex(file => file.rel === rel);
      console.log('Current file index:', currentFileIndex);

      document.getElementById('pvTitle').textContent = name;
      const box = document.getElementById('pvMedia');
      box.innerHTML = 'Loading…';

      const copyBtn = document.getElementById('pvCopyBtn');
      copyBtn.style.display = 'none';
      _pvTextCache = '';

      document.getElementById('pvOpenBtn').onclick = ()=> window.open(rawUrl, '_blank');
      const dl = document.getElementById('pvDownloadBtn'); dl.href = downloadUrl; dl.setAttribute('download', name);

      // Update navigation buttons visibility
      updateNavButtons();

      // First remove any existing keyboard event listener to prevent duplicates
      document.removeEventListener('keydown', handlePreviewKeydown);

      // Use setTimeout to ensure the event listener is added after the modal is fully opened
      setTimeout(() => {
        // Then add keyboard event listener
        document.addEventListener('keydown', handlePreviewKeydown);
        console.log('Preview keyboard navigation enabled');
      }, 100);

      // Add a click event listener to the modal to ensure focus
      const modal = document.getElementById('previewModal');
      if (modal) {
        modal.addEventListener('click', function(e) {
          // Only handle clicks on the modal background, not its contents
          if (e.target === modal) {
            // Refocus the modal to ensure keyboard events work
            modal.focus();
          }
        });
      }

      if(mime.startsWith('image/')){
        box.innerHTML = `<img src="${rawUrl}" alt="${name}">`;
      } else if(mime.startsWith('video/')){
        box.innerHTML = `<video src="${rawUrl}" controls preload="metadata" style="max-width:100%;"></video>`;
      } else if(mime.startsWith('audio/')){
        box.innerHTML = `<audio src="${rawUrl}" controls preload="metadata" style="width:100%;"></audio>`;
      } else if(mime === 'application/pdf'){
        box.innerHTML = `<embed src="${rawUrl}" type="application/pdf" style="width:100%; height:65vh;">`;
      } else if(isTextLike(mime)){
        box.innerHTML = `<pre style="white-space:pre-wrap; padding:.75rem; width:100%; max-height:65vh; overflow:auto;">Loading…</pre>`;
        fetch(rawUrl, {cache:'no-store'}).then(r=>r.text()).then(t=>{
          _pvTextCache = t;
          box.querySelector('pre').textContent = t;
          copyBtn.style.display = 'inline-flex';
          copyBtn.onclick = ()=>{
            if(navigator.clipboard){ navigator.clipboard.writeText(_pvTextCache).then(()=> showToast('Copied to clipboard','success')); }
            else { const i=document.createElement('textarea'); i.value=_pvTextCache; document.body.appendChild(i); i.select(); document.execCommand('copy'); i.remove(); showToast('Copied!','success'); }
          };
        }).catch(()=>{ box.querySelector('pre').textContent = 'Cannot preview'; });
      } else {
        box.innerHTML = `<div style="padding:.75rem; text-align:center;">No inline preview available. Use Open or Download.</div>`;
      }
      openModal('previewModal');
    }

    function updateNavButtons() {
      const prevBtn = document.getElementById('pvPrevBtn');
      const nextBtn = document.getElementById('pvNextBtn');

      if (filesList.length <= 1) {
        // Hide both buttons if there's only one file or no files
        prevBtn.style.display = 'none';
        nextBtn.style.display = 'none';
        return;
      }

      // Show/hide previous button based on current index
      prevBtn.style.display = currentFileIndex > 0 ? 'flex' : 'none';

      // Show/hide next button based on current index
      nextBtn.style.display = currentFileIndex < filesList.length - 1 ? 'flex' : 'none';
    }

    function navigateToFile(direction) {
      console.log('Navigating', direction, 'Current index:', currentFileIndex, 'Files list length:', filesList.length);

      // Reload the files list to ensure it's up to date
      loadFilesList();

      if (filesList.length <= 1) {
        console.log('Cannot navigate: not enough files');
        return;
      }

      let newIndex = currentFileIndex;
      if (direction === 'prev' && currentFileIndex > 0) {
        newIndex = currentFileIndex - 1;
        console.log('Moving to previous file, new index:', newIndex);
      } else if (direction === 'next' && currentFileIndex < filesList.length - 1) {
        newIndex = currentFileIndex + 1;
        console.log('Moving to next file, new index:', newIndex);
      } else {
        console.log('Cannot navigate further in this direction');
        return; // Can't navigate further
      }

      const file = filesList[newIndex];
      if (!file) {
        console.error('File not found at index:', newIndex);
        return;
      }

      console.log('Navigating to file:', file.name, 'Data:', file);

      // Use setTimeout to ensure the event handling is complete before opening the new preview
      setTimeout(() => {
        openPreview(file.rel, file.name, file.mime, file.raw, file.dl);
      }, 10);
    }



    // Handle keyboard navigation in preview modal
    function handlePreviewKeydown(e) {
      console.log('Keydown event detected:', e.key, e.keyCode);

      // Only process if preview modal is open
      const previewModal = document.getElementById('previewModal');
      if (!previewModal || !previewModal.classList.contains('active')) {
        console.log('Preview modal not active, removing listener');
        document.removeEventListener('keydown', handlePreviewKeydown);
        return;
      }

      // Left arrow key - previous file
      if (e.key === 'ArrowLeft' || e.keyCode === 37) {
        console.log('Left arrow pressed - navigating to previous file');
        e.preventDefault();
        e.stopPropagation();
        navigateToFile('prev');
      }
      // Right arrow key - next file
      else if (e.key === 'ArrowRight' || e.keyCode === 39) {
        console.log('Right arrow pressed - navigating to next file');
        e.preventDefault();
        e.stopPropagation();
        navigateToFile('next');
      }
      // Escape key - close modal
      else if (e.key === 'Escape' || e.keyCode === 27) {
        console.log('Escape pressed - closing preview modal');
        e.preventDefault();
        closeModal('previewModal');
      }
    }

    // DELETE
    function deleteFile(rel){
      if(!confirm('Delete this item?')) return;
      fetch(URLS.api_delete, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({files:[rel]})})
        .then(r=>r.json()).then(j=>{
          if(j.ok){ showToast('Deleted', 'success'); setTimeout(()=> location.reload(), 400); }
          else showToast(j.error || 'Delete failed', 'error');
        }).catch(()=> showToast('Delete failed', 'error'));
    }

    // NEW FOLDER
    function showNewFolderModal(){ openModal('newFolderModal'); setTimeout(()=> document.getElementById('folderNameInput')?.focus(), 50); }
    async function createNewFolder(){
      const name = (document.getElementById('folderNameInput')?.value || '').trim();
      if(!name){ showToast('Enter folder name', 'warning'); return; }
      try{
        const r = await fetch(URLS.api_mkdir, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({dest: window.currentPath || '', name})});
        const j = await r.json();
        if(j.ok){ showToast('Folder created', 'success'); closeModal('newFolderModal'); setTimeout(()=> location.reload(), 300); }
        else showToast(j.error || 'Failed', 'error');
      }catch(e){ showToast('Failed', 'error'); }
    }

    // CLIPBOARD TEXT
    function openClipModal(){ openModal('clipModal'); document.getElementById('clipTextInput')?.focus(); }
    async function saveClipboardText(){
      const ta = document.getElementById('clipTextInput');
      const nameInput = document.getElementById('clipNameInput');
      const text = (ta?.value || '').trim();
      let fname = (nameInput?.value || '').trim();
      if(!text){ showToast('Enter some text', 'warning'); return; }
      if(!fname){
        const now = new Date();
        const pad = (n)=> String(n).padStart(2,'0');
        fname = `clip-${now.getFullYear()}${pad(now.getMonth()+1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}.txt`;
      } else if(!/.txt$/i.test(fname)){
        fname += '.txt';
      }

      try {
        const r = await fetch(URLS.api_cliptext, {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({ dest: window.currentPath || '', name: fname, text })
        });
        const j = await r.json();
        if(j.ok){
          showToast('Text saved', 'success');
          closeModal('clipModal');
          setTimeout(()=> location.reload(), 300);
        } else {
          showToast(j.error || 'Failed to save', 'error');
        }
      } catch(e){
        showToast('Failed to save', 'error');
      }
    }

    // SORT controls bindings
    function initSortControls(){
      const sortBy = document.getElementById('sortBy');
      const sortDir = document.getElementById('sortDir');
      const ff = document.getElementById('foldersFirst');
      const prefs = getSortPrefs();
      if(sortBy){ sortBy.value = prefs.by; sortBy.addEventListener('change', ()=>{ setSortPrefs(sortBy.value, null, null); applySort(); }); }
      if(sortDir){
        sortDir.dataset.dir = prefs.dir;
        sortDir.innerHTML = prefs.dir === 'asc' ? '<i class="fas fa-arrow-up-wide-short"></i>' : '<i class="fas fa-arrow-down-wide-short"></i>';
        sortDir.addEventListener('click', ()=>{
          const cur = sortDir.dataset.dir === 'asc' ? 'desc' : 'asc';
          setSortPrefs(null, cur, null);
          sortDir.dataset.dir = cur;
          sortDir.innerHTML = cur === 'asc' ? '<i class="fas fa-arrow-up-wide-short"></i>' : '<i class="fas fa-arrow-down-wide-short"></i>';
          applySort();
        });
      }
      if(ff){ ff.checked = prefs.foldersFirst; ff.addEventListener('change', ()=>{ setSortPrefs(null, null, ff.checked); applySort(); }); }
    }

// SOCKET (live update without reload)
let fileUpdateQueue = [];
let fileUpdateTimer = null;

function processFileUpdates() {
    if (fileUpdateQueue.length === 0) return;

    const updates = [...fileUpdateQueue];
    fileUpdateQueue = [];

    let addedCount = 0;
    let deletedCount = 0;
    let movedCount = 0;

    updates.forEach(msg => {
        switch (msg.action) {
            case 'added':
                upsertFileCard(msg.meta);
                addedCount++;
                break;
            case 'deleted':
                removeFileCard(msg.rel);
                deletedCount++;
                break;
            case 'moved':
                msg.items.forEach(item => {
                    removeFileCard(item.from_rel);
                    upsertFileCard(item.meta);
                    movedCount++;
                });
                break;
        }
    });

    let notificationTitle = '';
    let notificationBody = '';

    if (movedCount > 0) {
        const message = `${movedCount} item${movedCount > 1 ? 's' : ''} moved`;
        showToast(message, 'success');
        notificationTitle = 'Items Moved';
        notificationBody = message;
    } else if (addedCount > 0) {
        const message = `${addedCount} file${addedCount > 1 ? 's' : ''} uploaded`;
        showToast(message, 'success');
        notificationTitle = 'Files Uploaded';
        notificationBody = message;
    }

    if (notificationTitle && Notification.permission === 'granted') {
        if (navigator.serviceWorker.controller) {
            navigator.serviceWorker.controller.postMessage({
                type: 'SHOW_NOTIFICATION',
                title: notificationTitle,
                body: notificationBody
            });
        }
    }

    if (addedCount > 0 || deletedCount > 0 || movedCount > 0) {
        try { changeDhikr(); } catch (e) {}
    }
}

function initSocket(){
  try {
    const socket = io({reconnection:true, reconnectionAttempts:5, reconnectionDelay:1000});

    socket.on('file_update', (msg)=> {
      if (!msg || typeof msg !== 'object') return;
      const cur = window.currentPath || '';

      let isRelevant = false;
      // msg.dir is the parent/destination directory of the event
      if (msg.dir === cur) {
        isRelevant = true;
      }

      // If a file is moved *from* the current directory, it's also relevant
      if (!isRelevant && msg.action === 'moved') {
        for (const item of msg.items) {
          const pathParts = item.from_rel.split('/');
          pathParts.pop();
          const parentPath = pathParts.join('/');
          if (parentPath === cur) {
            isRelevant = true;
            break;
          }
        }
      }

      if (isRelevant) {
        fileUpdateQueue.push(msg);
        clearTimeout(fileUpdateTimer);
        fileUpdateTimer = setTimeout(processFileUpdates, 500);
      } else {
         // Optional: notify if update happened in another folder, but for now we ignore it.
      }
    });

    socket.on('share_ready', (msg)=> {
        if(msg && msg.folder === APP_CONFIG.current_folder){
            showToast('Received a shared file!', 'info');
            checkForPendingShares();
        }
    });

  } catch(e){
    console.warn('Socket init failed', e);
  }
}
function safeHTML(s){
  return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function qsCardByRel(rel){
  const grid = document.getElementById('fileGrid');
  if(!grid) return null;
  const esc = (window.CSS && CSS.escape) ? CSS.escape(rel) : String(rel).replace(/"/g,'\\"');
  return grid.querySelector(`.file-card[data-rel="${esc}"]`);
}
function renderFileCard(meta){
  const isDir = !!meta.is_dir;
  const mime = (meta.mime || '').toLowerCase();
  let preview = '';
  if(isDir){
    preview = `<div class="file-icon-large" style="font-size:2rem;opacity:.6;">📁</div>`;
  } else if(mime.startsWith('image/')){
    preview = `<img src="${meta.raw_url}" alt="${safeHTML(meta.name)}" loading="lazy" />`;
  } else if(mime.startsWith('video/')){
    preview = `<div class="file-icon-large" style="font-size:2rem;opacity:.6;">🎬</div>`;
  } else if(mime.startsWith('audio/')){
    preview = `<div class="file-icon-large" style="font-size:2rem;opacity:.6;">🎵</div>`;
  } else if(mime === 'application/pdf'){
    preview = `<div class="file-icon-large" style="font-size:2rem;opacity:.6;">📄</div>`;
  } else {
    preview = `<div class="file-icon-large" style="font-size:2rem;opacity:.6;">📄</div>`;
  }

  const el = document.createElement('div');
  el.className = 'file-card';
  el.dataset.rel = meta.rel;
  el.dataset.name = meta.name || '';
  el.dataset.mime = meta.mime || '';
  el.dataset.isDir = isDir ? '1' : '0';
  el.dataset.size = String(meta.size || 0);
  el.dataset.mtime = String(meta.mtime || 0);
  el.dataset.raw = meta.raw_url || '';
  el.dataset.dl = meta.download_url || '';

  const openHref = encodeURI(`/b/${meta.rel}`);
  el.innerHTML = `
    <div class="file-preview">${preview}</div>
    <div class="file-info">
      <div class="file-name" title="${safeHTML(meta.name)}">${safeHTML(meta.name)}</div>
      <div class="file-meta">${safeHTML(meta.size_h || (isDir ? '-' : ''))} • ${safeHTML(meta.mtime_h || '')}</div>
      <div class="file-actions">
        ${isDir
          ? `<a class="btn btn-secondary btn-icon" href="${openHref}" title="Open"><i class="fas fa-folder-open"></i></a>
             <button class="btn btn-danger btn-icon" onclick="event.stopPropagation(); deleteFile('${meta.rel.replace(/'/g,"\\'")}')" title="Delete Folder"><i class="fas fa-trash"></i></button>`
          : `<a class="btn btn-primary btn-icon" href="${meta.download_url}" title="Download"><i class="fas fa-download"></i></a>
             <button class="btn btn-secondary btn-icon" onclick="event.stopPropagation(); shareFile('${meta.rel.replace(/'/g,"\\'")}')" title="Share"><i class="fas fa-share"></i></button>
             <button class="btn btn-danger btn-icon" onclick="event.stopPropagation(); deleteFile('${meta.rel.replace(/'/g,"\\'")}')" title="Delete"><i class="fas fa-trash"></i></button>`
        }
      </div>
    </div>
  `;
  return el;
}
function upsertFileCard(meta){
  const grid = document.getElementById('fileGrid');
  if(!grid || !meta) return;

  const noFilesMessage = document.getElementById('noFilesMessage');
  if (noFilesMessage) {
    noFilesMessage.style.display = 'none';
  }

  const existing = qsCardByRel(meta.rel);
  const node = renderFileCard(meta);
  if(existing){
    existing.replaceWith(node);
  } else {
    grid.appendChild(node);
  }
  // Keep UX consistent: apply current sort and search filter
  try { applySort(); } catch(e){}
  try { searchFiles(); } catch(e){}
}
function checkGridEmpty() {
    const grid = document.getElementById('fileGrid');
    const noFilesMessage = document.getElementById('noFilesMessage');
    if (!grid || !noFilesMessage) return;
    const hasCards = grid.querySelector('.file-card');
    noFilesMessage.style.display = hasCards ? 'none' : '';
}
function removeFileCard(rel){
  const el = qsCardByRel(rel);
  if(el) {
    el.remove();
    setTimeout(checkGridEmpty, 50);
  }
}
    // My QR modal with toggle (optional online/local)
    let qrOnlineMode = localStorage.getItem('qrMode') === 'online';
    async function showMyQR(){
      try {
        const mode = qrOnlineMode ? 'online' : 'local';
        const r = await fetch(`${URLS.api_my_qr}?mode=${mode}`, {cache:'no-store'});
        const j = await r.json();
        if(j.ok){
          const toggleId = 'qrToggle-' + Date.now();
          document.getElementById('myQRBody').innerHTML = `
            ${j.ngrok_available ? `
            <div class="toggle-container" style="margin-bottom: 1rem; justify-content: center;">
              <span class="toggle-label">Local</span>
              <div class="toggle-switch ${qrOnlineMode ? 'active' : ''}" id="${toggleId}">
                <div class="slider"></div>
              </div>
              <span class="toggle-label">Online</span>
            </div>
            ` : ''}
            <div class="qr-box"><img src="data:image/png;base64,${j.b64}" alt="QR" style="image-rendering:pixelated; image-rendering:crisp-edges;"/></div>
            <p style="text-align: center; margin-top: .75rem; color: var(--text-secondary);">Or enter this code on the other device:</p>
            <p style="font-size: 2rem; font-weight: bold; color: var(--primary); text-align: center; letter-spacing: 0.1em; margin-bottom: 1rem;">${j.login_code}</p>
            <div class="row" style="justify-content:space-between; margin-top:.75rem; border-top: 1px solid var(--border); padding-top: .75rem;">
              <div style="font-size:.85rem; color:var(--text-secondary); word-break:break-all;" id="myQRLink">${j.url}</div>
              <button class="btn btn-secondary" id="copyQRBtn"><i class="fas fa-link"></i> Copy Link</button>
            </div>
            ${!j.ngrok_available && qrOnlineMode ? '<p style="color:var(--warning); text-align:center; margin-top:.5rem;"><i class="fas fa-exclamation-triangle"></i> Ngrok not available. Showing local QR.</p>' : ''}
          `;
          document.getElementById('copyQRBtn')?.addEventListener('click', ()=> copyLink(j.url));
          if(j.ngrok_available){
            const toggle = document.getElementById(toggleId);
            if(toggle){
              toggle.addEventListener('click', ()=>{
                qrOnlineMode = !qrOnlineMode;
                localStorage.setItem('qrMode', qrOnlineMode ? 'online' : 'local');
                closeModal('myQRModal');
                setTimeout(showMyQR, 100);
              });
            }
          }
          openModal('myQRModal');
        } else {
          showToast('Failed to generate QR', 'error');
        }
      } catch(e){ showToast('Failed to generate QR', 'error'); }
    }
    document.getElementById('myQRBtn')?.addEventListener('click', showMyQR);

    // Settings (only for admin; button is hidden for non-admin)
    async function openSettings(){
      try {
        const r = await fetch(URLS.api_me, {cache:'no-store'});
        const j = await r.json();
        if(!j.ok) return;

        const privacyToggle = document.getElementById('privacyToggle');
        if(j.public === false) privacyToggle.classList.add('active'); else privacyToggle.classList.remove('active');

        const deleteToggle = document.getElementById('allowDeleteToggle');
        if(j.prefs?.allow_non_admin_delete === false) deleteToggle.classList.remove('active'); else deleteToggle.classList.add('active');

        const codeInput = document.getElementById('permanentCodeInput');
        if (j.permanent_code) {
          codeInput.value = j.permanent_code;
        } else {
          codeInput.value = '';
        }
        // Also try to populate the token if it exists, though it's mainly set on generation
        // This requires a new endpoint or modifying /api/me to return the token, which is a security risk.
        // Let's stick to showing the code only, and the token on generation.

        openModal('settingsModal');
      } catch(e){ openModal('settingsModal'); }
    }
    function togglePrivacy(){ const t = document.getElementById('privacyToggle'); t.classList.toggle('active'); }
    document.getElementById('settingsBtn')?.addEventListener('click', openSettings);
    document.getElementById('privacyToggle')?.addEventListener('click', togglePrivacy);
    document.getElementById('allowDeleteToggle')?.addEventListener('click', ()=> document.getElementById('allowDeleteToggle').classList.toggle('active'));
    document.getElementById('generateTokenBtn')?.addEventListener('click', generateToken);
    document.getElementById('regenerateTokenBtn')?.addEventListener('click', regenerateToken);
    document.getElementById('shareTokenBtn')?.addEventListener('click', showTokenShare);
    document.getElementById('setupPwaBtn')?.addEventListener('click', setupPwaToken);
    document.getElementById('saveSettingsBtn')?.addEventListener('click', async ()=>{
      const priv = document.getElementById('privacyToggle').classList.contains('active'); // true => private
      const pwd = document.getElementById('privacyPassword').value || '';
      const allowDelete = document.getElementById('allowDeleteToggle').classList.contains('active');

      let all_ok = true;
      try {
        await savePref('allow_non_admin_delete', allowDelete);
      } catch(e) { all_ok = false; }

      try {
        const r = await fetch(URLS.api_privacy, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({public: !priv, password: pwd})});
        const j = await r.json();
        if(!j.ok){ all_ok = false; showToast(j.error || 'Failed to save privacy', 'error'); }
      } catch(e){ all_ok = false; showToast('Failed to save privacy', 'error'); }

      if(all_ok){
        showToast('Settings saved', 'success');
        document.getElementById('privacyPassword').value='';
        closeModal('settingsModal');
      }
    });

    async function setupPwaToken() {
      try {
        showToast('Generating and saving token for PWA...', 'info');
        const r = await fetch(URLS.api_accounts_token, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({name: 'PWA Offline Share Token'})
        });
        const j = await r.json();
        if (j.ok && j.token) {
          await window.fileDB.initDB();
          await window.fileDB.saveConfigValue('api_token', j.token);
          showToast('Offline Share is now enabled!', 'success');
        } else {
          showToast(j.error || 'Failed to get token.', 'error');
        }
      } catch (e) {
        showToast('An error occurred during PWA setup.', 'error');
      }
    }

    async function generateToken() {
      try {
        const r = await fetch(URLS.api_accounts_token, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({name: 'Non-expiring API Token'})
        });
        const j = await r.json();

        if (j.ok) {
          const tokenInput = document.getElementById('apiTokenInput');
          tokenInput.value = j.token;

          const codeInput = document.getElementById('permanentCodeInput');
          if (j.permanent_code) {
            codeInput.value = j.permanent_code;
          }

          tokenInput.select();
          document.execCommand('copy');
          // Store token for sharing
          tokenInput.dataset.token = j.token;
          // Show share button
          document.getElementById('shareTokenBtn').style.display = 'inline-flex';
          showToast('Token and code generated. Token copied.', 'success');
        } else {
          showToast(j.error || 'Failed to generate token', 'error');
        }
      } catch (e) {
        showToast('Failed to generate token', 'error');
      }
    }

    async function regenerateToken() {
      if (!confirm('Are you sure you want to regenerate your permanent token and code? The old ones will stop working immediately.')) {
        return;
      }
      try {
        const r = await fetch(URLS.api_accounts_token_regenerate, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'}
        });
        const j = await r.json();

        if (j.ok) {
          const tokenInput = document.getElementById('apiTokenInput');
          tokenInput.value = j.token;

          const codeInput = document.getElementById('permanentCodeInput');
          if (j.permanent_code) {
            codeInput.value = j.permanent_code;
          }

          tokenInput.select();
          document.execCommand('copy');
          tokenInput.dataset.token = j.token;
          document.getElementById('shareTokenBtn').style.display = 'inline-flex';
          showToast('New token and code generated. Token copied.', 'success');
        } else {
          showToast(j.error || 'Failed to regenerate token', 'error');
        }
      } catch (e) {
        showToast('Failed to regenerate token', 'error');
      }
    }

    async function showTokenShare() {
      try {
        const tokenInput = document.getElementById('apiTokenInput');
        const token = tokenInput.dataset.token || tokenInput.value;

        if (!token) {
          showToast('Please generate a token first', 'warning');
          return;
        }

        // Generate QR code for token URL
        const mode = localStorage.getItem('qrMode') === 'online' ? 'online' : 'local';
        const r = await fetch(`${URLS.api_my_qr}?mode=${mode}&token=${encodeURIComponent(token)}`, {cache:'no-store'});
        const j = await r.json();

        if (j.ok) {
          const toggleId = 'tokenQrToggle-' + Date.now();
          document.getElementById('tokenShareBody').innerHTML = `
            ${j.ngrok_available ? `
            <div class="toggle-container">
              <span class="toggle-label">Local</span>
              <div class="toggle-switch ${qrOnlineMode ? 'active' : ''}" id="${toggleId}">
                <div class="slider"></div>
              </div>
              <span class="toggle-label">Online</span>
            </div>
            ` : ''}
            <div class="qr-box"><img src="data:image/png;base64,${j.b64}" alt="QR" style="image-rendering:pixelated; image-rendering:crisp-edges;"/></div>
            <div class="row" style="justify-content:space-between; margin-top:.75rem;">
              <div style="font-size:.85rem; color:var(--text-secondary); word-break:break-all;" id="tokenShareLink">${j.url}</div>
              <button class="btn btn-secondary" id="copyTokenShareBtn"><i class="fas fa-link"></i> Copy</button>
            </div>
            <p style="margin-top:0.5rem; text-align:center;">Share this link to allow others to access your server with this token</p>
            ${!j.ngrok_available && qrOnlineMode ? '<p style="color:var(--warning); text-align:center; margin-top:.5rem;"><i class="fas fa-exclamation-triangle"></i> Ngrok not available. Showing local QR.</p>' : ''}
          `;

          document.getElementById('copyTokenShareBtn')?.addEventListener('click', () => copyTokenShareLink());

          if (j.ngrok_available) {
            const toggle = document.getElementById(toggleId);
            if (toggle) {
              toggle.addEventListener('click', () => {
                qrOnlineMode = !qrOnlineMode;
                localStorage.setItem('qrMode', qrOnlineMode ? 'online' : 'local');
                closeModal('tokenShareModal');
                setTimeout(showTokenShare, 100);
              });
            }
          }

          openModal('tokenShareModal');
        } else {
          showToast('Failed to generate QR code', 'error');
        }
      } catch (e) {
        console.error(e);
        showToast('Failed to generate QR code', 'error');
      }
    }

    function copyTokenShareLink() {
      const linkElement = document.getElementById('tokenShareLink');
      if (linkElement) {
        const text = linkElement.textContent;
        try {
          // Try the modern clipboard API first
          if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text)
              .then(() => showToast('Link copied to clipboard', 'success'))
              .catch(err => {
                console.error('Clipboard API error:', err);
                fallbackCopy();
              });
          } else {
            fallbackCopy();
          }
        } catch (e) {
          console.error('Copy error:', e);
          fallbackCopy();
        }

        // Fallback copy method
        function fallbackCopy() {
          try {
            const textarea = document.createElement('textarea');
            textarea.value = text;
            textarea.style.position = 'fixed';  // Prevent scrolling to the element
            textarea.style.opacity = '0';
            document.body.appendChild(textarea);
            textarea.focus();
            textarea.select();
            const successful = document.execCommand('copy');
            document.body.removeChild(textarea);
            if (successful) {
              showToast('Link copied to clipboard', 'success');
            } else {
              showToast('Failed to copy link', 'error');
            }
          } catch (err) {
            console.error('Fallback copy error:', err);
            showToast('Failed to copy link', 'error');
          }
        }
      }
    }

    async function goOffline() {
        try {
            const r = await fetch(URLS.api_go_offline + '?next=' + encodeURIComponent(window.location.pathname + window.location.search));
            const j = await r.json();
            if (j.ok && j.url) {
                showToast('Switching to local address...', 'info');
                window.location.href = j.url;
            } else {
                showToast(j.error || 'Failed to switch to local mode.', 'error');
            }
        } catch (e) {
            showToast('Error switching to local mode.', 'error');
        }
    }

    async function goOnline() {
        try {
            const r = await fetch(URLS.api_go_online + '?next=' + encodeURIComponent(window.location.pathname + window.location.search));
            const j = await r.json();
            if (j.ok && j.url) {
                showToast('Switching to online address...', 'info');
                window.location.href = j.url;
            } else {
                showToast(j.error || 'Failed to switch to online mode.', 'error');
            }
        } catch (e) {
            showToast('Error switching to online mode.', 'error');
        }
    }

    // Mobile Menu
    function initMobileMenu() {
      const menuBtn = document.getElementById('mobileMenuBtn');
      const dropdown = document.getElementById('mobileDropdown');
      const installBtn = document.getElementById('installBtn');
      const installBtnMobile = document.getElementById('installBtnMobile');

      if (menuBtn && dropdown) {
        menuBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          dropdown.classList.toggle('active');
        });

        document.addEventListener('click', (e) => {
          if (!dropdown.contains(e.target) && dropdown.classList.contains('active')) {
            dropdown.classList.remove('active');
          }
        });
      }

      // Sync visibility of mobile install button with desktop one
      if (installBtn && installBtnMobile) {
          const observer = new MutationObserver(() => {
              installBtnMobile.style.display = installBtn.style.display === 'none' ? 'none' : 'flex';
          });
          observer.observe(installBtn, { attributes: true, attributeFilter: ['style'] });
          // Initial sync
          installBtnMobile.style.display = installBtn.style.display === 'none' ? 'none' : 'flex';
      }
    }

    // PUSH NOTIFICATIONS (Local)
    async function requestNotificationPermission() {
        if (!('Notification' in window)) {
            showToast('This browser does not support desktop notification', 'error');
            return;
        }
        const subscribeBtn = document.getElementById('subscribeBtn');
        const pushStatus = document.getElementById('pushStatus');
        subscribeBtn.disabled = true;

        try {
            const permission = await Notification.requestPermission();
            if (permission === 'granted') {
                showToast('Notifications enabled!', 'success');
                pushStatus.textContent = 'Notifications are enabled for this site.';
            } else {
                showToast('Notification permission was not granted.', 'warning');
                pushStatus.textContent = 'Notifications have been disabled.';
                subscribeBtn.disabled = false;
            }
        } catch (e) {
            console.error('Notification permission request failed:', e);
            showToast('Failed to enable notifications.', 'error');
            subscribeBtn.disabled = false;
        }
    }

    function initNotificationState() {
        if (!('Notification' in window)) {
            document.getElementById('subscribeBtn').style.display = 'none';
            return;
        }
        const subscribeBtn = document.getElementById('subscribeBtn');
        const pushStatus = document.getElementById('pushStatus');
        if (!subscribeBtn || !pushStatus) return;

        if(Notification.permission === 'granted') {
            subscribeBtn.disabled = true;
            pushStatus.textContent = 'Notifications are enabled on this device.';
        } else if (Notification.permission === 'denied') {
            subscribeBtn.disabled = true;
            pushStatus.textContent = 'Notifications have been disabled in your browser settings.';
        }
        else {
            subscribeBtn.disabled = false;
            pushStatus.textContent = 'Enable notifications to be alerted of new files.';
        }
    }

    // INIT
    document.addEventListener('DOMContentLoaded', async ()=>{
      const dhikrBanner = document.getElementById('dhikrBanner');
      if (dhikrBanner) {
        const dhikrToggleBtn = document.getElementById('dhikrToggleBtn');
        if (dhikrToggleBtn) {
          dhikrToggleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const isCollapsed = dhikrBanner.classList.toggle('collapsed');
            document.body.classList.toggle('dhikr-collapsed', isCollapsed);
            const icon = dhikrToggleBtn.querySelector('i');
            if (icon) {
              icon.className = isCollapsed ? 'fas fa-chevron-down' : 'fas fa-chevron-up';
            }
            dhikrToggleBtn.title = isCollapsed ? 'Expand Banner' : 'Collapse Banner';
          });
        }
      }

      window.currentPath = APP_CONFIG.current_rel;
      try {
        const r = await fetch('/api/prefs'); const j = await r.json();
        const v = j?.prefs?.view || localStorage.getItem('fileView') || 'grid';
        setView(v);
      } catch(e){ setView(localStorage.getItem('fileView') || 'grid'); }

      // Page-specific initializations for the main file browser
      if (document.getElementById('fileGrid')) {
        document.getElementById('searchInput')?.addEventListener('input', searchFiles);
        initUploadArea();
        initFileGrid();
        initSortControls();
        applySort();
        initBulkActions();
        checkGridEmpty();
        initSocket();

        // Bind Create Folder / Paste text buttons
        document.getElementById('mkdirCreateBtn')?.addEventListener('click', createNewFolder);
        document.getElementById('folderNameInput')?.addEventListener('keydown', (e)=>{ if(e.key==='Enter'){ e.preventDefault(); createNewFolder(); }});
        document.getElementById('openClipBtn')?.addEventListener('click', openClipModal);
        document.getElementById('clipSaveBtn')?.addEventListener('click', saveClipboardText);
        document.getElementById('clipTextInput')?.addEventListener('keydown', (e)=>{ if((e.ctrlKey||e.metaKey) && e.key==='Enter'){ e.preventDefault(); saveClipboardText(); }});
        document.getElementById('clipNameInput')?.addEventListener('keydown', (e)=>{ if(e.key==='Enter'){ e.preventDefault(); saveClipboardText(); }});
      }

      // Global initializations for all pages
      document.getElementById('confirmRenameBtn')?.addEventListener('click', confirmRename);
      document.getElementById('goOfflineBtn')?.addEventListener('click', goOffline);
      document.getElementById('goOnlineBtn')?.addEventListener('click', goOnline);
      document.getElementById('subscribeBtn')?.addEventListener('click', requestNotificationPermission);
      initPwaInstall();
      initMobileMenu();
      initNotificationState();
    });

    // PWA INSTALL
    function initPwaInstall() {
      const installBtn = document.getElementById('installBtn');
      if (!installBtn) return;

      // Hide button if app is already installed
      if (window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone) {
        installBtn.style.display = 'none';
        return;
      }

      let deferredPrompt;
      window.addEventListener('beforeinstallprompt', (e) => {
        e.preventDefault();
        deferredPrompt = e;
        // Show the button if the app can be installed
        installBtn.style.display = 'inline-flex';
        installBtn.classList.remove('btn-secondary');
        installBtn.classList.add('btn-primary');
      });

      installBtn.addEventListener('click', async () => {
        if (deferredPrompt) {
          deferredPrompt.prompt();
          const { outcome } = await deferredPrompt.userChoice;
          if (outcome === 'accepted') {
            showToast('App installed!', 'success');
            installBtn.style.display = 'none'; // Hide after accepting
          }
          deferredPrompt = null;
        }
      });

      window.addEventListener('appinstalled', () => {
        installBtn.style.display = 'none';
        deferredPrompt = null;
      });
    }

    // FAB
    function toggleFabMenu(){ document.getElementById('fabMenu')?.classList.toggle('active'); }
    function closeFabMenu(){ document.getElementById('fabMenu')?.classList.remove('active'); }
