import React, { useEffect, useState } from "react";
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

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, errorInfo) {
    console.error("App Error Boundary caught:", error, errorInfo);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-surface-base flex items-center justify-center p-6">
          <div className="max-w-md w-full card card-lg text-center">
            <h3 className="text-lg font-semibold mb-2 text-semantic-error">Something went wrong</h3>
            <p className="text-sm text-text-secondary mb-4">
              The application encountered an unexpected error. Please return to the landing page and try again.
            </p>
            <pre className="text-xs bg-surface-overlay p-3 rounded-sm mb-4 text-left overflow-auto max-h-40 text-semantic-error">
              {this.state.error?.message || "Unknown error"}
            </pre>
            <button
              className="btn-primary"
              onClick={() => {
                sessionStorage.clear();
                window.location.href = "/";
              }}
            >
              Return to Landing Page
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

function App() {
  const iv = useInterview();
  const { currentUser, isGuest, loading: authLoading, loginWithGoogle } = useAuth();
  const [caps, setCaps] = useState({ mode: "CPU", llmMode: "api", audioEnabled: true });

  // 1. Route Guard: Auto-transition to dashboard if user is known
  useEffect(() => {
    if (!authLoading && currentUser && iv.step === "landing") {
      iv.setStep("dashboard");
    }
  }, [currentUser, authLoading, iv.step]);

  // 2. Fetch server capabilities once
  useEffect(() => {
    api.getHealth().then(res => {
      setCaps({
        mode: res.mode || "CPU",
        llmMode: res.llm_mode || "api",
        audioEnabled: res.asr_available === true
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
    // Allow guests (isGuest=true) even if currentUser temporarily null during async restore
    if (!currentUser && !isGuest) {
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

  // FLOW: Setup
  if (iv.step === "setup") {
    return (
      <Setup 
        onSubmit={(data) => {
          iv.setReport(null);
          iv.saveSetup(data);
          iv.setStep("pre-interview");
        }} 
        onBack={() => iv.setStep("dashboard")}
      />
    );
  }

  // FLOW: Pre-Interview (Equipment Check & Question Gen)
  if (iv.step === "pre-interview") {
    return (
      <PreInterview 
        sessionId={iv.sessionId}
        setupData={iv.setupData}
        onBegin={() => iv.startInterview()} 
      />
    );
  }

  // FLOW: Active Interview
  if (iv.step === "interview") {
    return (
      <Interview 
        sessionId={iv.sessionId}
        question={iv.question}
        questionNumber={iv.questionNumber}
        totalQuestions={iv.totalQuestions}
        loading={iv.loading}
        evaluating={iv.evaluating}
        setupData={iv.setupData}
        audioEnabled={caps.audioEnabled}
        onSubmitText={iv.submitText}
        onSubmitAudio={iv.submitAudio}
        onSkip={() => iv.skipQuestion && iv.skipQuestion()}
      />
    );
  }

  // FLOW: Final Evaluation Processing
  if (iv.step === "processing") {
    return (
      <Processing 
        sessionId={iv.sessionId}
        onDone={(report) => {
          iv.setReport(report);
          iv.setStep("results");
        }} 
      />
    );
  }
  
  // FLOW: Results & Feedback
  if (iv.step === "results") {
    return (
      <Results 
        report={iv.report} 
        caps={caps}
        onRestart={() => iv.restart()} 
      />
    );
  }

  return (
    <div className="error-screen">
      <div className="card card-sm" style={{textAlign:"center"}}>
        <h3>Unknown Application State</h3>
        <p>Current Step: {iv.step}</p>
        <button className="btn-primary" onClick={() => iv.setStep("landing")} style={{marginTop: "1rem"}}>
          Return to Landing
        </button>
      </div>
    </div>
  );
}

export default function AppWithBoundary() {
  return (
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  );
}
