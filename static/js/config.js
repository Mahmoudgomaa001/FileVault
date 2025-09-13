// --- Configuration Management using IndexedDB ---

// In-memory cache of the config
let appConfig = {
  local_url: '',
  server_url: ''
};

/**
 * Loads configuration (local_url, server_url) from IndexedDB.
 * This is the single source of truth for PWA configuration.
 * @returns {Promise<object>} A promise that resolves with the configuration object.
 */
async function loadConfig() {
  try {
    // db.js must be loaded before this file.
    if (!window.fileDB) throw new Error("fileDB is not available.");

    await window.fileDB.initDB();
    const local_url = await window.fileDB.getConfigValue('local_url');
    const server_url = await window.fileDB.getConfigValue('server_url');

    appConfig = {
        local_url: local_url || '',
        server_url: server_url || ''
    };
    console.log('Configuration loaded from IndexedDB:', appConfig);
    return appConfig;
  } catch (error) {
    console.error('Could not load configuration from IndexedDB:', error);
    // Return default empty config on failure
    return appConfig;
  }
}

/**
 * Returns the currently loaded configuration from the in-memory cache.
 * @returns {object} The application configuration.
 */
function getConfig() {
  return appConfig;
}

/**
 * Saves the configuration object to IndexedDB.
 * @param {object} newConfig - The configuration object to save. Must have local_url and server_url.
 * @returns {Promise<void>}
 */
async function saveConfig(newConfig) {
    try {
        if (!window.fileDB) throw new Error("fileDB is not available.");
        await window.fileDB.initDB();

        // Use Promise.all to save both values concurrently.
        await Promise.all([
            window.fileDB.saveConfigValue('local_url', newConfig.local_url || ''),
            window.fileDB.saveConfigValue('server_url', newConfig.server_url || '')
        ]);

        // Update the in-memory config object
        appConfig = { ...appConfig, ...newConfig };
        console.log('Configuration saved to IndexedDB:', appConfig);
    } catch (error) {
        console.error('Failed to save config to IndexedDB:', error);
        throw error; // Re-throw so the caller knows it failed
    }
}

// Expose functions to the global scope
window.appConfigManager = {
  loadConfig,
  getConfig,
  saveConfig
};
