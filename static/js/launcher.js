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

        // The "Connect to Server" button is a simple link, but we can also use the token for a seamless login.
        if (config.server_url) {
            const loginUrl = new URL('/login', config.server_url);
            if (apiToken) loginUrl.searchParams.set('token', apiToken);
            goServerBtn.href = loginUrl.href;
            goServerBtn.disabled = false;
        } else {
            goServerBtn.href = '#';
            goServerBtn.disabled = true;
        }

        // The "Connect to Local" button passes all the necessary config and tokens.
        if (config.local_url) {
            const loginUrl = new URL('/login_and_sync', config.local_url);
            if (apiToken) loginUrl.searchParams.set('token', apiToken);
            if (config.server_url) loginUrl.searchParams.set('remote_server_url', config.server_url);
            // Pass the local URL itself so the main app knows its own address
            loginUrl.searchParams.set('local_url', config.local_url);

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
