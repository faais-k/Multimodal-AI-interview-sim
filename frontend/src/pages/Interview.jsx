import { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Volume2, Mic, PenLine, SkipForward, AlertTriangle, Activity, VideoOff, Send, Square } from "lucide-react";
import PostureMonitor from "../components/PostureMonitor";
import { useAudioRecorder } from "../hooks/useAudioRecorder";
import { useAntiCheat } from "../hooks/useAntiCheat";
import { AUDIO_INPUT_HINT } from "../api/client";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { ListeningIndicator } from "@/components/animations/ListeningIndicator";
import { ProcessingVisualization } from "@/components/animations/ProcessingVisualization";
import { cn } from "@/lib/utils";
import { LOGO_DATA } from "../assets/logo";


const TYPE_META = {
  self_intro: { label: "Introduction", color: "ascent-blue" },
  intro: { label: "Introduction", color: "ascent-blue" },
  project: { label: "Project", color: "warning" },
  technical: { label: "Technical", color: "secondary" },
  followup: { label: "Follow-up", color: "warning" },
  hr: { label: "Behavioural", color: "ascent-blue" },
  critical: { label: "Critical", color: "error" },
  wrapup: { label: "Wrap-up", color: "secondary" },
  warmup: { label: "Warm-up", color: "ascent-blue" },
};

export default function Interview({ 
  sessionId, 
  question, 
  questionNumber, 
  totalQuestions,
  loading, 
  evaluating, 
  onSubmitText, 
  onSubmitAudio, 
  onSkip,
  onExit,
  error,
  setupData, 
  audioEnabled = false 
}) {
  const [mode, setMode] = useState(audioEnabled ? "voice" : "text");
  const [answer, setAnswer] = useState("");
  const [submitting, setSub] = useState(false);
  const [cameraStream, setCameraStream] = useState(null);
  const [isListening, setIsListening] = useState(false);
  const [timeElapsed, setTimeElapsed] = useState(0);
  const [isAnswering, setIsAnswering] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [toast, setToast] = useState(null);
  const streamRef = useRef(null);
  const textareaRef = useRef(null);
  const timerRef = useRef(null);
  const modeRef = useRef(mode);

  useEffect(() => {
    modeRef.current = mode;
  }, [mode]);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    };
  }, []);

  const { 
    recording, 
    audioBlob, 
    audioURL, 
    micError, 
    volume,
    startRecording, 
    stopRecording, 
    reset: resetRec,
    mediaRef
  } = useAudioRecorder();
  
  // Wrap startRecording to cancel speech synthesis
  const handleStartRecording = () => {
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    startRecording();
  };

  const startRecRef = useRef(handleStartRecording);
  useEffect(() => {
    startRecRef.current = handleStartRecording;
  }, [handleStartRecording]);

  const antiCheat = useAntiCheat(sessionId, true);

  // Helper to skip with TTS cancellation
  const handleSkip = () => {
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    onSkip();
  };

  // Camera cleanup helper
  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    setCameraStream(null);
  }, []);

  useEffect(() => {
    navigator.mediaDevices.getUserMedia({ video: true, audio: false })
      .then(s => {
        streamRef.current = s;
        setCameraStream(s);
      })
      .catch(e => console.warn("Camera unavailable:", e));

    // Cleanup on page unload (beforeunload)
    const handleBeforeUnload = () => {
      stopCamera();
      if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    };

    // Cleanup on visibility change (tab switch/close)
    const handleVisibilityChange = () => {
      if (document.hidden && streamRef.current) {
        // Optional: pause camera when tab hidden to save resources
        // streamRef.current.getVideoTracks().forEach(t => t.enabled = false);
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      stopCamera();
      window.removeEventListener('beforeunload', handleBeforeUnload);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [stopCamera]);

  useEffect(() => {
    setAnswer(""); 
    resetRec(); 
    setSub(false);
    setSubmitError(null); // Clear any submission errors
    setIsListening(false);
    setTimeElapsed(0);
    setIsAnswering(false);
    if (timerRef.current) clearInterval(timerRef.current);
    
    // Safety check: if question is null, we might be transitioning
    if (!question) return;

    if (question.question && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(question.question);
      utterance.rate = 0.9;
      utterance.pitch = 1;
      
      utterance.onend = () => {
        setIsAnswering(true);
        timerRef.current = setInterval(() => {
          setTimeElapsed(prev => prev + 1);
        }, 1000);

        // Check current mode at callback time, not closure time
        // User may have switched to text mode during TTS playback
        const currentMode = modeRef.current;
        if (currentMode === "voice" && audioEnabled) {
          // Double-check: verify user didn't just switch modes
          setTimeout(() => {
            if (modeRef.current === "voice") {
              startRecRef.current();
            }
          }, 50);
        }
      };
      
      setTimeout(() => window.speechSynthesis.speak(utterance), 50);
    } else if (question.question) {
      setIsAnswering(true);
      timerRef.current = setInterval(() => {
        setTimeElapsed(prev => prev + 1);
      }, 1000);
    }
  }, [question?.id, resetRec]);

  // Toast auto-hide
  useEffect(() => {
    if (toast) {
      const t = setTimeout(() => setToast(null), 4000);
      return () => clearTimeout(t);
    }
  }, [toast]);

  // Sync anti-cheat warnings to Toast
  useEffect(() => {
    if (antiCheat?.showWarning && antiCheat?.warningMessage) {
      setToast({ message: antiCheat.warningMessage, type: "warning" });
    }
  }, [antiCheat?.showWarning, antiCheat?.warningMessage]);

  useEffect(() => {
    if (!audioEnabled && mode === "voice") {
      setMode("text");
    }
  }, [audioEnabled, mode]);

  // Sync isListening with recording state
  useEffect(() => {
    setIsListening(recording);
  }, [recording]);

  const handleTextSubmit = async () => {
    if (!answer.trim() || submitting || loading || evaluating) return;
    setSub(true);
    setSubmitError(null);
    try {
      const res = await onSubmitText(answer);
      // Check if anti-cheat triggered (raw_score 0.0 with specific reason)
      if (res && res.raw_score === 0 && res.scoring_method === "cheating_detected") {
        setToast({ 
          message: "⚠️ Response flagged as non-original or repetitive. Please provide a genuine answer.", 
          type: "error" 
        });
      }
    } catch (e) {
      console.error("Text submission failed:", e);
      setSubmitError(e.message || "Failed to submit answer. Please try again.");
    } finally {
      setSub(false);
    }
  };

  const handleAudioSubmit = async () => {
    if (!audioBlob || submitting || loading || evaluating) return;
    setSub(true);
    setSubmitError(null);
    try {
      const res = await onSubmitAudio(audioBlob);
      if (res && res.raw_score === 0 && res.scoring_method === "cheating_detected") {
        setToast({ 
          message: "⚠️ Response flagged. Please provide an original verbal answer.", 
          type: "error" 
        });
      }
    } catch (e) {
      console.error("Audio submission failed:", e);
      setSubmitError(e.message || "Failed to submit audio. Please try again.");
    } finally {
      setSub(false);
    }
  };

  const isAudioProcessing = !recording && !audioBlob && mediaRef.current && mediaRef.current.state === "inactive";

  const handleSpeakQuestion = () => {
    if ('speechSynthesis' in window && question?.question) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(question.question);
      utterance.rate = 0.9;
      utterance.pitch = 1;
      window.speechSynthesis.speak(utterance);
    }
  };

  const formatTime = (seconds) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  const qtype = question?.type || "technical";
  const meta = TYPE_META[qtype] || TYPE_META.technical;
  
  const canSubmitText = answer.trim().length >= 10 && !submitting && !loading && !evaluating;
  const canSubmitAudio = !!audioBlob && !submitting && !loading && !evaluating;
  const busy = submitting || loading || evaluating;

  // Determine current state for UI variant
  const getState = () => {
    if (evaluating) return "processing";
    if (mode === "voice" && recording) return "listening";
    if (mode === "voice" && isListening && !audioBlob) return "listening";
    return "input";
  };
  
  const currentState = getState();

  return (
    <div className="min-h-screen bg-surface-base flex flex-col">
      {/* Top Bar */}
      <header className="h-14 border-b border-border bg-surface-base/95 backdrop-blur-sm flex items-center justify-between px-6 flex-shrink-0 z-20">
        <div className="flex items-center gap-3">
          <img src={LOGO_DATA} alt="Ascent Logo" className="w-8 h-8 rounded-sm object-cover" />
          <span className="font-semibold text-sm">Ascent</span>
        </div>
        
        <div className="flex items-center gap-4">
          <span className="text-sm text-text-secondary">
            Question <span className="font-mono font-bold text-text-primary">{questionNumber}</span> 
            <span className="text-text-muted">/</span> 
            <span className="font-mono text-text-secondary">{totalQuestions || "?"}</span>
          </span>
          <div className="w-px h-4 bg-border" />
          <Badge variant="secondary" className="capitalize">{setupData?.expertiseLevel || "Intermediate"}</Badge>
        </div>
        
        <div className="flex items-center gap-3">
          {micError && (
            <div className="flex items-center gap-2 text-xs text-semantic-error animate-pulse">
              <AlertTriangle size={14} />
              {micError}
            </div>
          )}
          <div className="flex items-center gap-2 text-xs text-text-secondary">
            <span className="w-1.5 h-1.5 bg-ascent-blue rounded-full" />
            Posture OK
          </div>
          <div className="w-px h-4 bg-border mx-1" />
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={() => {
              if (window.confirm("Are you sure you want to end this interview? Your progress will be lost.")) {
                onExit();
              }
            }}
            className="text-xs text-semantic-error hover:text-red-700 hover:bg-red-50 h-8"
          >
            End Interview
          </Button>
        </div>
      </header>

      {/* Snackbar / Toast Notification */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: 50, x: "-50%" }}
            animate={{ opacity: 1, y: 0, x: "-50%" }}
            exit={{ opacity: 0, y: 20, x: "-50%" }}
            className={cn(
              "fixed bottom-8 left-1/2 z-50 px-6 py-3 rounded-sm shadow-xl flex items-center gap-3 min-w-[320px] max-w-md border",
              toast.type === "error" ? "bg-red-600 text-white border-red-500" : 
              toast.type === "warning" ? "bg-amber-500 text-white border-amber-400" :
              "bg-text-primary text-white border-border"
            )}
          >
            {toast.type === "error" || toast.type === "warning" ? <AlertTriangle size={18} /> : <Activity size={18} />}
            <span className="text-sm font-medium">{toast.message}</span>
            <button onClick={() => setToast(null)} className="ml-auto hover:opacity-70">
              <Square size={14} className="rotate-45" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Error Alert Bar */}
      {error && (
        <div className="bg-semantic-error text-white px-6 py-2 text-sm flex items-center justify-between animate-in fade-in slide-in-from-top-4">
          <div className="flex items-center gap-2">
            <AlertTriangle size={16} />
            <span>{error}</span>
          </div>
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={onExit}
            className="text-white hover:bg-white/10 h-7 text-xs border border-white/20"
          >
            Exit to Dashboard
          </Button>
        </div>
      )}

      {/* Main Interview Area */}
      <main className="flex-1 flex flex-col items-center justify-center px-6 py-8 relative">
        <AnimatePresence mode="wait">
          {/* Processing State */}
          {currentState === "processing" && (
            <motion.div
              key="processing"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="flex flex-col items-center"
            >
              <ProcessingVisualization size="md" className="mb-8" />
              <h2 className="text-xl font-semibold mb-2">Analyzing Response</h2>
              <p className="text-text-secondary text-sm">
                {mode === "voice" ? "Transcribing audio & evaluating…" : "Evaluating your answer…"}
              </p>
            </motion.div>
          )}

          {/* Listening State */}
          {currentState === "listening" && (
            <motion.div
              key="listening"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="w-full max-w-3xl"
            >
              {/* Question Type Badge */}
              <div className="flex items-center justify-center gap-2 mb-6">
                <Badge variant={meta.color === "ascent-blue" ? "default" : meta.color === "warning" ? "warning" : "secondary"}>
                  {meta.label}
                </Badge>
                <span className="text-xs text-text-muted">{qtype === "technical" ? "System Design" : ""}</span>
              </div>

              {/* Question */}
              <h1 className="text-xl font-medium text-center leading-relaxed mb-8 text-text-primary select-none">
                {loading ? "Fetching your next question..." : (question?.question || "Preparing your next question...")}
              </h1>

              {/* Listen Button & Timer */}
              <div className="flex justify-center items-center gap-4 mb-12">
                <button
                  onClick={handleSpeakQuestion}
                  disabled={!('speechSynthesis' in window)}
                  className="flex items-center gap-2 px-4 py-2 text-sm text-text-secondary hover:text-text-primary transition-colors border border-border rounded-sm hover:border-border-strong"
                >
                  <Volume2 size={16} />
                  Listen to question
                </button>
                {isAnswering && (
                  <div className="flex items-center gap-2 px-4 py-2 text-sm font-mono bg-surface-overlay border border-border rounded-sm">
                    <span className="w-2 h-2 bg-ascent-blue rounded-full animate-pulse" />
                    {formatTime(timeElapsed)}
                  </div>
                )}
              </div>

              {/* Listening Indicator */}
              <div className="flex flex-col items-center mb-10">
                <ListeningIndicator size="md" className="mb-3" volume={volume} />
                <span className="text-sm text-ascent-blue font-medium">
                  {isAnswering ? "AI is listening" : "AI is speaking..."}
                </span>
                <span className="text-xs text-text-muted mt-1">Speak your answer or switch to text mode</span>
              </div>

              {/* Recording Controls */}
              <div className="flex justify-center gap-4">
                <Button variant="outline" onClick={handleSkip}>
                  Skip Question
                </Button>
                <Button 
                  onClick={stopRecording}
                  className="flex items-center gap-2 bg-semantic-error hover:bg-red-700"
                >
                  <Square size={16} fill="currentColor" />
                  Stop Recording
                </Button>
              </div>
            </motion.div>
          )}

          {/* Input State (Text or Voice Ready) */}
          {currentState === "input" && (
            <motion.div
              key="input"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              className="w-full max-w-3xl"
            >
              {/* Question Type Badge */}
              <div className="flex items-center justify-center gap-2 mb-6">
                <Badge variant={meta.color === "ascent-blue" ? "default" : meta.color === "warning" ? "warning" : "secondary"}>
                  {meta.label}
                </Badge>
                <span className="text-xs text-text-muted">{qtype === "technical" ? "System Design" : ""}</span>
              </div>

              {/* Question */}
              <h1 className="text-xl font-medium text-center leading-relaxed mb-6 text-text-primary select-none">
                {loading ? "Fetching your next question..." : (question?.question || "Preparing your next question...")}
              </h1>

              {/* Listen Button & Timer */}
              <div className="flex justify-center items-center gap-4 mb-8">
                <button
                  onClick={handleSpeakQuestion}
                  disabled={!('speechSynthesis' in window)}
                  className="flex items-center gap-2 px-4 py-2 text-sm text-text-secondary hover:text-text-primary transition-colors border border-border rounded-sm hover:border-border-strong"
                >
                  <Volume2 size={16} />
                  Listen to question
                </button>
                {isAnswering && (
                  <div className="flex items-center gap-2 px-4 py-2 text-sm font-mono bg-surface-overlay border border-border rounded-sm">
                    <span className="w-2 h-2 bg-ascent-blue rounded-full animate-pulse" />
                    {formatTime(timeElapsed)}
                  </div>
                )}
              </div>

              {/* Mode Toggle */}
              {audioEnabled && (
                <div className="flex justify-center mb-6">
                  <div className="inline-flex bg-surface-overlay p-1 rounded-sm">
                    <button
                      className={cn(
                        "px-4 py-2 text-sm font-medium rounded-sm flex items-center gap-2 transition-all",
                        mode === "voice" 
                          ? "bg-text-primary text-white" 
                          : "text-text-secondary hover:text-text-primary"
                      )}
                      onClick={() => { setMode("voice"); setAnswer(""); }}
                      disabled={busy}
                    >
                      <Mic size={14} />
                      Voice Answer
                    </button>
                    <button
                      className={cn(
                        "px-4 py-2 text-sm font-medium rounded-sm flex items-center gap-2 transition-all",
                        mode === "text" 
                          ? "bg-text-primary text-white" 
                          : "text-text-secondary hover:text-text-primary"
                      )}
                      onClick={() => { setMode("text"); resetRec(); }}
                      disabled={busy}
                    >
                      <PenLine size={14} />
                      Type Answer
                    </button>
                  </div>
                </div>
              )}

              {/* Submit Error Display */}
              {submitError && (
                <div className="mb-4 p-3 bg-semantic-error-bg border border-semantic-error/20 rounded-sm flex items-center gap-2 text-sm text-semantic-error animate-in">
                  <AlertTriangle size={16} />
                  <span>{submitError}</span>
                  <button 
                    onClick={() => setSubmitError(null)}
                    className="ml-auto text-xs hover:underline"
                  >
                    Dismiss
                  </button>
                </div>
              )}

              {/* Text Input */}
              {mode === "text" && (
                <div className="space-y-4 animate-in">
                  <textarea
                    ref={textareaRef}
                    value={answer}
                    onChange={e => setAnswer(e.target.value)}
                    onPaste={e => {
                      e.preventDefault();
                      setToast({ message: "Pasting is disabled. Please type your answer.", type: "warning" });
                    }}
                    placeholder="Structure your answer with:\n• The approach you'd take\n• Key technical decisions and trade-offs\n• How you'd handle specific constraints"
                    rows={6}
                    disabled={busy}
                    className="w-full px-4 py-4 bg-white border border-border rounded-sm text-base leading-relaxed resize-none focus:outline-none focus:border-ascent-blue focus:ring-2 focus:ring-ascent-blue/10 transition-all"
                  />
                  <div className="flex items-center justify-between">
                    <span className={cn(
                      "text-sm font-mono",
                      answer.trim().split(/\s+/).filter(Boolean).length >= 50 
                        ? "text-ascent-blue" 
                        : "text-semantic-warning"
                    )}>
                      {answer.trim().split(/\s+/).filter(Boolean).length} / 50 words minimum
                    </span>
                    <div className="flex items-center gap-3">
                      <Button variant="outline" onClick={handleSkip} disabled={busy}>
                        Skip
                      </Button>
                      <Button 
                        onClick={handleTextSubmit}
                        disabled={!canSubmitText || busy}
                        className="flex items-center gap-2 px-8"
                      >
                        {busy ? (
                          <>
                            <span className="spinner" style={{width:16,height:16,borderWidth:2,borderColor:"white"}} />
                            Processing...
                          </>
                        ) : (
                          <>
                            Submit Answer
                            <Activity size={16} />
                          </>
                        )}
                      </Button>
                    </div>
                  </div>
                </div>
              )}

              {/* Voice - Idle */}
              {mode === "voice" && !recording && !audioBlob && (
                <div className="flex flex-col items-center gap-6 animate-in">
                  <Button 
                    onClick={handleStartRecording}
                    disabled={busy}
                    size="lg"
                    className="flex items-center gap-2 px-12 py-6 text-lg"
                  >
                    <Mic size={24} />
                    Start Recording
                  </Button>
                  <Button variant="ghost" onClick={handleSkip} disabled={busy}>
                    Skip Question
                  </Button>
                </div>
              )}

              {/* Voice - Recording */}
              {mode === "voice" && recording && (
                <div className="flex flex-col items-center gap-8 animate-in">
                  <div className="relative">
                    <div className="w-24 h-24 rounded-full border-4 border-ascent-blue/20 flex items-center justify-center">
                      <div 
                        className="w-20 h-20 rounded-full bg-ascent-blue flex items-center justify-center transition-transform duration-75"
                        style={{ transform: `scale(${1 + volume * 0.5})` }}
                      >
                        <Mic size={32} className="text-white" />
                      </div>
                    </div>
                    <div className="absolute -inset-4 rounded-full border border-ascent-blue/30 animate-ping opacity-20" />
                  </div>
                  <div className="text-center">
                    <p className="text-sm font-medium text-text-primary mb-1">Recording in progress...</p>
                    <p className="text-xs text-text-secondary">Click stop when you're finished answering</p>
                  </div>
                  <Button 
                    variant="destructive"
                    onClick={stopRecording}
                    size="lg"
                    className="px-10"
                  >
                    <Square size={18} fill="currentColor" />
                    Stop Recording
                  </Button>
                </div>
              )}

              {/* Voice - Recording Complete / Processing */}
              {mode === "voice" && (audioBlob || isAudioProcessing) && !recording && (
                <div className="space-y-6 animate-in">
                  <div className="flex items-center gap-4 p-5 bg-ascent-blue-subtle/30 border border-ascent-blue/30 rounded-sm">
                    <div className="w-12 h-12 bg-ascent-blue rounded-sm flex items-center justify-center">
                      <Activity size={24} className="text-white" />
                    </div>
                    <div className="flex-1">
                      <p className="font-medium text-text-primary">
                        {isAudioProcessing ? "Processing audio..." : "Recording ready"}
                      </p>
                      <p className="text-sm text-text-secondary">
                        {isAudioProcessing ? "Finalizing your answer..." : "Review your answer before submitting"}
                      </p>
                    </div>
                    {!isAudioProcessing && (
                      <Button variant="outline" onClick={resetRec} disabled={busy} size="sm">
                        Re-record
                      </Button>
                    )}
                  </div>

                  {audioURL && (
                    <div className="p-2 bg-surface-overlay rounded-sm">
                      <audio controls src={audioURL} className="w-full" />
                    </div>
                  )}

                  <div className="flex items-center justify-between pt-4">
                    <Button variant="ghost" onClick={handleSkip} disabled={busy}>
                      Skip
                    </Button>
                    <Button 
                      onClick={handleAudioSubmit}
                      disabled={!audioBlob || busy || isAudioProcessing}
                      className="flex items-center gap-2 px-12"
                    >
                      {busy ? (
                        <>
                          <span className="spinner" style={{width:16,height:16,borderWidth:2,borderColor:"white"}} />
                          Evaluating...
                        </>
                      ) : isAudioProcessing ? (
                        "Processing..."
                      ) : (
                        <>
                          Submit Answer
                          <Send size={18} />
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Camera Picture-in-Picture */}
        <Card className="static mt-8 w-full max-w-sm mx-auto overflow-hidden shadow-sm z-10 border-border/50 xl:fixed xl:top-20 xl:right-6 xl:mt-0 xl:w-52">
          <div className="bg-text-primary relative">
            {cameraStream ? (
              <PostureMonitor sessionId={sessionId} stream={cameraStream} />
            ) : (
              <div className="flex flex-col items-center justify-center h-full gap-2 p-6">
                <VideoOff size={24} className="text-text-muted" />
                <span className="text-xs text-text-muted font-medium">Camera off</span>
              </div>
            )}
            <div className="absolute top-2 left-2 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 bg-ascent-blue rounded-full animate-pulse" />
              <span className="text-[10px] text-white/60 font-mono">LIVE</span>
            </div>
          </div>
        </Card>
      </main>

      {/* Premium Toast Notification System */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className={cn(
              "fixed bottom-8 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 px-5 py-3.5 rounded-sm shadow-2xl border backdrop-blur-md",
              toast.type === "error" ? "bg-error/90 border-error/20 text-white" 
              : toast.type === "warning" ? "bg-amber-600/90 border-amber-500/20 text-white"
              : "bg-ascent-blue/90 border-ascent-blue/20 text-white"
            )}
          >
            {toast.type === "error" ? <AlertTriangle size={18} /> 
             : toast.type === "warning" ? <AlertTriangle size={18} /> 
             : <Activity size={18} />}
            <span className="text-sm font-medium tracking-tight">{toast.message}</span>
            <button 
              onClick={() => setToast(null)}
              className="ml-2 p-1 hover:bg-white/10 rounded-full transition-colors"
            >
              <Square size={12} fill="currentColor" className="opacity-70" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
