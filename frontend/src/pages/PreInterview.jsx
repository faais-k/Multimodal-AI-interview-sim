import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import "./PreInterview.css";

const Logo = () => (
  <svg width="28" height="28" viewBox="0 0 36 36" fill="none">
    <rect width="36" height="36" rx="10" fill="url(#pi-lg)"/>
    <path d="M8 26 L18 10 L28 26" stroke="white" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" fill="none" opacity="0.4"/>
    <path d="M8 26 L14 18 L18 22 L22 14 L28 26" stroke="white" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" fill="none"/>
    <defs><linearGradient id="pi-lg" x1="0" y1="0" x2="36" y2="36"><stop offset="0%" stopColor="#14B8A6"/><stop offset="100%" stopColor="#0D9488"/></linearGradient></defs>
  </svg>
);

export default function PreInterview({ onBegin, setupData, sessionId }) {
  const [checks, setChecks] = useState({ camera: false, mic: false });
  const [starting, setStarting] = useState(false);
  const [camError, setCamError] = useState(null);
  const [generating, setGenerating] = useState(true);
  const [questionsReady, setQuestionsReady] = useState(false);
  const [genError, setGenError] = useState(null);
  const videoRef  = useRef();
  const streamRef = useRef(null);

  // Camera/Mic setup
  useEffect(() => {
    (async () => {
      try {
        const s = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
        streamRef.current = s;
        setChecks({ camera: true, mic: true });
        if (videoRef.current) videoRef.current.srcObject = s;
      } catch (e) {
        console.warn("Camera/mic:", e);
        setCamError("Camera or microphone not accessible. You can still proceed with text answers.");
      }
    })();
    return () => streamRef.current?.getTracks().forEach(t => t.stop());
  }, []);

  // Background question generation
  useEffect(() => {
    if (!sessionId) return;
    
    let cancelled = false;
    
    const generateQuestions = async () => {
      try {
        setGenerating(true);
        const result = await api.generateDynamicInterview(sessionId);
        
        if (!cancelled) {
          if (result.status === "ok") {
            setQuestionsReady(true);
            setGenerating(false);
          } else {
            setGenError("Failed to generate questions");
            setGenerating(false);
          }
        }
      } catch (e) {
        if (!cancelled) {
          setGenError(e.message || "Failed to generate questions");
          setGenerating(false);
        }
      }
    };
    
    generateQuestions();
    
    return () => { cancelled = true; };
  }, [sessionId]);

  const begin = async () => {
    setStarting(true);
    try { await document.documentElement.requestFullscreen(); } catch (_) {}
    if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop());
    onBegin();
  };

  const CheckRow = ({ label, done, optional }) => (
    <div className="pi-check">
      <div className={`pi-check__icon${done ? " done" : optional ? " optional" : ""}`}>
        {done
          ? <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
          : <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/></svg>
        }
      </div>
      <div className="pi-check__label">{label}</div>
      {optional && !done && <span className="chip chip-stone" style={{fontSize:"var(--text-xs)"}}>Optional</span>}
    </div>
  );

  return (
    <div className="pi-shell">
      <header className="pi-bar">
        <div className="pi-bar__brand"><Logo /><span>Ascent</span></div>
        <span className="pi-bar__step">Pre-Interview Check</span>
      </header>

      <div className="pi-body">
        <div className="pi-left animate-in">
          <div className="pi-left__header">
            <h1 className="pi-left__title">
              Ready, <em className="gradient-text">{setupData?.name || "Candidate"}</em>?
            </h1>
            <p className="pi-left__sub">Let's verify your equipment before the interview begins.</p>
          </div>

          {/* Camera preview */}
          <div className="pi-video-wrap">
            {camError ? (
              <div className="pi-video-error">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M15 10l4.553-2.069A1 1 0 0 1 21 8.87v6.26a1 1 0 0 1-1.447.9L15 14M3 8a2 2 0 0 0-2 2v4a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2v-4a2 2 0 0 0-2-2H3z"/></svg>
                <span>{camError}</span>
              </div>
            ) : (
              <video ref={videoRef} autoPlay playsInline muted className="pi-video" />
            )}
          </div>

          {/* Checks */}
          <div className="pi-checks" style={{display: "flex", flexDirection: "row", gap: "1rem", justifyContent: "space-between"}}>
            <CheckRow label="Camera accessible" done={checks.camera} optional />
            <CheckRow label="Microphone accessible" done={checks.mic} optional />
            <CheckRow label="Questions generated" done={questionsReady} />
          </div>

          {genError && (
            <div className="pi-error">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 8v4m0 4h.01"/></svg>
              {genError} — You can still proceed with default questions.
            </div>
          )}

          <button
            className="btn-primary pi-begin"
            onClick={begin}
            disabled={starting || (generating && !genError)}
          >
            {starting ? (
              <><span className="spinner"/>Starting…</>
            ) : generating && !genError ? (
              <><span className="spinner"/>Generating questions…</>
            ) : (
              <>Begin Interview<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polygon points="5 3 19 12 5 21 5 3"/></svg></>
            )}
          </button>
        </div>

        <div className="pi-right animate-in">
          <div className="card pi-session-card">
            <div className="pi-session-card__title">Session Details</div>
            <div className="pi-session-rows">
              {setupData?.name && <div className="pi-session-row"><span>Candidate</span><span>{setupData.name}</span></div>}
              {setupData?.jobRole && <div className="pi-session-row"><span>Target Role</span><span>{setupData.jobRole}</span></div>}
              {setupData?.company && <div className="pi-session-row"><span>Company</span><span>{setupData.company}</span></div>}
              {setupData?.expertiseLevel && <div className="pi-session-row"><span>Level</span><span style={{textTransform:"capitalize"}}>{setupData.expertiseLevel}</span></div>}
            </div>
          </div>

          <div className="card pi-tips-card">
            <div className="pi-tips-card__title">Before You Begin</div>
            <ul className="pi-tips-list">
              <li>Sit in a quiet, well-lit space</li>
              <li>Face the camera directly</li>
              <li>Keep your shoulders level and back straight</li>
              <li>Answers are evaluated in real time — be specific and structured</li>
              <li>Use the STAR method: Situation → Task → Action → Result</li>
              <li>Don't tab away — anti-cheat monitoring is active</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
