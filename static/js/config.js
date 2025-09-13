// --- Configuration Management ---

const CONFIG_CACHE_KEY = '/config.json';
let appConfig = {
  local_url: '',
  server_url: ''
};

/**
 * Fetches the configuration, prioritizing the cached version.
 * If not cached, fetches from the network and caches it via the service worker.
 * @returns {Promise<object>} A promise that resolves with the configuration object.
 */
async function loadConfig() {
  try {
    // We request '/config.json', which is intercepted by the service worker.
    const response = await fetch(CONFIG_CACHE_KEY, { cache: 'no-store' });
    if (!response.ok) {
      throw new Error(`Failed to fetch config, status: ${response.status}`);
    }
    const config = await response.json();
    if (config.ok) {
        appConfig = {
            local_url: config.local_url,
            server_url: config.server_url
        };
        console.log('Configuration loaded:', appConfig);
        return appConfig;
    } else {
        throw new Error('Config response was not ok');
    }
  } catch (error) {
    console.error('Could not load configuration:', error);
    // Return default empty config on failure
    return appConfig;
  }
}

/**
 * Returns the currently loaded configuration.
 * @returns {object} The application configuration.
 */
function getConfig() {
  return appConfig;
}

/**
 * Updates the configuration and messages the service worker to cache the new version.
 * @param {object} newConfig - The new configuration object to save.
 * @returns {Promise<void>}
 */
async function saveConfig(newConfig) {
    appConfig = { ...appConfig, ...newConfig };
    console.log('Saving new configuration:', appConfig);

    // To "save" the config, we create a new Response object with the updated config
    // and put it into the cache, overwriting the old /config.json.
    // This is a client-side only operation; we are not talking to the server here.
    try {
        const cache = await caches.open('filevault-cache-v9'); // Ensure this matches SW cache name
        const configResponse = new Response(JSON.stringify({ ok: true, ...appConfig }), {
            headers: { 'Content-Type': 'application/json' }
        });
        await cache.put(CONFIG_CACHE_KEY, configResponse);
        console.log('Configuration updated in cache.');
    } catch (error) {
        console.error('Failed to update config in cache:', error);
    }
}

// Expose functions to the global scope if needed, or use as a module.
window.appConfigManager = {
  loadConfig,
  getConfig,
  saveConfig
};
