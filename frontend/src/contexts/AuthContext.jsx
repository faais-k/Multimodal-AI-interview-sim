import { createContext, useContext, useEffect, useState } from "react";
import { auth } from "../firebase";
import { onAuthStateChanged, signInWithPopup, GoogleAuthProvider, signOut } from "firebase/auth";
import { googleProvider } from "../firebase";

const AuthContext = createContext();

export function useAuth() {
  return useContext(AuthContext);
}

export function AuthProvider({ children }) {
  const [currentUser, setCurrentUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  async function loginWithGoogle() {
    if (!auth) {
      const msg = "Firebase not initialized. Check your Vercel env vars.";
      setError(msg);
      alert(msg);
      return;
    }

    try {
      setError(null);
      // INSTANT POPUP to avoid browser blockers
      console.log("🚀 Opening Google Login Popup...");
      const result = await signInWithPopup(auth, googleProvider);
      console.log("✅ Popup success! User:", result.user.email);
      return result;
    } catch (err) {
      console.error("❌ Login Error:", err);
      if (err.code === "auth/popup-blocked") {
        const msg = "Popup blocked! Please allow popups for this site (check your address bar).";
        setError(msg);
        alert(msg);
      } else {
        setError(err.message);
      }
    }
  }

  function logout() {
    if (!auth) return;
    return signOut(auth);
  }

  useEffect(() => {
    if (!auth) {
      console.warn("⚠️ Auth context initialized without Firebase Auth.");
      setLoading(false);
      return;
    }

    console.log("🕒 AuthProvider starting listener...");
    const unsubscribe = onAuthStateChanged(auth, async (user) => {
      console.log("👤 Auth State Changed:", user ? `Logged in: ${user.email}` : "Logged out");
      setCurrentUser(user);
      
      if (user) {
        const token = await user.getIdToken();
        localStorage.setItem("firebaseToken", token);
      } else {
        localStorage.removeItem("firebaseToken");
      }
      
      setLoading(false);
      console.log("🏁 Auth loading finished.");
    });

    return unsubscribe;
  }, []);

  const value = {
    currentUser,
    loginWithGoogle,
    logout,
    loading,
    error
  };

  return (
    <AuthContext.Provider value={value}>
      {!loading && children}
    </AuthContext.Provider>
  );
}
