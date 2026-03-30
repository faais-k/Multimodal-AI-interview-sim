/**
 * Interview screen.
 *
 * Fixes applied:
 *  - Removed duplicate style prop on infoVal (was style={S.infoVal} + style={...})
 *  - Stream acquired once here; passed as prop to PostureMonitor (no double getUserMedia)
 *  - PreInterview stops its stream before handing off; Interview gets fresh video-only stream
 *  - Fullscreen check uses state (not document.fullscreenElement directly in render — causes hydration issues)
 *  - Loading state shown correctly during submission
 */
import { useEffect, useRef, useState } from "react";
import PostureMonitor from "../components/PostureMonitor";
import { useAudioRecorder } from "../hooks/useAudioRecorder";
import { useAntiCheat } from "../hooks/useAntiCheat";

const TYPE_COLORS = {
  self_intro: { bg:"#667eea22", border:"#667eea", text:"#667eea", label:"Self Introduction" },
  intro:      { bg:"#667eea22", border:"#667eea", text:"#667eea", label:"Self Introduction" },
  project:    { bg:"#9f7aea22", border:"#9f7aea", text:"#9f7aea", label:"Project"           },
  technical:  { bg:"#4299e122", border:"#4299e1", text:"#4299e1", label:"Technical"         },
  followup:   { bg:"#ed893622", border:"#ed8936", text:"#ed8936", label:"Follow-up"         },
  hr:         { bg:"#48bb7822", border:"#48bb78", text:"#48bb78", label:"HR / Behavioral"   },
  critical:   { bg:"#fc818122", border:"#fc8181", text:"#fc8181", label:"Critical Thinking" },
  warmup:     { bg:"#68d39122", border:"#68d391", text:"#68d391", label:"Wrap-up"           },
  wrapup:     { bg:"#68d39122", border:"#68d391", text:"#68d391", label:"Wrap-up"           },
};

export default function Interview({ sessionId, question, questionNumber, loading, evaluating, onSubmitText, onSubmitAudio, setupData }) {
  const [mode, setMode]     = useState("text");
  const [answer, setAnswer] = useState("");
  const [submitting, setSub]= useState(false);
  const [camStream, setCam] = useState(null);
  const [isFullscreen, setIsFullscreen] = useState(!!document.fullscreenElement);
  const streamRef = useRef(null);

  const { recording, audioBlob, audioURL, micError, start: startRec, stop: stopRec, reset: resetRec } = useAudioRecorder();
  const antiCheat = useAntiCheat(sessionId, true);

  // Camera stream — video only (audio handled separately by recorder)
  useEffect(() => {
    navigator.mediaDevices.getUserMedia({ video: true, audio: false })
      .then(s => { streamRef.current = s; setCam(s); })
      .catch(e => console.warn("Camera unavailable:", e));
    return () => streamRef.current?.getTracks().forEach(t => t.stop());
  }, []);

  // Track fullscreen state via event (avoids direct DOM reads in render)
  useEffect(() => {
    const onFsChange = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", onFsChange);
    return () => document.removeEventListener("fullscreenchange", onFsChange);
  }, []);

  // Reset answer when question changes
  useEffect(() => {
    setAnswer("");
    resetRec();
    setSub(false);
  }, [question?.id]);

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

  const qtype  = question?.type || "technical";
  const colors = TYPE_COLORS[qtype] || TYPE_COLORS.technical;
  const canSubmitText  = answer.trim().length > 0 && !submitting && !loading && !evaluating;
  const canSubmitAudio = !!audioBlob && !submitting && !loading && !evaluating;

  return (
    <div style={S.page}>
      {/* Anti-cheat warning toast */}
      {antiCheat.showWarning && (
        <div style={S.toast}>{antiCheat.warningMessage}</div>
      )}

      {/* Fullscreen exit banner */}
      {!isFullscreen && (
        <div style={S.fsBar}>
          ⛶ You exited fullscreen —{" "}
          <span style={S.fsLink} onClick={antiCheat.enterFullscreen}>
            click here to return
          </span>
        </div>
      )}

      <div style={S.layout}>
        {/* LEFT: Question + Answer */}
        <div style={S.left}>
          {/* Progress bar */}
          <div style={S.progressBar}>
            <div style={S.progressInner}>
              <span style={S.progressLabel}>Question {questionNumber}</span>
              <span style={{ ...S.typeBadge, background: colors.bg, border: `1px solid ${colors.border}`, color: colors.text }}>
                {colors.label}
              </span>
            </div>
          </div>

          {/* Question card */}
          <div style={{ ...S.questionCard, borderLeft: `4px solid ${colors.border}` }}>
            {(loading || submitting) && !question
              ? <div style={S.skeleton} />
              : <p style={S.questionText}>{question?.question || "Loading question…"}</p>
            }
          </div>

          {/* Mode toggle */}
          <div style={S.modeRow}>
            {["text", "audio"].map(m => (
              <button key={m} style={{ ...S.modeBtn, ...(mode === m ? S.modeActive : {}) }}
                onClick={() => setMode(m)}>
                {m === "text" ? "✏️ Type Answer" : "🎤 Speak Answer"}
              </button>
            ))}
          </div>

          {/* Text mode */}
          {mode === "text" && (
            <div style={S.answerArea}>
              <textarea
                style={S.textarea} rows={6}
                placeholder="Type your answer here. Be specific — mention real projects, outcomes, and reasoning…"
                value={answer}
                onChange={e => setAnswer(e.target.value)}
                onKeyDown={e => { if (e.ctrlKey && e.key === "Enter") handleTextSubmit(); }}
                disabled={submitting || loading || evaluating}
              />
              <div style={S.textHint}>Ctrl + Enter to submit</div>

              {/* P3-B: LLM evaluation progress indicator */}
              {evaluating && (
                <div style={S.evalBox}>
                  <span style={S.evalText}>⏳ Evaluating your answer…</span>
                  <div style={S.evalTrack}>
                    <div style={S.evalBar} />
                  </div>
                </div>
              )}

              <button
                style={{ ...S.submitBtn, ...(!canSubmitText ? S.submitDisabled : {}) }}
                onClick={handleTextSubmit} disabled={!canSubmitText}>
                {submitting ? "⏳ Scoring your answer…" : evaluating ? "⏳ Evaluating…" : "Submit Answer →"}
              </button>
            </div>
          )}

          {/* Audio mode */}
          {mode === "audio" && (
            <div style={S.audioArea}>
              <div style={S.recorderBox}>
                {!recording && !audioBlob && (
                  <button style={S.recordBtn} onClick={startRec}>
                    <span style={S.recordDot} /> Start Recording
                  </button>
                )}
                {recording && (
                  <button style={{ ...S.recordBtn, ...S.recordActive }} onClick={stopRec}>
                    <span style={{ ...S.recordDot, ...S.recordPulse }} /> Recording… Click to Stop
                  </button>
                )}
                {audioBlob && !recording && (
                  <div style={S.audioReview}>
                    <audio src={audioURL} controls style={S.audioPlayer} />
                    {/* P3-B: LLM evaluation indicator for audio mode */}
                    {evaluating && (
                      <div style={S.evalBox}>
                        <span style={S.evalText}>⏳ Transcribing & evaluating…</span>
                        <div style={S.evalTrack}>
                          <div style={S.evalBar} />
                        </div>
                      </div>
                    )}
                    <div style={S.audioActions}>
                      <button style={S.rerecordBtn} onClick={resetRec} disabled={evaluating}>🔄 Re-record</button>
                      <button
                        style={{ ...S.submitBtn, flex: 1, ...(!canSubmitAudio ? S.submitDisabled : {}) }}
                        onClick={handleAudioSubmit} disabled={!canSubmitAudio}>
                        {submitting || evaluating ? "⏳ Transcribing & evaluating…" : "Submit Recording →"}
                      </button>
                    </div>
                  </div>
                )}
              </div>
              {micError && <div style={{color:"#fc8181",fontSize:"13px",textAlign:"center",padding:"8px",background:"#fc818122",borderRadius:"6px"}}>{micError}</div>}
              <p style={S.audioHint}>🎙️ Speak clearly. Whisper will transcribe automatically.</p>
            </div>
          )}
        </div>

        {/* RIGHT: Camera + Posture */}
        <div style={S.right}>
          <div style={S.camCard}>
            <div style={S.camTitle}>📷 Live Posture Monitor</div>
            <PostureMonitor sessionId={sessionId} stream={camStream} />
            <div style={S.camHints}>
              <div style={S.hint}>• Sit upright, face visible</div>
              <div style={S.hint}>• Look at the camera naturally</div>
              <div style={S.hint}>• Keep shoulders level</div>
            </div>
          </div>

          {/* Candidate info */}
          <div style={S.infoCard}>
            <div style={S.infoRow}>
              <span style={S.infoIcon}>👤</span>
              <span style={S.infoVal}>{setupData?.name || "Candidate"}</span>
            </div>
            <div style={S.infoRow}>
              <span style={S.infoIcon}>💼</span>
              <span style={S.infoVal}>{setupData?.jobRole || "—"}</span>
            </div>
            {setupData?.company && (
              <div style={S.infoRow}>
                <span style={S.infoIcon}>🏢</span>
                <span style={S.infoVal}>{setupData.company}</span>
              </div>
            )}
            <div style={S.infoRow}>
              <span style={S.infoIcon}>📊</span>
              {/* Fix: single style prop, no duplicate */}
              <span style={{ ...S.infoVal, textTransform: "capitalize" }}>
                {setupData?.expertiseLevel || "fresher"}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

const S = {
  page:          { minHeight: "100vh", background: "#0f1117", fontFamily: "'Segoe UI',system-ui,sans-serif", position: "relative" },
  toast:         { position: "fixed", top: "16px", left: "50%", transform: "translateX(-50%)", background: "#ed8936", color: "#fff", padding: "10px 24px", borderRadius: "8px", fontWeight: 600, fontSize: "14px", zIndex: 9999, boxShadow: "0 4px 20px rgba(0,0,0,.4)" },
  fsBar:         { background: "#fc818133", borderBottom: "1px solid #fc818155", padding: "8px 24px", color: "#fc8181", fontSize: "13px", textAlign: "center" },
  fsLink:        { textDecoration: "underline", cursor: "pointer", fontWeight: 600 },
  layout:        { display: "grid", gridTemplateColumns: "1fr 340px", gap: "24px", padding: "24px", maxWidth: "1200px", margin: "0 auto" },
  left:          { display: "flex", flexDirection: "column", gap: "16px" },
  right:         { display: "flex", flexDirection: "column", gap: "16px" },
  progressBar:   { background: "#1a1d2e", border: "1px solid #2a2d3e", borderRadius: "10px", padding: "14px 18px" },
  progressInner: { display: "flex", alignItems: "center", justifyContent: "space-between" },
  progressLabel: { color: "#a0a3b1", fontSize: "13px", fontWeight: 600 },
  typeBadge:     { borderRadius: "20px", padding: "4px 12px", fontSize: "12px", fontWeight: 700 },
  questionCard:  { background: "#1a1d2e", border: "1px solid #2a2d3e", borderRadius: "12px", padding: "24px 28px" },
  questionText:  { color: "#e2e8f0", fontSize: "18px", lineHeight: 1.7, margin: 0, fontWeight: 500 },
  skeleton:      { height: "80px", background: "linear-gradient(90deg,#2a2d3e 25%,#343748 50%,#2a2d3e 75%)", backgroundSize: "200% 100%", borderRadius: "6px", animation: "shimmer 1.4s infinite" },
  modeRow:       { display: "flex", gap: "12px" },
  modeBtn:       { flex: 1, padding: "11px", background: "#1a1d2e", border: "1px solid #2a2d3e", borderRadius: "8px", color: "#a0a3b1", cursor: "pointer", fontSize: "14px", fontWeight: 600 },
  modeActive:    { background: "#667eea22", border: "1px solid #667eea", color: "#667eea" },
  answerArea:    { display: "flex", flexDirection: "column", gap: "10px" },
  textarea:      { width: "100%", background: "#1a1d2e", border: "1px solid #2a2d3e", borderRadius: "10px", padding: "16px", color: "#e2e8f0", fontSize: "15px", lineHeight: 1.6, resize: "vertical", outline: "none", boxSizing: "border-box", fontFamily: "inherit" },
  textHint:      { color: "#4a5568", fontSize: "12px", textAlign: "right" },
  audioArea:     { display: "flex", flexDirection: "column", gap: "12px" },
  recorderBox:   { background: "#1a1d2e", border: "1px solid #2a2d3e", borderRadius: "12px", padding: "28px", display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: "12px", minHeight: "140px" },
  recordBtn:     { display: "flex", alignItems: "center", gap: "12px", padding: "14px 32px", background: "#1a1d2e", border: "2px solid #fc8181", borderRadius: "50px", color: "#fc8181", cursor: "pointer", fontSize: "15px", fontWeight: 700 },
  recordActive:  { background: "#fc818122" },
  recordDot:     { width: "12px", height: "12px", borderRadius: "50%", background: "#fc8181", display: "inline-block" },
  recordPulse:   { animation: "pulse 1s infinite" },
  audioReview:   { width: "100%", display: "flex", flexDirection: "column", gap: "12px" },
  audioPlayer:   { width: "100%" },
  audioActions:  { display: "flex", gap: "10px" },
  rerecordBtn:   { padding: "12px 20px", background: "transparent", border: "1px solid #2a2d3e", borderRadius: "8px", color: "#a0a3b1", cursor: "pointer", fontSize: "14px", fontWeight: 600 },
  audioHint:     { color: "#4a5568", fontSize: "13px", textAlign: "center", margin: 0 },
  submitBtn:     { padding: "14px 28px", background: "linear-gradient(135deg,#667eea,#764ba2)", border: "none", borderRadius: "10px", color: "#fff", fontSize: "15px", fontWeight: 700, cursor: "pointer" },
  submitDisabled:{ opacity: 0.4, cursor: "not-allowed" },
  evalBox:       { background: "#667eea11", border: "1px solid #667eea33", borderRadius: "8px", padding: "10px 14px", display: "flex", flexDirection: "column", gap: "8px" },
  evalText:      { color: "#667eea", fontSize: "13px", fontWeight: 600 },
  evalTrack:     { height: "4px", background: "#2a2d3e", borderRadius: "2px", overflow: "hidden" },
  evalBar:       { height: "100%", width: "60%", background: "linear-gradient(90deg,#667eea,#764ba2)", borderRadius: "2px", animation: "progressPulse 1.5s ease-in-out infinite" },
  camCard:       { background: "#1a1d2e", border: "1px solid #2a2d3e", borderRadius: "12px", padding: "16px", display: "flex", flexDirection: "column", gap: "12px" },
  camTitle:      { color: "#a0a3b1", fontSize: "13px", fontWeight: 700, letterSpacing: "0.5px" },
  camHints:      { display: "flex", flexDirection: "column", gap: "4px" },
  hint:          { color: "#4a5568", fontSize: "12px" },
  infoCard:      { background: "#1a1d2e", border: "1px solid #2a2d3e", borderRadius: "12px", padding: "16px", display: "flex", flexDirection: "column", gap: "10px" },
  infoRow:       { display: "flex", alignItems: "center", gap: "10px" },
  infoIcon:      { fontSize: "16px" },
  infoVal:       { color: "#e2e8f0", fontSize: "13px", fontWeight: 500 },
};
