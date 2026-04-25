import { initializeApp } from "firebase/app";
import { getAuth, GoogleAuthProvider, browserLocalPersistence, setPersistence } from "firebase/auth";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID
};

// Initialize Firebase
let app;
try {
  if (firebaseConfig.apiKey) {
    app = initializeApp(firebaseConfig);
  }
} catch (error) {
  // Silent fail or minimal log for production
  console.error("Firebase Init Failed");
}

export const auth = app ? getAuth(app) : null;

if (auth) {
  setPersistence(auth, browserLocalPersistence).catch(() => {});
}

export const googleProvider = new GoogleAuthProvider();
// Force account selection every time for clarity
googleProvider.setCustomParameters({
  prompt: 'select_account'
});
