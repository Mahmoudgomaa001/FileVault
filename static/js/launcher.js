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

        // The "Connect to Server" button is a simple link.
        if (config.server_url) {
            goServerBtn.href = config.server_url;
            goServerBtn.disabled = false;
        } else {
            goServerBtn.href = '#';
            goServerBtn.disabled = true;
        }

        // The "Connect to Local" button is special. It passes the config and token
        // to the local instance so it can fetch pending files from the server origin.
        if (config.local_url) {
            const remoteConfig = `&remote_server_url=${encodeURIComponent(config.server_url)}&remote_api_token=${encodeURIComponent(apiToken)}`;
            const loginUrl = new URL('/login_and_sync', config.local_url);
            loginUrl.search = `?token=${encodeURIComponent(apiToken)}${remoteConfig}`;

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
