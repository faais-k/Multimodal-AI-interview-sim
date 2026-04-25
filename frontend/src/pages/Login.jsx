import React, { useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import "./Login.css";

export default function Login({ onLoginSuccess }) {
  const { loginWithGoogle } = useAuth();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleGoogleLogin = async () => {
    try {
      setError("");
      setLoading(true);
      await loginWithGoogle();
      if (onLoginSuccess) onLoginSuccess();
    } catch (err) {
      setError("Failed to sign in with Google. Please try again.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
          <div className="login-logo">
            <span className="logo-icon">🚀</span>
            <h1>Ascent AI</h1>
          </div>
          <p className="login-subtitle">Elevate your career with multimodal AI mock interviews</p>
        </div>

        <div className="login-content">
          <h2>Welcome Back</h2>
          <p>Sign in to track your progress and access your interview history.</p>

          {error && <div className="login-error">{error}</div>}

          <button 
            className="google-login-btn" 
            onClick={handleGoogleLogin}
            disabled={loading}
          >
            <img 
              src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" 
              alt="Google" 
            />
            {loading ? "Signing in..." : "Continue with Google"}
          </button>
        </div>

        <div className="login-footer">
          <p>By continuing, you agree to our Terms of Service and Privacy Policy.</p>
        </div>
      </div>
      
      <div className="login-visual">
        <div className="visual-circle circle-1"></div>
        <div className="visual-circle circle-2"></div>
        <div className="visual-content">
          <div className="stat-card">
            <span className="stat-value">92%</span>
            <span className="stat-label">Interview Ready</span>
          </div>
          <div className="stat-card">
            <span className="stat-value">12k+</span>
            <span className="stat-label">Users Hired</span>
          </div>
        </div>
      </div>
    </div>
  );
}
