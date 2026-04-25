import { createContext, useContext, useEffect, useState } from "react";
import { auth, googleProvider } from "../firebase";
import { onAuthStateChanged, signInWithPopup, signInWithRedirect, getRedirectResult, signOut } from "firebase/auth";

const AuthContext = createContext();

export function useAuth() {
  return useContext(AuthContext);
}

export function AuthProvider({ children }) {
  const [currentUser, setCurrentUser] = useState(null);
  const [isGuest, setIsGuest] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // ROOT FIX: Check for guest session immediately
  useEffect(() => {
    const guestStatus = localStorage.getItem("isGuestSession") === "true";
    if (guestStatus) {
      console.log("🚀 Restoring Guest Session...");
      setIsGuest(true);
    }
  }, []);

  async function loginWithGoogle() {
    try {
      setError(null);
      setIsGuest(false);
      localStorage.removeItem("isGuestSession");
      
      console.log("🚀 Attempting First-Party Auth...");
      // This will now use the Vercel Proxy because of the firebase.js fix
      const result = await signInWithPopup(auth, googleProvider);
      return result;
    } catch (err) {
      console.error("❌ Auth Error:", err);
      if (err.code === "auth/popup-blocked" || err.code === "auth/cancelled-popup-request") {
        return signInWithRedirect(auth, googleProvider);
      }
      setError(err.message);
    }
  }

  function loginAsGuest() {
    console.log("👤 Continuing as Guest...");
    setIsGuest(true);
    localStorage.setItem("isGuestSession", "true");
    setError(null);
  }

  function logout() {
    localStorage.removeItem("firebaseToken");
    localStorage.removeItem("cachedUser");
    localStorage.removeItem("isGuestSession");
    setIsGuest(false);
    if (auth) signOut(auth);
  }

  useEffect(() => {
    if (!auth) {
      setLoading(false);
      return;
    }

    getRedirectResult(auth)
      .then((result) => {
        if (result) {
          setCurrentUser(result.user);
        }
      })
      .catch((err) => console.error("Redirect Result Error:", err));

    const unsubscribe = onAuthStateChanged(auth, async (user) => {
      if (user) {
        setCurrentUser(user);
        setIsGuest(false);
        const token = await user.getIdToken();
        localStorage.setItem("firebaseToken", token);
        localStorage.setItem("cachedUser", JSON.stringify({
          email: user.email,
          uid: user.uid,
          displayName: user.displayName
        }));
      } else {
        const cached = localStorage.getItem("cachedUser");
        if (cached && !isGuest) {
          setCurrentUser(JSON.parse(cached));
        } else {
          setCurrentUser(null);
        }
      }
      setLoading(false);
    });

    return unsubscribe;
  }, [isGuest]);

  const value = {
    currentUser,
    isGuest,
    loginWithGoogle,
    loginAsGuest,
    logout,
    loading,
    error
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}
