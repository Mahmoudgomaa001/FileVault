// --- IndexedDB for File Storage ---

const DB_NAME = 'pwa-file-storage';
const FILE_STORE = 'files';
const CONFIG_STORE = 'config';
let db;

/**
 * Initializes the IndexedDB database.
 * @returns {Promise<IDBDatabase>} A promise that resolves with the database object.
 */
function initDB() {
  return new Promise((resolve, reject) => {
    if (db) {
      return resolve(db);
    }
    // Increment version to 2 to trigger onupgradeneeded for new store
    const request = indexedDB.open(DB_NAME, 2);

    request.onerror = (event) => {
      console.error('Database error:', event.target.error);
      reject('Database error');
    };

    request.onsuccess = (event) => {
      db = event.target.result;
      console.log('Database opened successfully.');
      resolve(db);
    };

    request.onupgradeneeded = (event) => {
      const dbInstance = event.target.result;
      if (!dbInstance.objectStoreNames.contains(FILE_STORE)) {
        dbInstance.createObjectStore(FILE_STORE, { keyPath: 'id', autoIncrement: true });
        console.log('Object store "files" created.');
      }
      if (!dbInstance.objectStoreNames.contains(CONFIG_STORE)) {
        // This store will hold key-value pairs, e.g., { key: 'api_token', value: '...' }
        dbInstance.createObjectStore(CONFIG_STORE, { keyPath: 'key' });
        console.log('Object store "config" created.');
      }
    };
  });
}

/**
 * Saves or updates a configuration value in the config store.
 * @param {string} key - The key for the config value (e.g., 'api_token').
 * @param {*} value - The value to store.
 * @returns {Promise<void>}
 */
function saveConfigValue(key, value) {
    return new Promise((resolve, reject) => {
        initDB().then(db => {
            const transaction = db.transaction([CONFIG_STORE], 'readwrite');
            const store = transaction.objectStore(CONFIG_STORE);
            const request = store.put({ key: key, value: value });
            request.onsuccess = () => resolve();
            request.onerror = (event) => reject('Error saving config value: ' + event.target.error);
        });
    });
}

/**
 * Retrieves a configuration value from the config store.
 * @param {string} key - The key of the config value to retrieve.
 * @returns {Promise<*>} A promise that resolves with the stored value or undefined.
 */
function getConfigValue(key) {
    return new Promise((resolve, reject) => {
        initDB().then(db => {
            const transaction = db.transaction([CONFIG_STORE], 'readonly');
            const store = transaction.objectStore(CONFIG_STORE);
            const request = store.get(key);
            request.onsuccess = (event) => {
                resolve(event.target.result ? event.target.result.value : undefined);
            };
            request.onerror = (event) => reject('Error getting config value: ' + event.target.error);
        });
    });
}

/**
 * Saves a file to the IndexedDB.
 * @param {File} file - The file object to save.
 * @returns {Promise<number>} A promise that resolves with the ID of the saved file.
 */
function saveFile(file) {
  return new Promise((resolve, reject) => {
    initDB().then(db => {
      const transaction = db.transaction([FILE_STORE], 'readwrite');
      const store = transaction.objectStore(FILE_STORE);
      const request = store.add({ file: file, name: file.name, size: file.size });

      request.onsuccess = (event) => {
        resolve(event.target.result);
      };

      request.onerror = (event) => {
        console.error('Error saving file:', event.target.error);
        reject('Error saving file');
      };
    });
  });
}

/**
 * Retrieves all files from the IndexedDB.
 * @returns {Promise<Array<object>>} A promise that resolves with an array of file objects.
 */
function getFiles() {
  return new Promise((resolve, reject) => {
    initDB().then(db => {
      const transaction = db.transaction([FILE_STORE], 'readonly');
      const store = transaction.objectStore(FILE_STORE);
      const request = store.getAll();

      request.onsuccess = (event) => {
        resolve(event.target.result);
      };

      request.onerror = (event) => {
        console.error('Error getting files:', event.target.error);
        reject('Error getting files');
      };
    });
  });
}

/**
 * Deletes a file from IndexedDB by its ID.
 * @param {number} id - The ID of the file to delete.
 * @returns {Promise<void>}
 */
function deleteFile(id) {
  return new Promise((resolve, reject) => {
    initDB().then(db => {
      const transaction = db.transaction([FILE_STORE], 'readwrite');
      const store = transaction.objectStore(FILE_STORE);
      const request = store.delete(id);

      request.onsuccess = () => {
        resolve();
      };
      request.onerror = (event) => {
        reject('Error deleting file: ' + event.target.error);
      };
    });
  });
}


/**
 * Clears all files from the IndexedDB object store.
 * @returns {Promise<void>}
 */
function clearFiles() {
  return new Promise((resolve, reject) => {
    initDB().then(db => {
      const transaction = db.transaction([FILE_STORE], 'readwrite');
      const store = transaction.objectStore(FILE_STORE);
      const request = store.clear();

      request.onsuccess = () => {
        console.log('All files cleared from IndexedDB.');
        resolve();
      };

      request.onerror = (event) => {
        console.error('Error clearing files:', event.target.error);
        reject('Error clearing files');
      };
    });
  });
}

window.fileDB = {
  initDB,
  saveFile,
  getFiles,
  deleteFile,
  clearFiles,
  saveConfigValue,
  getConfigValue
};
