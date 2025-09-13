document.addEventListener('DOMContentLoaded', async () => {
    const goLocalBtn = document.getElementById('goLocalBtn');
    const goServerBtn = document.getElementById('goServerBtn');
    const settingsBtn = document.getElementById('settingsBtn');
    const saveAppSettingsBtn = document.getElementById('saveAppSettingsBtn');
    const localUrlInput = document.getElementById('localUrlInput');
    const serverUrlInput = document.getElementById('serverUrlInput');

    let apiToken = null;

    async function updateButtonLinks(config) {
        if (!apiToken) {
            showToast('API Token not found. Please set one up in the main app settings.', 'warning');
        }

        const loginUrlSuffix = apiToken ? `/login?token=${encodeURIComponent(apiToken)}` : '';

        if (config.local_url) {
            goLocalBtn.href = new URL(loginUrlSuffix, config.local_url).href;
            goLocalBtn.disabled = !apiToken;
        } else {
            goLocalBtn.href = '#';
            goLocalBtn.disabled = true;
        }

        if (config.server_url) {
            goServerBtn.href = new URL(loginUrlSuffix, config.server_url).href;
            goServerBtn.disabled = !apiToken;
        } else {
            goServerBtn.href = '#';
            goServerBtn.disabled = true;
        }
    }

    async function initialize() {
        try {
            await window.fileDB.initDB();
            apiToken = await window.fileDB.getConfigValue('api_token');
            const config = await window.appConfigManager.loadConfig();
            await updateButtonLinks(config);
        } catch (e) {
            console.error("Failed to initialize launcher:", e);
            showToast('Could not load configuration or token.', 'error');
        }
    }

    // Settings modal logic
    if (settingsBtn) {
        settingsBtn.addEventListener('click', () => {
            const config = window.appConfigManager.getConfig();
            if (localUrlInput) localUrlInput.value = config.local_url;
            if (serverUrlInput) serverUrlInput.value = config.server_url;
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
            await updateButtonLinks(newConfig);
            showToast('Settings saved!', 'success');
            closeModal('appSettingsModal');
        });
    }

    initialize();
});
