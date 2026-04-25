import React, { useEffect, useState } from "react";
import "./App.css";
import Landing from "./pages/Landing";
import Dashboard from "./pages/Dashboard";
import Setup from "./pages/Setup";
import PreInterview from "./pages/PreInterview";
import Interview from "./pages/Interview";
import Processing from "./pages/Processing";
import Results from "./pages/Results";
import { useInterview } from "./contexts/InterviewContext";
import { useAuth } from "./contexts/AuthContext";
import { api } from "./api/client";

function App() {
  const iv = useInterview();
  const { currentUser, loading: authLoading, loginWithGoogle } = useAuth();
  const [caps, setCaps] = useState({ mode: "CPU", llmMode: "api", audioEnabled: true });

  // Route Guard: Auto-transition to dashboard if user is known
  useEffect(() => {
    if (!authLoading && currentUser && iv.step === "landing") {
      iv.setStep("dashboard");
    }
  }, [currentUser, authLoading, iv.step]);

  // Fetch server capabilities once
  useEffect(() => {
    api.getHealth().then(res => {
      setCaps({
        mode: res.runtime_mode || "CPU",
        llmMode: res.llm_evaluator || "api",
        audioEnabled: res.asr_model !== "none"
      });
    }).catch(() => {});
  }, []);

  if (authLoading) {
    return (
      <div className="ascent-loader-overlay">
        <div className="ascent-loader"></div>
      </div>
    );
  }

  // FLOW: Landing
  if (iv.step === "landing") {
    return (
      <Landing 
        onStart={async () => {
          const res = await loginWithGoogle();
          if (res) iv.setStep("dashboard");
        }} 
        onGuestLogin={() => iv.setStep("dashboard")}
      />
    );
  }

  // FLOW: Dashboard
  if (iv.step === "dashboard") {
    if (!currentUser) {
      iv.setStep("landing");
      return null;
    }
    return (
      <Dashboard 
        onStartNew={() => iv.setStep("setup")}
        onViewResults={async (sid) => {
          try {
            const reportData = await api.getReport(sid);
            iv.setReport(reportData);
            iv.setStep("results");
          } catch (e) {
            alert("Could not load report details.");
          }
        }}
      />
    );
  }

  // FLOW: Interview Pipeline
  if (iv.step === "setup") return <Setup onReady={() => iv.setStep("pre-interview")} />;
  if (iv.step === "pre-interview") return <PreInterview onStart={() => iv.setStep("interview")} />;
  if (iv.step === "interview") return <Interview onComplete={() => iv.setStep("processing")} />;
  if (iv.step === "interview-processing" || iv.step === "processing") return <Processing onDone={() => iv.setStep("results")} />;
  
  if (iv.step === "results") {
    return (
      <Results 
        report={iv.report} 
        caps={caps}
        onRestart={() => {
          iv.restart(); 
          iv.setStep("dashboard");
        }} 
      />
    );
  }

  return <div className="error-screen">Unknown Step: {iv.step}</div>;
}

export default App;
