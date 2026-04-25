import React, { useState, useEffect } from 'react';
import './App.css';

// Contexts
import { useInterview } from './contexts/InterviewContext';
import { useAuth } from './contexts/AuthContext';

// Pages
import Landing from './pages/Landing';
import Login from './pages/Login';
import CandidateDashboard from './pages/CandidateDashboard';
import InterviewConfig from './pages/InterviewConfig';
import InterviewSession from './pages/InterviewSession';
import InterviewResults from './pages/InterviewResults';

function App() {
  const iv = useInterview();
  const { currentUser, isGuest, loading: authLoading } = useAuth();
  
  // ROOT FIX: Routing Logic
  useEffect(() => {
    if (!authLoading) {
      const hasSession = !!currentUser || isGuest;
      
      console.log("🚦 Routing Check:", { hasSession, step: iv.step });
      
      if (hasSession) {
        // If logged in/guest, and still on landing/login, move to dashboard
        if (iv.step === "landing" || iv.step === "login") {
          iv.setStep("dashboard");
        }
      } else {
        // If NO session, force landing (unless already on login)
        if (iv.step !== "landing" && iv.step !== "login") {
          iv.setStep("landing");
        }
      }
    }
  }, [currentUser, isGuest, authLoading, iv.step]);

  if (authLoading) {
    return <div className="loading-screen">Verifying Session...</div>;
  }

  // Define views based on step
  if (iv.step === "landing") {
    return <Landing onStart={() => iv.setStep("login")} />;
  }

  if (iv.step === "login") {
    return <Login onLoginSuccess={() => iv.setStep("dashboard")} />;
  }

  if (iv.step === "dashboard") {
    return <CandidateDashboard />;
  }

  if (iv.step === "config") {
    return <InterviewConfig />;
  }

  if (iv.step === "interview") {
    return <InterviewSession />;
  }

  if (iv.step === "results") {
    return <InterviewResults />;
  }

  return <div>Unknown step: {iv.step}</div>;
}

export default App;
