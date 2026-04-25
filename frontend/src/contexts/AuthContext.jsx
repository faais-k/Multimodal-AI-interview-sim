import { createContext, useContext, useEffect, useState } from "react";
import { auth, googleProvider } from "../firebase";
import { onAuthStateChanged, signInWithPopup, signInWithRedirect, getRedirectResult, signOut } from "firebase/auth";

const AuthContext = createContext();

export function useAuth() {
  return useContext(AuthContext);
}

export function AuthProvider({ children }) {
  const [currentUser, setCurrentUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  async function loginWithGoogle() {
    try {
      setError(null);
      // 1. TRIGGER POPUP IMMEDIATELY (Zero delay for browser trust)
      console.log("🚀 Attempting Popup Login...");
      const result = await signInWithPopup(auth, googleProvider);
      console.log("✅ Popup success!");
      return result;
    } catch (err) {
      console.error("❌ Auth Error:", err);
      
      // 2. FALLBACK: If popup is blocked, use Redirect
      if (err.code === "auth/popup-blocked" || err.code === "auth/cancelled-popup-request") {
        console.log("⚠️ Popup blocked/interrupted, falling back to redirect...");
        alert("Popup was blocked or closed. Switching to Redirect login...");
        return signInWithRedirect(auth, googleProvider);
      }
      
      setError(err.message);
    }
  }

  function logout() {
    if (!auth) return;
    return signOut(auth);
  }

  useEffect(() => {
    if (!auth) {
      setLoading(false);
      return;
    }

    // RESCUE LOGIC: Check if we just returned from a redirect
    console.log("🕒 AuthProvider checking for redirect results...");
    getRedirectResult(auth)
      .then((result) => {
        if (result) {
          console.log("🎯 Redirect Recovery Success! User:", result.user.email);
          setCurrentUser(result.user);
        }
      })
      .catch((err) => {
        console.error("❌ Redirect Recovery Error:", err);
      });

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
