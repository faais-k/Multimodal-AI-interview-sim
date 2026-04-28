import { useEffect, useState, useRef } from "react";
import { api } from "../api/client";
import { useAuth } from "../contexts/AuthContext";
import { saveGuestInterview } from "@/lib/guestStorage";
import "./Processing.css";

const STEPS = [
  { id: "scoring",   label: "Scoring all answers" },
  { id: "fluency",   label: "Detecting filler words" },
  { id: "posture",   label: "Analysing posture" },
  { id: "report",    label: "Building action plan" }
];

export default function Processing({ sessionId, onDone }) {
  const { isGuest } = useAuth();
  const [currentStep, setCurrentStep] = useState(0);
  const [error, setError] = useState(null);
  const [completedSteps, setCompletedSteps] = useState([]);
  const hasStarted = useRef(false);

  useEffect(() => {
    if (hasStarted.current || !sessionId) return;
    hasStarted.current = true;

    const runAnalysis = async () => {
      try {
        // Step 1: Aggregate (Scoring & Posture)
        setCurrentStep(0);
        await api.aggregate(sessionId);
        setCompletedSteps(prev => [...prev, "scoring"]);

        // Step 2: Analytics (Filler words & patterns)
        setCurrentStep(1);
        await api.analytics(sessionId);
        setCompletedSteps(prev => [...prev, "fluency"]);

        // Step 3: Decision (Final recommendation)
        setCurrentStep(2);
        await api.decision(sessionId);
        setCompletedSteps(prev => [...prev, "posture"]);

        // Step 4: Build Report (Fetch final data)
        setCurrentStep(3);
        const report = await api.getReport(sessionId);
        setCompletedSteps(prev => [...prev, "report"]);

        // Save to guest storage for guest users
        if (isGuest && report) {
          try {
            await saveGuestInterview(sessionId, report);
          } catch (e) {
            console.warn("Failed to save guest interview:", e);
          }
        }

        // Small delay for UX so user sees the last step complete
        setTimeout(() => onDone(report), 800);
      } catch (err) {
        console.error("Analysis pipeline failed:", err);
        setError(err.message || "The analysis engine encountered an error. Please try again.");
      }
    };

    runAnalysis();
  }, [sessionId, onDone, isGuest]);

  const handleRetry = () => {
    setError(null);
    setCompletedSteps([]);
    hasStarted.current = false;
    // The effect will re-run
  };

  return (
    <div className="proc-shell">
      <div className="proc-card animate-in">
        {error ? (
          <div className="flex flex-col items-center text-center">
            <div className="proc-icon proc-icon--error mb-4">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
            </div>
            <h2 className="proc-title text-xl font-bold mb-2">Analysis Failed</h2>
            <p className="proc-sub mb-6 text-text-secondary">{error}</p>
            <button className="btn-primary px-8 py-2 bg-text-primary text-white rounded-sm" onClick={handleRetry}>
              Retry Analysis
            </button>
          </div>
        ) : (
          <>
            <div className="proc-icon mb-6">
              <span className="spinner" style={{width:48,height:48,borderWidth:3}}/>
            </div>
            <h2 className="proc-title text-xl font-bold mb-2">Analysing your interview…</h2>
            <p className="proc-sub mb-8 text-text-secondary">Generating your personalised scorecard and action plan.</p>
            
            <div className="proc-steps space-y-4 w-full max-w-xs mx-auto">
              {STEPS.map((s, i) => {
                const isCompleted = completedSteps.includes(s.id);
                const isCurrent = currentStep === i;
                
                return (
                  <div 
                    className={`proc-step flex items-center gap-3 transition-opacity duration-300 ${isCurrent ? "opacity-100" : isCompleted ? "opacity-100" : "opacity-40"}`} 
                    key={s.id}
                  >
                    <div className="flex-shrink-0">
                      {isCompleted ? (
                        <div className="w-5 h-5 bg-veridian rounded-full flex items-center justify-center">
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                        </div>
                      ) : isCurrent ? (
                        <span className="spinner" style={{width:16,height:16,borderWidth:2}}/>
                      ) : (
                        <div className="w-5 h-5 border-2 border-border rounded-full" />
                      )}
                    </div>
                    <span className={`text-sm ${isCurrent ? "font-semibold text-text-primary" : "text-text-secondary"}`}>
                      {s.label}
                    </span>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
