/**
 * Guest Interview Storage - IndexedDB
 * 
 * Provides persistent storage for guest users' interview history.
 * Falls back to localStorage if IndexedDB unavailable.
 */

const DB_NAME = 'ascent_guest_db';
const DB_VERSION = 1;
const STORE_NAME = 'interviews';

let dbPromise = null;

function openDB() {
  if (dbPromise) return dbPromise;
  
  if (!('indexedDB' in window)) {
    console.warn('IndexedDB not supported, falling back to localStorage');
    return Promise.resolve(null);
  }
  
  dbPromise = new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    
    request.onerror = () => {
      console.warn('IndexedDB open failed, falling back to localStorage');
      resolve(null);
    };
    
    request.onsuccess = () => resolve(request.result);
    
    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        const store = db.createObjectStore(STORE_NAME, { keyPath: 'session_id' });
        store.createIndex('saved_at', 'saved_at', { unique: false });
      }
    };
  });
  
  return dbPromise;
}

// Fallback localStorage key
const FALLBACK_KEY = 'ascent_guest_interviews';

function getFallback() {
  try {
    const data = localStorage.getItem(FALLBACK_KEY);
    return data ? JSON.parse(data) : [];
  } catch {
    return [];
  }
}

function setFallback(interviews) {
  try {
    localStorage.setItem(FALLBACK_KEY, JSON.stringify(interviews));
  } catch (e) {
    console.warn('Failed to save to localStorage:', e);
  }
}

/**
 * Save an interview report for a guest user
 */
export async function saveGuestInterview(sessionId, reportData) {
  const interview = {
    session_id: sessionId,
    report: reportData,
    saved_at: new Date().toISOString(),
  };
  
  const db = await openDB();
  
  if (!db) {
    // Fallback to localStorage
    const existing = getFallback();
    const filtered = existing.filter(i => i.session_id !== sessionId);
    filtered.unshift(interview); // Add to beginning (newest first)
    // Keep only last 50
    if (filtered.length > 50) filtered.pop();
    setFallback(filtered);
    return;
  }
  
  return new Promise((resolve, reject) => {
    const transaction = db.transaction([STORE_NAME], 'readwrite');
    const store = transaction.objectStore(STORE_NAME);
    
    const request = store.put(interview);
    
    request.onsuccess = () => resolve();
    request.onerror = () => {
      console.warn('IndexedDB save failed, falling back to localStorage');
      const existing = getFallback();
      const filtered = existing.filter(i => i.session_id !== sessionId);
      filtered.unshift(interview);
      if (filtered.length > 50) filtered.pop();
      setFallback(filtered);
      resolve();
    };
  });
}

/**
 * Get all interview history for a guest user
 */
export async function getGuestHistory() {
  const db = await openDB();
  
  if (!db) {
    return getFallback();
  }
  
  return new Promise((resolve) => {
    const transaction = db.transaction([STORE_NAME], 'readonly');
    const store = transaction.objectStore(STORE_NAME);
    const index = store.index('saved_at');
    
    const request = index.openCursor(null, 'prev'); // Descending order
    const results = [];
    
    request.onsuccess = (event) => {
      const cursor = event.target.result;
      if (cursor && results.length < 50) {
        results.push(cursor.value);
        cursor.continue();
      } else {
        resolve(results);
      }
    };
    
    request.onerror = () => {
      console.warn('IndexedDB read failed, falling back to localStorage');
      resolve(getFallback());
    };
  });
}

/**
 * Delete a specific guest interview
 */
export async function deleteGuestInterview(sessionId) {
  const db = await openDB();
  
  if (!db) {
    const existing = getFallback();
    const filtered = existing.filter(i => i.session_id !== sessionId);
    setFallback(filtered);
    return;
  }
  
  return new Promise((resolve) => {
    const transaction = db.transaction([STORE_NAME], 'readwrite');
    const store = transaction.objectStore(STORE_NAME);
    
    const request = store.delete(sessionId);
    request.onsuccess = () => resolve();
    request.onerror = () => {
      // Fallback
      const existing = getFallback();
      const filtered = existing.filter(i => i.session_id !== sessionId);
      setFallback(filtered);
      resolve();
    };
  });
}

/**
 * Clear all guest interview history
 */
export async function clearGuestHistory() {
  const db = await openDB();
  
  if (!db) {
    localStorage.removeItem(FALLBACK_KEY);
    return;
  }
  
  return new Promise((resolve) => {
    const transaction = db.transaction([STORE_NAME], 'readwrite');
    const store = transaction.objectStore(STORE_NAME);
    
    const request = store.clear();
    request.onsuccess = () => {
      localStorage.removeItem(FALLBACK_KEY);
      resolve();
    };
    request.onerror = () => {
      localStorage.removeItem(FALLBACK_KEY);
      resolve();
    };
  });
}
