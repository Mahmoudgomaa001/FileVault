// --- IndexedDB for File Storage ---

const DB_NAME = 'pwa-file-storage';
const STORE_NAME = 'files';
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
    const request = indexedDB.open(DB_NAME, 1);

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
      if (!dbInstance.objectStoreNames.contains(STORE_NAME)) {
        dbInstance.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true });
        console.log('Object store "files" created.');
      }
    };
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
      const transaction = db.transaction([STORE_NAME], 'readwrite');
      const store = transaction.objectStore(STORE_NAME);
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
      const transaction = db.transaction([STORE_NAME], 'readonly');
      const store = transaction.objectStore(STORE_NAME);
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
      const transaction = db.transaction([STORE_NAME], 'readwrite');
      const store = transaction.objectStore(STORE_NAME);
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
      const transaction = db.transaction([STORE_NAME], 'readwrite');
      const store = transaction.objectStore(STORE_NAME);
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
  clearFiles
};
