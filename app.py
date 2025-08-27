from flask import Flask, render_template_string, request, jsonify, send_from_directory, send_file, session, redirect, url_for
import os
import shutil
import zipfile
import io
from functools import wraps
from werkzeug.utils import secure_filename
import logging

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a real secret key

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
users = {
    "admin": "password",
    "user": "password"
}
user_roles = {
    "admin": "admin",
    "user": "user"
}

FILES_DIRECTORY = 'files'
if not os.path.exists(FILES_DIRECTORY):
    os.makedirs(FILES_DIRECTORY)

app.config['UPLOAD_FOLDER'] = FILES_DIRECTORY

# Admin settings
admin_settings = {
    'allow_user_delete': True
}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session or user_roles.get(session['username']) != 'admin':
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if users.get(username) == password:
            session['username'] = username
            return redirect(url_for('index'))
        return 'Invalid credentials'
    return '''
        <form method="post">
            Username: <input type="text" name="username"><br>
            Password: <input type="password" name="password"><br>
            <input type="submit" value="Login">
        </form>
    '''

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

# Store the template in a variable to avoid file I/O on every request
TEMPLATE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>File Manager</title>
    <style>
        body { font-family: sans-serif; margin: 0; background-color: #f4f4f4; }
        .container { max-width: 960px; margin: 20px auto; background: #fff; padding: 20px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
        #file-list { list-style: none; padding: 0; }
        #file-list li { display: flex; align-items: center; padding: 10px; border-bottom: 1px solid #eee; user-select: none; }
        #file-list li:hover { background-color: #f0f8ff; }
        #file-list li.selected { background-color: #cce5ff; border: 1px solid #99ccff; }
        #file-list .file-icon { margin-right: 10px; width: 20px; text-align: center; }
        #file-list .file-name { flex-grow: 1; cursor: pointer; }
        .toolbar { margin-bottom: 20px; display: flex; gap: 10px; align-items: center; justify-content: space-between; }
        .toolbar button, .upload-btn { padding: 8px 12px; border: 1px solid #ccc; background-color: #f0f0f0; cursor: pointer; border-radius: 4px; }
        .toolbar button:hover, .upload-btn:hover { background-color: #e0e0e0; }
        .toolbar-group { display: flex; gap: 10px; }
        #breadcrumb { margin-bottom: 20px; font-size: 1.1em; }
        #breadcrumb a { text-decoration: none; color: #007bff; }
        #breadcrumb a:hover { text-decoration: underline; }
        #no-files-message { text-align: center; color: #888; padding: 20px; }
        .modal { display: none; position: fixed; z-index: 1001; left: 0; top: 0; width: 100%; height: 100%; overflow: auto; background-color: rgba(0,0,0,0.4); }
        .modal-content { background-color: #fefefe; margin: 10% auto; padding: 20px; border: 1px solid #888; width: 80%; max-width: 500px; box-shadow: 0 4px 8px 0 rgba(0,0,0,0.2); }
        #folder-tree { list-style-type: none; padding-left: 0; }
        #folder-tree ul { padding-left: 20px; }
        #folder-tree li { cursor: pointer; padding: 5px; border-radius: 3px; }
        #folder-tree li:hover { background-color: #f0f0f0; }
        #folder-tree .selected-folder { background-color: #d0e0ff; font-weight: bold; }
        #bulk-actions-toolbar { display: none; }
        #file-list li .checkbox-container { margin-right: 15px; display: none; }
        #file-list.select-mode li .checkbox-container { display: block; }
        #file-list li .checkbox-container input { width: 18px; height: 18px; cursor: pointer; }

        #selection-exit-bar {
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            background-color: #007bff;
            color: white;
            text-align: center;
            padding: 15px;
            font-size: 1.2em;
            cursor: pointer;
            z-index: 1002;
            display: none;
        }

        body.select-mode-active #selection-exit-bar {
            display: block;
        }
    </style>
</head>
<body>
    <div id="selection-exit-bar" style="display: none;" onclick="exitSelectMode()">
        <span>Done</span>
    </div>
    <div class="container">
        <h1>File Manager</h1>
        <div class="toolbar">
            <div id="main-toolbar" class="toolbar-group">
                <button onclick="showCreateFolderPrompt()">New Folder</button>
                <input type="file" id="file-upload" multiple style="display: none;" onchange="uploadFiles()">
                <button class="upload-btn" onclick="document.getElementById('file-upload').click()">Upload</button>
            </div>
             <div id="bulk-actions-toolbar" class="toolbar-group">
                <span id="selection-count" style="align-self: center; font-weight: bold;"></span>
                <button onclick="moveSelectedItems()">Move</button>
                <button id="bulk-delete-btn" onclick="deleteSelectedItems()">Delete</button>
                <button onclick="downloadSelectedItems()">Download</button>
                <button onclick="exitSelectMode()">Cancel</button>
            </div>
            <div class="toolbar-group">
                 <a href="/logout" style="text-decoration: none;"><button>Logout</button></a>
                 <button id="settings-btn" onclick="showSettingsModal()">Settings</button>
            </div>
        </div>
        <div id="breadcrumb"></div>
        <ul id="file-list"></ul>
        <div id="no-files-message" style="display: none;">No files in this directory.</div>
    </div>

    <!-- Move Modal -->
    <div id="move-modal" class="modal">
        <div class="modal-content">
            <h2>Select Destination Folder</h2>
            <ul id="folder-tree"></ul>
            <button onclick="confirmMove()">Move Here</button>
            <button onclick="closeMoveModal()">Cancel</button>
        </div>
    </div>

    <!-- Settings Modal -->
    <div id="settings-modal" class="modal">
        <div class="modal-content">
            <h2>Settings</h2>
            <label>
                <input type="checkbox" id="allow-user-delete-checkbox" onchange="updateSettings()">
                Allow non-admin users to delete files
            </label>
            <br><br>
            <button onclick="closeSettingsModal()">Close</button>
        </div>
    </div>

    <script>
        let currentPath = '';
        let selectedItems = new Set();
        let isSelectMode = false;
        let lastSelectedItem = null;
        let longPressTimer;
        let canClick = true;
        let allowUserDelete = true;
        let isAdmin = false;

        document.addEventListener('DOMContentLoaded', () => {
            fetchFiles(currentPath);

            document.addEventListener('click', (e) => {
                const container = document.querySelector('.container');
                if (isSelectMode && !container.contains(e.target)) {
                    exitSelectMode();
                }
            });

            document.addEventListener('keydown', handleKeyDown);
        });

        function handleKeyDown(e) {
            if ((e.ctrlKey || e.metaKey) && e.key === 'a') {
                e.preventDefault();
                if (!isSelectMode) enterSelectMode();
                selectAllVisibleItems();
            } else if (e.key === 'Escape') {
                if (isSelectMode) exitSelectMode();
            }
        }

        function fetchFiles(path) {
            fetch(`/api/files?path=${encodeURIComponent(path)}`)
                .then(response => response.json())
                .then(data => {
                    if (data.error) throw new Error(data.error);
                    currentPath = data.current_path;
                    isAdmin = data.is_admin;
                    allowUserDelete = data.allow_user_delete;
                    updateBreadcrumb(currentPath);
                    renderFileList(data.files);
                    updateUIForPermissions();
                })
                .catch(error => {
                    console.error('Error fetching files:', error);
                    // Fallback to root if path is invalid
                    if (path !== '') fetchFiles('');
                });
        }

        function renderFileList(files) {
            const fileList = document.getElementById('file-list');
            const noFilesMessage = document.getElementById('no-files-message');
            fileList.innerHTML = '';
            fileList.classList.toggle('select-mode', isSelectMode);

            if (files.length === 0) {
                noFilesMessage.style.display = 'block';
            } else {
                noFilesMessage.style.display = 'none';
                files.forEach(file => {
                    const li = document.createElement('li');
                    li.dataset.path = file.path;
                    li.dataset.name = file.name;
                    li.dataset.type = file.type;

                    if (selectedItems.has(file.path)) {
                        li.classList.add('selected');
                    }

                    li.addEventListener('mousedown', (e) => handleItemMouseDown(e, li));
                    li.addEventListener('mouseup', (e) => handleItemMouseUp(e, li));
                    li.addEventListener('mouseleave', () => clearTimeout(longPressTimer));
                    li.addEventListener('click', (e) => handleItemClick(e, li));

                    const checkboxContainer = document.createElement('div');
                    checkboxContainer.className = 'checkbox-container';
                    const checkbox = document.createElement('input');
                    checkbox.type = 'checkbox';
                    checkbox.checked = selectedItems.has(file.path);
                    checkbox.addEventListener('click', (e) => {
                        e.stopPropagation();
                        toggleSelection(li);
                    });
                    checkboxContainer.appendChild(checkbox);

                    const icon = document.createElement('span');
                    icon.className = 'file-icon';
                    icon.textContent = file.type === 'folder' ? '📁' : '📄';

                    const name = document.createElement('span');
                    name.className = 'file-name';
                    name.textContent = file.name;

                    li.appendChild(checkboxContainer);
                    li.appendChild(icon);
                    li.appendChild(name);
                    fileList.appendChild(li);
                });
            }
            updateBulkActionsToolbar();
        }

        function handleItemMouseDown(e, li) {
            if (e.button !== 0 || isSelectMode) return;
            canClick = true;
            longPressTimer = setTimeout(() => {
                canClick = false;
                enterSelectMode();
                toggleSelection(li);
            }, 500);
        }

        function handleItemMouseUp(e, li) {
            clearTimeout(longPressTimer);
        }

        function handleItemClick(e, li) {
            if (!canClick) {
                e.preventDefault();
                e.stopPropagation();
                return;
            }
            const filePath = li.dataset.path;
            const fileType = li.dataset.type;

            if (isSelectMode) {
                if (e.shiftKey && lastSelectedItem) {
                    selectRange(lastSelectedItem, li);
                } else {
                     toggleSelection(li, e.ctrlKey || e.metaKey);
                }
            } else {
                if (fileType === 'folder') {
                    fetchFiles(filePath);
                } else {
                    window.open(`/files/${filePath}`, '_blank');
                }
            }
        }

        function enterSelectMode() {
            if (isSelectMode) return;
            isSelectMode = true;
            document.body.classList.add('select-mode-active');
            document.getElementById('file-list').classList.add('select-mode');
            updateBulkActionsToolbar();
        }

        function exitSelectMode() {
            if (!isSelectMode) return;
            isSelectMode = false;
            document.body.classList.remove('select-mode-active');
            selectedItems.clear();
            lastSelectedItem = null;
            document.getElementById('file-list').classList.remove('select-mode');
            document.querySelectorAll('#file-list li.selected').forEach(item => item.classList.remove('selected'));
            document.querySelectorAll('#file-list input[type="checkbox"]').forEach(cb => cb.checked = false);
            updateBulkActionsToolbar();
        }

        function toggleSelection(li, isCtrlClick = false) {
            if (!isSelectMode) enterSelectMode();

            const path = li.dataset.path;
            const checkbox = li.querySelector('input[type="checkbox"]');
            
            if (selectedItems.has(path)) {
                selectedItems.delete(path);
                li.classList.remove('selected');
                if(checkbox) checkbox.checked = false;
            } else {
                selectedItems.add(path);
                li.classList.add('selected');
                if(checkbox) checkbox.checked = true;
            }

            if (!isCtrlClick) {
                lastSelectedItem = li;
            }
            updateBulkActionsToolbar();
        }

        function selectAllVisibleItems() {
            const allVisibleItems = document.querySelectorAll('#file-list li');
            if (allVisibleItems.length === 0) return;

            const allSelected = allVisibleItems.length === selectedItems.size;

            allVisibleItems.forEach(li => {
                const path = li.dataset.path;
                const checkbox = li.querySelector('input[type="checkbox"]');
                if (allSelected) {
                    selectedItems.delete(path);
                    li.classList.remove('selected');
                    if (checkbox) checkbox.checked = false;
                } else {
                    if (!selectedItems.has(path)) {
                        selectedItems.add(path);
                        li.classList.add('selected');
                        if (checkbox) checkbox.checked = true;
                    }
                }
            });
            lastSelectedItem = allVisibleItems[allVisibleItems.length - 1];
            updateBulkActionsToolbar();
        }

        function selectRange(startLi, endLi) {
            const items = Array.from(document.querySelectorAll('#file-list li'));
            const startIndex = items.indexOf(startLi);
            const endIndex = items.indexOf(endLi);
            if (startIndex === -1 || endIndex === -1) return;

            // Determine the new range of paths that should be selected
            const [min, max] = [Math.min(startIndex, endIndex), Math.max(startIndex, endIndex)];
            const newRangePaths = new Set();
            for (let i = min; i <= max; i++) {
                newRangePaths.add(items[i].dataset.path);
            }

            // Iterate through all items to update their selection state
            items.forEach(li => {
                const path = li.dataset.path;
                const checkbox = li.querySelector('input[type="checkbox"]');
                const shouldBeSelected = newRangePaths.has(path);
                const isSelected = selectedItems.has(path);

                if (shouldBeSelected && !isSelected) {
                    // Add to selection
                    selectedItems.add(path);
                    li.classList.add('selected');
                    if (checkbox) checkbox.checked = true;
                } else if (!shouldBeSelected && isSelected) {
                    // Remove from selection if it was previously selected.
                    // This handles shrinking the selection range.
                    // Note: This simple implementation will also deselect items that were
                    // individually selected with Ctrl+Click if they fall outside the new range.
                    // A more complex implementation would be needed to preserve those.
                    selectedItems.delete(path);
                    li.classList.remove('selected');
                    if (checkbox) checkbox.checked = false;
                }
            });

            lastSelectedItem = endLi;
            updateBulkActionsToolbar();
        }

        function updateBulkActionsToolbar() {
            const bulkActionsToolbar = document.getElementById('bulk-actions-toolbar');
            const mainToolbar = document.getElementById('main-toolbar');
            const selectionCount = document.getElementById('selection-count');

            if (isSelectMode && selectedItems.size > 0) {
                bulkActionsToolbar.style.display = 'flex';
                mainToolbar.style.display = 'none';
                selectionCount.textContent = `${selectedItems.size} selected`;
            } else {
                bulkActionsToolbar.style.display = 'none';
                mainToolbar.style.display = 'flex';
                selectionCount.textContent = '';
                if (!isSelectMode) {
                    // This is handled by exitSelectMode to prevent loops
                }
            }
             updateUIForPermissions();
        }

        function updateUIForPermissions() {
            const deleteButton = document.getElementById('bulk-delete-btn');
            const settingsButton = document.getElementById('settings-btn');
            if (deleteButton) {
                const canDelete = isAdmin || allowUserDelete;
                // Only show delete button in bulk actions if user has permission
                deleteButton.style.display = canDelete ? 'inline-block' : 'none';
            }
            if (settingsButton) {
                settingsButton.style.display = isAdmin ? 'inline-block' : 'none';
            }
        }

        function updateBreadcrumb(path) {
            const breadcrumb = document.getElementById('breadcrumb');
            breadcrumb.innerHTML = '';
            const parts = path.split('/').filter(p => p);
            let homeLink = document.createElement('a');
            homeLink.href = '#';
            homeLink.textContent = 'Home';
            homeLink.onclick = (e) => { e.preventDefault(); fetchFiles(''); };
            breadcrumb.appendChild(homeLink);

            let builtPath = '';
            parts.forEach(part => {
                builtPath += (builtPath ? '/' : '') + part;
                breadcrumb.append(' / ');
                let partLink = document.createElement('a');
                partLink.href = '#';
                partLink.textContent = part;
                // Use a closure to capture the correct path
                partLink.onclick = ((p) => (e) => { e.preventDefault(); fetchFiles(p); })(builtPath);
                breadcrumb.appendChild(partLink);
            });
        }

        function showCreateFolderPrompt() {
            const folderName = prompt("Enter new folder name:");
            if (folderName && folderName.trim()) {
                fetch('/api/create_folder', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ path: currentPath, folder_name: folderName.trim() })
                })
                .then(handleResponse)
                .then(() => fetchFiles(currentPath))
                .catch(handleError);
            }
        }

        function uploadFiles() {
            const files = document.getElementById('file-upload').files;
            if (files.length === 0) return;

            const formData = new FormData();
            formData.append('path', currentPath);
            for (const file of files) {
                formData.append('files[]', file);
            }

            fetch('/api/upload', {
                method: 'POST',
                body: formData
            })
            .then(handleResponse)
            .then(() => {
                document.getElementById('file-upload').value = ''; // Reset input
                fetchFiles(currentPath);
            })
            .catch(handleError);
        }

        function deleteSelectedItems() {
            if (selectedItems.size === 0) return;
            if (!confirm(`Are you sure you want to delete ${selectedItems.size} item(s)?`)) return;

            fetch('/api/delete', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ items: Array.from(selectedItems) })
            })
            .then(handleResponse)
            .then(() => {
                exitSelectMode();
                fetchFiles(currentPath);
            })
            .catch(handleError);
        }

        function downloadSelectedItems() {
            if (selectedItems.size === 0) return;

            fetch('/api/download_zip', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ items: Array.from(selectedItems) })
            })
            .then(response => {
                if (response.ok) {
                    const disposition = response.headers.get('Content-Disposition');
                    let filename = 'archive.zip';
                    if (disposition && disposition.indexOf('attachment') !== -1) {
                        const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
                        const matches = filenameRegex.exec(disposition);
                        if (matches != null && matches[1]) {
                            filename = matches[1].replace(/['"]/g, '');
                        }
                    }
                    return response.blob().then(blob => ({ blob, filename }));
                } else {
                    return response.json().then(err => { throw new Error(err.error || 'Download failed') });
                }
            })
            .then(({ blob, filename }) => {
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                exitSelectMode();
            })
            .catch(handleError);
        }


        let itemsToMove = [];
        function moveSelectedItems() {
            if (selectedItems.size === 0) return;
            itemsToMove = Array.from(selectedItems);

            fetch('/api/get_folder_tree')
                .then(response => response.json())
                .then(tree => {
                    const treeElement = document.getElementById('folder-tree');
                    treeElement.innerHTML = '';
                    const rootNode = document.createElement('li');
                    rootNode.textContent = 'Home (root)';
                    rootNode.dataset.path = '';
                    rootNode.onclick = (e) => selectFolder(e, rootNode);
                    treeElement.appendChild(rootNode);

                    buildFolderTree(tree, treeElement);
                    document.getElementById('move-modal').style.display = 'block';
                })
                .catch(handleError);
        }

        function buildFolderTree(nodes, parentElement) {
            const ul = document.createElement('ul');
            nodes.forEach(node => {
                const li = document.createElement('li');
                li.textContent = node.name;
                li.dataset.path = node.path;
                li.onclick = (e) => selectFolder(e, li);
                if (node.children && node.children.length > 0) {
                    buildFolderTree(node.children, li);
                }
                ul.appendChild(li);
            });
            parentElement.appendChild(ul);
        }

        let selectedDestination = '';
        function selectFolder(event, element) {
            event.stopPropagation();
            document.querySelectorAll('#folder-tree .selected-folder').forEach(el => el.classList.remove('selected-folder'));
            element.classList.add('selected-folder');
            selectedDestination = element.dataset.path;
        }

        function confirmMove() {
            if (selectedDestination === null || selectedDestination === undefined) {
                alert("Please select a destination folder.");
                return;
            }
            fetch('/api/move', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ items: itemsToMove, destination: selectedDestination })
            })
            .then(handleResponse)
            .then(() => {
                closeMoveModal();
                exitSelectMode();
                fetchFiles(currentPath);
            })
            .catch(handleError);
        }

        function closeMoveModal() {
            document.getElementById('move-modal').style.display = 'none';
            selectedDestination = '';
        }

        function showSettingsModal() {
            fetch('/api/settings')
                .then(response => response.json())
                .then(settings => {
                    document.getElementById('allow-user-delete-checkbox').checked = settings.allow_user_delete;
                    document.getElementById('settings-modal').style.display = 'block';
                }).catch(handleError);
        }

        function closeSettingsModal() {
            document.getElementById('settings-modal').style.display = 'none';
        }

        function updateSettings() {
            const allowDelete = document.getElementById('allow-user-delete-checkbox').checked;
            fetch('/api/settings', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ allow_user_delete: allowDelete })
            })
            .then(handleResponse)
            .catch(handleError);
        }

        function handleResponse(response) {
            return response.json().then(data => {
                if (!response.ok) {
                    throw new Error(data.error || `HTTP error! status: ${response.status}`);
                }
                return data;
            });
        }

        function handleError(error) {
            console.error('API Error:', error);
            alert(`An error occurred: ${error.message}`);
        }

    </script>
</body>
</html>
"""

@app.route('/')
@login_required
def index():
    return render_template_string(TEMPLATE_HTML)

@app.route('/api/files')
@login_required
def list_files():
    try:
        directory = request.args.get('path', '')
        # Prevent directory traversal attacks
        safe_path = os.path.abspath(os.path.join(FILES_DIRECTORY, directory))
        if not safe_path.startswith(os.path.abspath(FILES_DIRECTORY)):
            return jsonify({"error": "Access denied"}), 403

        current_path = os.path.join(FILES_DIRECTORY, directory)

        if not os.path.exists(current_path) or not os.path.isdir(current_path):
             # If a non-existent path is requested, default to root
            current_path = FILES_DIRECTORY
            directory = ''

        items = []
        for item in sorted(os.listdir(current_path), key=lambda x: (os.path.isfile(os.path.join(current_path, x)), x.lower())):
            item_path = os.path.join(current_path, item)
            item_type = 'folder' if os.path.isdir(item_path) else 'file'
            items.append({'name': item, 'type': item_type, 'path': os.path.join(directory, item)})

        is_admin = user_roles.get(session.get('username')) == 'admin'

        return jsonify({
            'files': items,
            'current_path': directory,
            'is_admin': is_admin,
            'allow_user_delete': admin_settings['allow_user_delete']
        })
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        return jsonify({"error": "An internal error occurred"}), 500

@app.route('/api/upload', methods=['POST'])
@login_required
def upload_file():
    try:
        path = request.form.get('path', '')
        target_folder = os.path.join(FILES_DIRECTORY, path)

        if not os.path.exists(target_folder) or not os.path.isdir(target_folder):
            return jsonify({"error": "Target directory does not exist."}), 400

        if 'files[]' not in request.files:
            return jsonify({"error": "No file part"}), 400

        files = request.files.getlist('files[]')
        for file in files:
            if file.filename == '':
                continue
            filename = secure_filename(file.filename)
            file.save(os.path.join(target_folder, filename))

        return jsonify({"success": "Files uploaded successfully"})
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        return jsonify({"error": "An internal error occurred"}), 500

@app.route('/api/create_folder', methods=['POST'])
@login_required
def create_folder():
    try:
        data = request.get_json()
        path = data.get('path', '')
        folder_name = data.get('folder_name')

        if not folder_name or not folder_name.strip():
            return jsonify({"error": "Folder name cannot be empty."}), 400

        folder_name = secure_filename(folder_name)
        new_folder_path = os.path.join(FILES_DIRECTORY, path, folder_name)

        if os.path.exists(new_folder_path):
            return jsonify({"error": "A folder with this name already exists."}), 400

        os.makedirs(new_folder_path)
        return jsonify({"success": "Folder created successfully"})
    except Exception as e:
        logger.error(f"Error creating folder: {e}")
        return jsonify({"error": "An internal error occurred"}), 500

@app.route('/api/delete', methods=['POST'])
@login_required
def delete_items():
    is_admin = user_roles.get(session.get('username')) == 'admin'
    if not is_admin and not admin_settings['allow_user_delete']:
        return jsonify({"error": "You do not have permission to delete files."}), 403

    try:
        data = request.get_json()
        items = data.get('items', [])
        if not items:
            return jsonify({"error": "No items selected for deletion."}), 400

        for item_path in items:
            full_path = os.path.join(FILES_DIRECTORY, item_path)
            # Security check
            if not os.path.abspath(full_path).startswith(os.path.abspath(FILES_DIRECTORY)):
                continue
            if os.path.exists(full_path):
                if os.path.isdir(full_path):
                    shutil.rmtree(full_path)
                else:
                    os.remove(full_path)

        return jsonify({"success": "Items deleted successfully"})
    except Exception as e:
        logger.error(f"Error deleting items: {e}")
        return jsonify({"error": "An internal error occurred"}), 500

@app.route('/api/move', methods=['POST'])
@login_required
def move_items():
    try:
        data = request.get_json()
        items = data.get('items', [])
        destination = data.get('destination', '')

        if not items:
            return jsonify({"error": "No items selected for moving."}), 400

        destination_path = os.path.join(FILES_DIRECTORY, destination)
        if not os.path.exists(destination_path) or not os.path.isdir(destination_path):
            return jsonify({"error": "Destination folder does not exist."}), 400

        for item_path in items:
            source_full_path = os.path.join(FILES_DIRECTORY, item_path)
            item_name = os.path.basename(item_path)
            destination_full_path = os.path.join(destination_path, item_name)

            if os.path.abspath(source_full_path) == os.path.abspath(destination_full_path):
                continue

            if os.path.exists(destination_full_path):
                 return jsonify({"error": f"An item named '{item_name}' already exists in the destination."}), 400

            if os.path.exists(source_full_path):
                shutil.move(source_full_path, destination_full_path)

        return jsonify({"success": "Items moved successfully"})
    except Exception as e:
        logger.error(f"Error moving items: {e}")
        return jsonify({"error": "An internal error occurred"}), 500

@app.route('/api/download_zip', methods=['POST'])
@login_required
def download_zip():
    try:
        data = request.get_json()
        items_to_zip = data.get('items', [])

        if not items_to_zip:
            return jsonify({"error": "No items to download"}), 400

        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for item_path in items_to_zip:
                full_path = os.path.join(FILES_DIRECTORY, item_path)
                if os.path.exists(full_path):
                    if os.path.isdir(full_path):
                        # Add folder contents recursively
                        for root, _, files in os.walk(full_path):
                            for file in files:
                                file_path = os.path.join(root, file)
                                # Path in zip should be relative to the folder being zipped
                                archive_path = os.path.relpath(file_path, os.path.join(FILES_DIRECTORY, os.path.dirname(item_path)))
                                zf.write(file_path, archive_path)
                    else: # it's a file
                        # Add file with its name
                        zf.write(full_path, os.path.basename(item_path))

        memory_file.seek(0)
        zip_filename = "archive.zip"
        if len(items_to_zip) == 1:
            base_name = os.path.basename(items_to_zip[0])
            name, _ = os.path.splitext(base_name)
            zip_filename = f"{name}.zip"

        return send_file(memory_file, download_name=zip_filename, as_attachment=True, mimetype='application/zip')

    except Exception as e:
        logger.error(f"Error creating zip file: {e}")
        return jsonify({"error": "Failed to create zip file."}), 500


@app.route('/api/settings', methods=['GET', 'POST'])
@admin_required
def settings():
    if request.method == 'POST':
        data = request.get_json()
        if 'allow_user_delete' in data:
            admin_settings['allow_user_delete'] = bool(data['allow_user_delete'])
        return jsonify({"success": True, "settings": admin_settings})
    return jsonify(admin_settings)

@app.route('/files/<path:filename>')
@login_required
def serve_file(filename):
    return send_from_directory(FILES_DIRECTORY, filename)

@app.route('/api/get_folder_tree', methods=['GET'])
@login_required
def get_folder_tree():
    def build_tree(path, rel_path=""):
        tree = []
        try:
            # Sort items alphabetically, folders first
            items = sorted(os.listdir(path), key=lambda x: (os.path.isfile(os.path.join(path, x)), x.lower()))
            for item in items:
                item_full_path = os.path.join(path, item)
                item_rel_path = os.path.join(rel_path, item)
                if os.path.isdir(item_full_path):
                    node = {
                        "name": item,
                        "path": item_rel_path,
                        "children": build_tree(item_full_path, item_rel_path)
                    }
                    tree.append(node)
        except OSError:
            pass # Ignore permission errors
        return tree

    folder_tree = build_tree(FILES_DIRECTORY)
    return jsonify(folder_tree)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
