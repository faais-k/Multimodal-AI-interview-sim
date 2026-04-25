import { initializeApp } from "firebase/app";
import { getAuth, GoogleAuthProvider, browserLocalPersistence, setPersistence } from "firebase/auth";

// Your web app's Firebase configuration
const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID
};

console.log("🔥 Firebase Config Loaded:", {
  projectId: firebaseConfig.projectId,
  hasApiKey: !!firebaseConfig.apiKey,
  authDomain: firebaseConfig.authDomain
});

// Initialize Firebase
let app;
try {
  if (!firebaseConfig.apiKey) {
    throw new Error("Firebase API Key is missing. Check your environment variables.");
  }
  app = initializeApp(firebaseConfig);
} catch (error) {
  console.error("Firebase Initialization Error:", error);
}

export const auth = app ? getAuth(app) : null;

if (auth) {
  setPersistence(auth, browserLocalPersistence)
    .then(() => console.log("✅ Auth persistence set to LOCAL"))
    .catch((err) => console.error("❌ Auth persistence error:", err));
}

export const googleProvider = new GoogleAuthProvider();
