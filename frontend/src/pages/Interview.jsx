import { useEffect, useRef, useState } from "react";
import PostureMonitor from "../components/PostureMonitor";
import { useAudioRecorder } from "../hooks/useAudioRecorder";
import { useAntiCheat } from "../hooks/useAntiCheat";
import { AUDIO_INPUT_HINT } from "../api/client";
import "./Interview.css";

const Logo = () => (
  <svg width="24" height="24" viewBox="0 0 36 36" fill="none">
    <rect width="36" height="36" rx="10" fill="url(#iv-lg)"/>
    <path d="M8 26 L18 10 L28 26" stroke="white" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" fill="none" opacity="0.4"/>
    <path d="M8 26 L14 18 L18 22 L22 14 L28 26" stroke="white" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" fill="none"/>
    <defs><linearGradient id="iv-lg" x1="0" y1="0" x2="36" y2="36"><stop offset="0%" stopColor="#14B8A6"/><stop offset="100%" stopColor="#0D9488"/></linearGradient></defs>
  </svg>
);

const TYPE_META = {
  self_intro: { label:"Introduction",     chipClass:"chip-teal"    },
  intro:      { label:"Introduction",     chipClass:"chip-teal"    },
  project:    { label:"Project",          chipClass:"chip-amber"   },
  technical:  { label:"Technical",        chipClass:"chip-stone"   },
  followup:   { label:"Follow-up",        chipClass:"chip-warning" },
  hr:         { label:"Behavioural",      chipClass:"chip-green"   },
  critical:   { label:"Critical",         chipClass:"chip-red"     },
  wrapup:     { label:"Wrap-up",          chipClass:"chip-stone"   },
  warmup:     { label:"Warm-up",          chipClass:"chip-teal"    },
};

export default function Interview({ sessionId, question, questionNumber, loading, evaluating, onSubmitText, onSubmitAudio, setupData, audioEnabled = false }) {
  const [mode, setMode]       = useState("text");
  const [answer, setAnswer]   = useState("");
  const [submitting, setSub]  = useState(false);
  const [cameraStream, setCameraStream] = useState(null);
  const streamRef             = useRef(null);

  const { recording, audioBlob, audioURL, micError, start: startRec, stop: stopRec, reset: resetRec } = useAudioRecorder();
  const antiCheat = useAntiCheat(sessionId, true);

  useEffect(() => {
    navigator.mediaDevices.getUserMedia({ video:true, audio:false })
      .then(s => {
        streamRef.current = s;
        setCameraStream(s);
      })
      .catch(e => console.warn("Camera unavailable:", e));
    return () => {
      streamRef.current?.getTracks().forEach(t => t.stop());
      setCameraStream(null);
    };
  }, []);

  useEffect(() => {
    setAnswer(""); resetRec(); setSub(false);
  }, [question?.id]);

  useEffect(() => {
    if (!audioEnabled && mode === "audio") {
      setMode("text");
    }
  }, [mode]);

  const handleTextSubmit = async () => {
    if (!answer.trim() || submitting || loading || evaluating) return;
    setSub(true);
    await onSubmitText(answer);
    setSub(false);
  };

  const handleAudioSubmit = async () => {
    if (!audioBlob || submitting || loading || evaluating) return;
    setSub(true);
    await onSubmitAudio(audioBlob);
    setSub(false);
  };

  const qtype = question?.type || "technical";
  const meta  = TYPE_META[qtype] || TYPE_META.technical;
  const canSubmitText  = answer.trim().length > 0 && !submitting && !loading && !evaluating;
  const canSubmitAudio = !!audioBlob && !submitting && !loading && !evaluating;
  const busy = submitting || loading || evaluating;

  return (
    <div className="iv-shell">
      {/* Top bar */}
      <header className="iv-bar">
        <div className="iv-bar__left">
          <Logo />
          <span className="iv-bar__title">Ascent</span>
          <div className="iv-bar__divider" aria-hidden="true"/>
          <span className="iv-bar__role">{setupData?.jobRole || "Interview"}</span>
        </div>
        <div className="iv-bar__center">
          {antiCheat?.warningMessage && (
            <div className="iv-warning" role="alert">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
              {antiCheat.warningMessage}
            </div>
          )}
        </div>
        <div className="iv-bar__right">
          {setupData?.name && <span className="iv-bar__name">{setupData.name}</span>}
          {setupData?.expertiseLevel && <span className={`chip chip-stone iv-bar__level`}>{setupData.expertiseLevel}</span>}
        </div>
      </header>

      {/* Main layout: question area + sidebar */}
      <div className="iv-layout">
        {/* ── Left: Question + Answer ── */}
        <main className="iv-main">
          <div className="iv-q-header">
            <span className="iv-q-num">Question {questionNumber}</span>
            <span className={`chip ${meta.chipClass}`}>{meta.label}</span>
          </div>

          {loading && !evaluating ? (
            <div className="iv-loading">
              <span className="spinner" style={{width:20,height:20}}/> Loading question…
            </div>
          ) : (
            <div className="iv-question-wrap animate-in" key={question?.id}>
              <div className="iv-question">
                {question?.question || "Preparing your next question…"}
              </div>
              <button
                className="iv-speak-btn"
                onClick={() => {
                  if ('speechSynthesis' in window && question?.question) {
                    window.speechSynthesis.cancel();
                    const utterance = new SpeechSynthesisUtterance(question.question);
                    utterance.rate = 0.9;
                    utterance.pitch = 1;
                    window.speechSynthesis.speak(utterance);
                  }
                }}
                disabled={!('speechSynthesis' in window)}
                title="Read question aloud"
                aria-label="Read question aloud"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
                  <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/>
                </svg>
                Listen
              </button>
            </div>
          )}

          {evaluating && (
            <div className="iv-eval-bar">
              <div className="iv-eval-bar__fill" />
              <span className="iv-eval-bar__label">
                <span className="spinner" style={{width:14,height:14}}/>
                {mode === "audio" ? "Transcribing & evaluating…" : "Evaluating your answer…"}
              </span>
            </div>
          )}

          {/* Mode switcher */}
          <div className="iv-mode-tabs" role="tablist">
            <button
              className={`iv-mode-tab${mode==="text"?" active":""}`}
              role="tab"
              aria-selected={mode==="text"}
              onClick={()=>{setMode("text");resetRec();}}
              disabled={busy}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
              Type Answer
            </button>
            {audioEnabled && (
              <button
                className={`iv-mode-tab${mode==="audio"?" active":""}`}
                role="tab"
                aria-selected={mode==="audio"}
                onClick={()=>{setMode("audio");setAnswer("");}}
                disabled={busy}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
                Speak Answer
              </button>
            )}
          </div>

          {!audioEnabled && (
            <div className="iv-audio-note">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4m0-4h.01"/></svg>
              {AUDIO_INPUT_HINT}
            </div>
          )}

          {/* Text input */}
          {mode === "text" && (
            <div className="iv-text-area-wrap animate-fade">
              <textarea
                className="iv-textarea"
                value={answer}
                onChange={e => setAnswer(e.target.value)}
                placeholder="Type your answer here. Be specific — mention real projects, outcomes, and reasoning…"
                onKeyDown={e => { if (e.ctrlKey && e.key === "Enter") handleTextSubmit(); }}
                disabled={busy}
                rows={6}
                aria-label="Your answer"
              />
              <div className="iv-textarea-hint">
                <span>{answer.trim().split(/\s+/).filter(Boolean).length} words</span>
                <span>Ctrl + Enter to submit</span>
              </div>
            </div>
          )}

          {/* Audio input */}
          {mode === "audio" && (
            <div className="iv-audio-wrap animate-fade">
              {micError && (
                <div className="iv-audio-error">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                  {micError} — please use text mode or grant microphone access.
                </div>
              )}
              {!micError && (
                <div className="iv-audio-controls">
                  {!recording && !audioBlob && (
                    <button className="iv-rec-btn iv-rec-btn--start" onClick={startRec} disabled={busy}>
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="6"/></svg>
                      Start Recording
                    </button>
                  )}
                  {recording && (
                    <button className="iv-rec-btn iv-rec-btn--stop" onClick={stopRec}>
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>
                      Stop Recording
                      <span className="iv-rec-dot" aria-hidden="true"/>
                    </button>
                  )}
                  {audioBlob && !recording && (
                    <div className="iv-audio-ready">
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                      Recording ready
                      <button className="btn-ghost" style={{fontSize:"var(--text-xs)",padding:"2px var(--space-2)"}} onClick={resetRec} disabled={busy}>Re-record</button>
                    </div>
                  )}
                  {audioURL && (
                    <audio controls src={audioURL} className="iv-audio-preview" aria-label="Your recording"/>
                  )}
                </div>
              )}
              <div className="iv-audio-note">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4m0-4h.01"/></svg>
                {AUDIO_INPUT_HINT}
              </div>
            </div>
          )}

          {/* Submit */}
          <div className="iv-submit-row">
            <button
              className="btn-primary iv-submit"
              onClick={mode === "text" ? handleTextSubmit : handleAudioSubmit}
              disabled={mode === "text" ? !canSubmitText : !canSubmitAudio}
            >
              {busy
                ? <><span className="spinner"/>Processing…</>
                : <>Submit Answer<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg></>
              }
            </button>
          </div>
        </main>

        {/* ── Right: Posture + Info ── */}
        <aside className="iv-sidebar">
          <div className="iv-posture-card">
            <div className="iv-posture-card__header">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M2 12h20"/></svg>
              Live Posture Monitor
            </div>
            <PostureMonitor sessionId={sessionId} stream={cameraStream} />
          </div>

          <div className="iv-info-card card card-sm">
            <div className="iv-info-row">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
              <span>{setupData?.name || "Candidate"}</span>
            </div>
            {setupData?.jobRole && (
              <div className="iv-info-row">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>
                <span>{setupData.jobRole}</span>
              </div>
            )}
            {setupData?.company && (
              <div className="iv-info-row">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="4" y="2" width="16" height="20" rx="2"/><line x1="9" y1="6" x2="15" y2="6"/><line x1="9" y1="10" x2="15" y2="10"/></svg>
                <span>{setupData.company}</span>
              </div>
            )}
            {setupData?.expertiseLevel && (
              <div className="iv-info-row">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
                <span style={{textTransform:"capitalize"}}>{setupData.expertiseLevel}</span>
              </div>
            )}
          </div>

          <div className="iv-tips card card-sm">
            <div className="iv-tips__title">Interview Tips</div>
            <ul className="iv-tips__list">
              <li>Sit upright, face visible</li>
              <li>Look at the camera naturally</li>
              <li>Use STAR: Situation → Task → Action → Result</li>
              <li>Be specific — mention real outcomes</li>
            </ul>
          </div>
        </aside>
      </div>
    </div>
  );
}
