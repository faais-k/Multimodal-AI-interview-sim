import { createContext, useContext, useEffect, useState } from "react";
import { auth } from "../firebase";
import { onAuthStateChanged, signInWithRedirect, GoogleAuthProvider, signOut, getRedirectResult } from "firebase/auth";
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
      console.log("🚀 Initiating Google Sign-In Redirect...");
      // No await needed here as it redirects the whole page
      signInWithRedirect(auth, googleProvider);
    } catch (err) {
      console.error("❌ Login Error:", err);
      setError(err.message);
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

    // Check if we just returned from a redirect
    console.log("🕒 AuthProvider checking for redirect result...");
    getRedirectResult(auth)
      .then((result) => {
        if (result) {
          console.log("🎯 Redirect result found! User:", result.user.email);
        }
      })
      .catch((err) => {
        console.error("❌ Redirect Result Error:", err);
        setError(err.message);
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
