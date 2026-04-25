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
      const msg = "Firebase not initialized. Check Vercel environment variables.";
      console.error(msg);
      alert(msg);
      return;
    }
    try {
      return await signInWithRedirect(auth, googleProvider);
    } catch (err) {
      console.error("Login Error:", err);
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

    // Check for redirect result on mount
    getRedirectResult(auth).catch((err) => {
      console.error("Redirect Result Error:", err);
      setError(err.message);
    });

    const unsubscribe = onAuthStateChanged(auth, async (user) => {
      setCurrentUser(user);
      
      // If user is logged in, grab their JWT so we can attach it to API requests
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
    error
  };

  return (
    <AuthContext.Provider value={value}>
      {!loading && children}
    </AuthContext.Provider>
  );
}
