document.addEventListener('DOMContentLoaded', async () => {
    const openAppBtn = document.getElementById('openAppBtn');
    const settingsBtn = document.getElementById('settingsBtn');
    const saveAppSettingsBtn = document.getElementById('saveAppSettingsBtn');
    const localUrlInput = document.getElementById('localUrlInput');
    const serverUrlInput = document.getElementById('serverUrlInput');

    function updateButtonLinks(config) {
        // The launcher now *always* opens the server_url to ensure a consistent origin.
        // The choice to upload to local or server happens inside the app.
        if (config.server_url) {
            openAppBtn.href = config.server_url;
            openAppBtn.disabled = false;
        } else {
            openAppBtn.href = '#';
            openAppBtn.disabled = true;
            openAppBtn.textContent = 'Configure Server URL in Settings';
        }
    }

    // Load config and update UI
    try {
        const config = await window.appConfigManager.loadConfig();
        updateButtonLinks(config);
    } catch (e) {
        console.error("Failed to load initial config", e);
        showToast('Could not load configuration.', 'error');
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
            updateButtonLinks(newConfig); // Update buttons immediately
            showToast('Settings saved!', 'success');
            closeModal('appSettingsModal');
        });
    }
});
