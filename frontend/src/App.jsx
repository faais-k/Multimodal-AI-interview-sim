import { useEffect, useState } from "react";
import { useInterview } from "./hooks/useInterview";
import { useAuth } from "./contexts/AuthContext";
import { api } from "./api/client";
import Landing      from "./pages/Landing";
import Login        from "./pages/Login";
import Dashboard    from "./pages/Dashboard";
import Setup        from "./pages/Setup";
import PreInterview from "./pages/PreInterview";
import Interview    from "./pages/Interview";
import Processing   from "./pages/Processing";
import Results      from "./pages/Results";

export default function App() {
  const iv = useInterview();
  const { currentUser, loading: authLoading } = useAuth();

  // ── Dynamic backend capability detection ─────────────────────────────────
  const [backendCaps, setBackendCaps] = useState({
    audioEnabled: false,   // conservative default until health check completes
    mode: null,            // "gpu" | "cpu" | null (unknown)
    llmMode: null,         // "local" | "api" | "disabled" | null
  });

  useEffect(() => {
    let cancelled = false;
    let attempts = 0;

    const checkHealth = async () => {
      try {
        const h = await api.health();
        if (cancelled) return;
        setBackendCaps({
          audioEnabled: h.audio_transcribe === "enabled",
          mode: h.mode || null,
          llmMode: h.llm_mode || null,
        });
      } catch (err) {
        if (cancelled) return;
        attempts++;
        if (attempts < 10) {
          setTimeout(checkHealth, 3000);
        } else {
          setBackendCaps(prev => ({ ...prev, audioEnabled: false }));
        }
      }
    };

    checkHealth();
    return () => { cancelled = true; };
  }, []);

  // Show nothing while checking auth session on refresh
  if (authLoading) return <div className="app-loader"><div className="spinner"></div></div>;

  // Auto-transition to dashboard if logged in and on landing/login
  useEffect(() => {
    console.log("🌍 Current Hostname:", window.location.hostname);
    if (!authLoading) {
      console.log("🚦 App Routing Check:", { 
        step: iv.step, 
        hasUser: !!currentUser, 
        authLoading 
      });
      
      if (currentUser && (iv.step === "landing" || iv.step === "login")) {
        console.log("➡️ Auto-forwarding to Dashboard...");
        iv.setStep("dashboard");
      }
    }
  }, [currentUser, authLoading, iv.step]);

  // STEP: Landing (Entry Point)
  if (iv.step === "landing") {
    console.log("📍 Rendering Landing Page");
    return <Landing onStart={() => {
      console.log("🖱️ Landing Start Clicked. User status:", !!currentUser);
      if (currentUser) iv.setStep("dashboard");
      else iv.setStep("login");
    }} />;
  }

  // STEP: Login
  if (iv.step === "login") {
    console.log("📍 Rendering Login Page");
    if (currentUser) {
      console.log("➡️ Logged in user detected on Login page, moving to dashboard");
      iv.setStep("dashboard");
      return null;
    }
    return <Login onLoginSuccess={() => {
      console.log("🎉 Login success callback triggered");
      iv.setStep("dashboard");
    }} />;
  }

  // STEP: Dashboard (Home for logged in users)
  if (iv.step === "dashboard") {
    console.log("📍 Rendering Dashboard");
    if (!currentUser) {
      console.log("🚫 Logged out user detected on Dashboard, moving to landing");
      iv.setStep("landing");
      return null;
    }
    return (
      <Dashboard 
        onStartNew={() => iv.setStep("setup")} 
        onViewResults={(sid) => iv.viewReport(sid)}
      />
    );
  }

  // STEP: Setup
  if (iv.step === "setup")
    return <Setup onSubmit={iv.setup} loading={iv.loading} error={iv.error} onBack={() => iv.setStep("dashboard")} />;

  if (iv.step === "preinterview")
    return <PreInterview onBegin={iv.startInterview} setupData={iv.setupData} sessionId={iv.sessionId} />;

  if (iv.step === "interview")
    return (
      <Interview
        sessionId      = {iv.sessionId}
        question       = {iv.question}
        questionNumber = {iv.questionNumber}
        loading        = {iv.loading}
        evaluating     = {iv.evaluating}
        onSubmitText   = {iv.submitText}
        onSubmitAudio  = {iv.submitAudio}
        setupData      = {iv.setupData}
        audioEnabled   = {backendCaps.audioEnabled}
      />
    );

  if (iv.step === "processing")
    return <Processing error={iv.error} onRetry={iv.retryFinalize} />;

  if (iv.step === "results")
    return <Results report={iv.report} caps={backendCaps} onRestart={iv.restart} />;

  return null;
}
