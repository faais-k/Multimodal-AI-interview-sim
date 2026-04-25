import { createContext, useContext, useEffect, useState } from "react";
import { auth } from "../firebase";
import { onAuthStateChanged, signInWithPopup, signOut } from "firebase/auth";
import { googleProvider } from "../firebase";

const AuthContext = createContext();

export function useAuth() {
  return useContext(AuthContext);
}

export function AuthProvider({ children }) {
  const [currentUser, setCurrentUser] = useState(null);
  const [isGuest, setIsGuest] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // 1. Google Login Path
  async function loginWithGoogle() {
    setError(null);
    try {
      // PRO TIP: Do NOT await any async logic before this line
      // to ensure Chrome treats this as a trusted user gesture.
      const result = await signInWithPopup(auth, googleProvider);
      setIsGuest(false);
      return result;
    } catch (err) {
      console.error("Login Error:", err);
      if (err.code === "auth/popup-blocked") {
        const msg = "Popup blocked! Please allow popups for this site or check your browser security settings (COOP).";
        alert(msg);
        setError(msg);
      } else {
        setError(err.message);
      }
      throw err; // Re-throw so callers know it failed
    }
  }

  // 2. Guest Login Path
  function loginAsGuest() {
    setError(null);
    const guestId = `guest_${Math.random().toString(36).substr(2, 9)}`;
    const guestUser = {
      uid: guestId,
      displayName: "Guest Candidate",
      email: "guest@ascent.ai",
      isGuest: true
    };
    setCurrentUser(guestUser);
    setIsGuest(true);
    localStorage.setItem("ascent_guest_user", JSON.stringify(guestUser));
    return guestUser;
  }

  function logout() {
    setIsGuest(false);
    localStorage.removeItem("ascent_guest_user");
    localStorage.removeItem("firebaseToken");
    if (auth.currentUser) {
      return signOut(auth);
    } else {
      setCurrentUser(null);
    }
  }

  useEffect(() => {
    let unsubscribe = () => {};
    
    const initAuth = async () => {
      try {
        // Restore Guest Session if exists
        const savedGuest = localStorage.getItem("ascent_guest_user");
        if (savedGuest) {
          setCurrentUser(JSON.parse(savedGuest));
          setIsGuest(true);
          setLoading(false);
          return;
        }

        if (!auth) {
          console.warn("Firebase Auth not initialized. Falling back to guest mode.");
          setLoading(false);
          return;
        }

        unsubscribe = onAuthStateChanged(auth, async (user) => {
          try {
            setCurrentUser(user);
            if (user) {
              const token = await user.getIdToken();
              localStorage.setItem("firebaseToken", token);
              setIsGuest(false);
            }
          } catch (err) {
            console.error("Auth State Callback Error:", err);
          } finally {
            setLoading(false);
          }
        });
      } catch (err) {
        console.error("AuthProvider Init Error:", err);
        setLoading(false);
      }
    };

    initAuth();
    return () => unsubscribe();
  }, []);

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
      {!loading && children}
    </AuthContext.Provider>
  );
}
