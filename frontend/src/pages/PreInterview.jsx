import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Check, AlertCircle, Video, Mic, FileQuestion, Play, Info, Square, RefreshCw } from "lucide-react";
import { api } from "../api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import { useAudioRecorder } from "../hooks/useAudioRecorder";

export default function PreInterview({ onBegin, setupData, sessionId }) {
  const [checks, setChecks] = useState({ camera: false, mic: false });
  const [starting, setStarting] = useState(false);
  const [camError, setCamError] = useState(null);
  const [generating, setGenerating] = useState(true);
  const [questionsReady, setQuestionsReady] = useState(false);
  const [genError, setGenError] = useState(null);
  const [hfFallback, setHfFallback] = useState(false);
  const [skeletonEnabled, setSkeletonEnabled] = useState(true);
  const [testRecording, setTestRecording] = useState(false);
  const videoRef = useRef();
  const streamRef = useRef(null);

  const {
    recording,
    audioURL,
    volume,
    startRecording: startRec,
    stopRecording: stopRec,
    reset: resetRec
  } = useAudioRecorder();

  const requestPermissions = async () => {
    try {
      setCamError(null);
      const s = await navigator.mediaDevices.getUserMedia({ 
        video: { width: 1280, height: 720 }, 
        audio: true 
      });
      streamRef.current = s;
      setChecks({ camera: true, mic: true });
      if (videoRef.current) videoRef.current.srcObject = s;
    } catch (e) {
      console.warn("Camera/mic access failed:", e);
      if (e.name === 'NotAllowedError' || e.name === 'PermissionDeniedError') {
        setCamError("Access denied. Please click the camera icon in your browser address bar to allow access.");
      } else {
        setCamError("Hardware not found or busy. Please check your camera and microphone connection.");
      }
    }
  };

  // Initial probe (some browsers allow this without interaction if already granted)
  useEffect(() => {
    const probe = async () => {
      try {
        const result = await navigator.permissions.query({ name: 'camera' });
        if (result.state === 'granted') {
          requestPermissions();
        }
      } catch (e) {
        // Fallback for browsers that don't support permissions.query for camera
        requestPermissions();
      }
    };
    probe();
    return () => streamRef.current?.getTracks().forEach(t => t.stop());
  }, []);

  const [micCalibrated, setMicCalibrated] = useState(false);
  const [micWarning, setMicWarning] = useState(false);
  const maxVolumeRef = useRef(0);

  // Background question generation
  useEffect(() => {
    if (!sessionId) {
      setGenError("No session found. Please go back and set up your interview again.");
      setGenerating(false);
      return;
    }
    
    let cancelled = false;
    const abortControllers = [];
    
    const createAbortableRequest = () => {
      const controller = new AbortController();
      abortControllers.push(controller);
      return controller;
    };
    
    const generateQuestions = async () => {
      try {
        setGenerating(true);
        
        // Post setup data to backend before generating plan
        if (setupData && !cancelled) {
          const jobController = createAbortableRequest();
          await api.setJobDescription({
            session_id: sessionId,
            job_role: setupData.jobRole || "",
            job_description: setupData.jobDescription || "",
            company: setupData.company || "",
          });
          if (cancelled) return;
          
          const profileController = createAbortableRequest();
          await api.setCandidateProfile({
            session_id: sessionId,
            name: setupData.name || "",
            expertise_level: setupData.expertiseLevel || "fresher",
            experience: setupData.experience || "",
            education: setupData.education || "",
          });
          if (cancelled) return;
        }
        
        const result = await api.generateDynamicInterview(sessionId);
        
        if (!cancelled) {
          if (result.status === "ok") {
            setQuestionsReady(true);
            setGenerating(false);
            if (result.llm_fallback) {
              setHfFallback(true);
            }
          } else {
            // Unexpected status but not an exception
            throw new Error("Generation failed");
          }
        }
      } catch (e) {
        if (cancelled) return;
        console.warn("Dynamic generation failed, falling back to static:", e);
        
        try {
          // FALLBACK: Generate static plan if dynamic fails
          const fallback = await api.generatePlan(sessionId);
          if (cancelled) return;
          
          if (fallback.status === "ok") {
            setQuestionsReady(true);
            setGenError("Using standard questions (dynamic research failed)");
          } else {
            setGenError("Could not generate questions. Please try restarting.");
          }
        } catch (err) {
          if (!cancelled) {
            setGenError(err.message || "Failed to generate questions");
          }
        } finally {
          if (!cancelled) {
            setGenerating(false);
          }
        }
      }
    };
    
    generateQuestions();
    
    return () => { 
      cancelled = true;
      // Abort any pending requests
      abortControllers.forEach(controller => {
        try {
          controller.abort();
        } catch (e) {
          // Ignore abort errors
        }
      });
    };
  }, [sessionId]);

  useEffect(() => {
    if (testRecording) {
      maxVolumeRef.current = Math.max(maxVolumeRef.current, volume);
    }
  }, [volume, testRecording]);

  const begin = async () => {
    setStarting(true);
    try { await document.documentElement.requestFullscreen(); } catch (_) {}
    if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop());
    resetRec();
    await onBegin();
  };

  const startMicTest = () => {
    setTestRecording(true);
    setMicCalibrated(false);
    setMicWarning(false);
    maxVolumeRef.current = 0;
    resetRec();
    startRec();
    setTimeout(() => {
      stopRec();
      setTestRecording(false);
      if (maxVolumeRef.current > 0.02) {
        setMicCalibrated(true);
      } else {
        setMicWarning(true);
      }
    }, 3000);
  };

  const checklistItems = [
    { 
      id: "camera", 
      label: "Camera Accessible", 
      icon: Video,
      done: checks.camera, 
      status: checks.camera ? "verified" : camError ? "warning" : "pending"
    },
    { 
      id: "mic", 
      label: "Microphone Calibrated", 
      icon: Mic,
      done: checks.mic && micCalibrated, 
      status: (checks.mic && micCalibrated) ? "verified" : micWarning ? "warning" : "pending"
    },
    { 
      id: "questions", 
      label: "Questions Generated", 
      icon: FileQuestion,
      done: questionsReady, 
      status: questionsReady ? "ready" : genError ? "error" : "generating"
    },
  ];

  const completedChecks = checklistItems.filter(i => i.done).length;

  return (
    <div className="min-h-screen bg-surface-base">
      {/* Header */}
      <header className="border-b border-border">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-14 flex items-center">
          <div className="flex items-center gap-2">
            <svg width="24" height="24" viewBox="0 0 36 36" fill="none">
              <rect width="36" height="36" rx="6" fill="#059669"/>
              <path d="M8 26 L14 18 L18 22 L22 14 L28 26" stroke="white" strokeWidth="2.5" strokeLinejoin="round" fill="none"/>
            </svg>
            <span className="font-semibold">Ascent</span>
          </div>
          <div className="ml-auto flex items-center gap-2 text-sm text-text-muted">
            <span className="w-2 h-2 bg-veridian rounded-full" />
            Step 2 of 3
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-8 sm:py-10">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        >
          {/* Header */}
          <div className="mb-8">
            <h1 className="text-2xl font-semibold mb-2">Pre-Flight Check</h1>
            <p className="text-text-secondary">Verify your environment before the interview begins.</p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8">
            {/* Checklist (60%) */}
            <div className="lg:col-span-7 space-y-4 min-w-0">
              {checklistItems.map((item, idx) => (
                <motion.div
                  key={item.id}
                  initial={{ opacity: 0, x: -12 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: idx * 0.1 }}
                >
                  <Card className={cn(
                    "p-5 transition-all",
                    item.done ? "border-veridian bg-veridian-subtle/10" : 
                    item.status === "generating" ? "border-semantic-warning bg-semantic-warning-bg/30" : ""
                  )}>
                    <div className="flex flex-col sm:flex-row sm:items-start gap-4">
                      <div className={cn(
                        "w-10 h-10 rounded-sm flex items-center justify-center transition-all",
                        item.done ? "bg-veridian text-white" :
                        item.status === "generating" ? "bg-semantic-warning-bg text-semantic-warning" :
                        item.status === "warning" ? "bg-semantic-warning-bg text-semantic-warning" :
                        "bg-surface-overlay text-text-muted"
                      )}>
                        {item.done ? (
                          <Check size={20} />
                        ) : item.status === "generating" ? (
                          <motion.div
                            animate={{ rotate: 360 }}
                            transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                          >
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <circle cx="12" cy="12" r="10" strokeDasharray="60" strokeDashoffset="20" />
                            </svg>
                          </motion.div>
                        ) : (
                          <item.icon size={20} />
                        )}
                      </div>
                      <div className="flex-1">
                        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-1">
                          <h3 className={cn(
                            "font-semibold",
                            item.done ? "text-text-primary" : "text-text-primary"
                          )}>
                            {item.label}
                          </h3>
                          <Badge 
                            variant={
                              item.done ? "success" : 
                              item.status === "generating" ? "warning" :
                              item.status === "warning" ? "warning" : "secondary"
                            }
                          >
                            {item.done ? "Verified" : 
                             item.status === "generating" ? "Generating..." :
                             item.status === "warning" ? "Review" : "Pending"}
                          </Badge>
                        </div>
                        <p className="text-sm text-text-secondary">
                          {item.id === "camera" && (item.done ? "Webcam detected and responsive. Video feed active." : camError || "Requires camera access for proctoring.")}
                          {item.id === "mic" && (item.done ? "Microphone calibrated. Audio levels are good." : micWarning ? "Audio too quiet. Speak louder during the test." : "Please test your microphone before proceeding.")}
                          {item.id === "questions" && (item.done ? (hfFallback ? "8 tailored questions ready (Standard Quality)." : "8 tailored questions ready. System design focus detected.") : 
                            genError ? `${genError} - Will use fallback questions.` : "Researching company • Analyzing resume...")}
                        </p>

                        {item.id === "camera" && !item.done && (
                          <div className="mt-3">
                            <Button size="sm" onClick={requestPermissions} className="h-8 text-xs bg-veridian hover:bg-veridian-dark">
                              <Video size={14} className="mr-1.5" /> Grant Camera & Mic Access
                            </Button>
                            {camError && (
                              <p className="mt-2 text-xs text-semantic-error flex items-center gap-1">
                                <AlertCircle size={12} /> {camError}
                              </p>
                            )}
                          </div>
                        )}
                        
                        {item.id === "mic" && checks.mic && (
                          <div className="mt-4 space-y-3">
                            <div className="flex items-center gap-2">
                              <div className="h-1.5 bg-surface-overlay rounded-sm flex-1 overflow-hidden">
                                <motion.div 
                                  className="h-full bg-veridian rounded-sm"
                                  animate={{ width: `${Math.min(volume * 100 * 2, 100)}%` }}
                                  transition={{ type: "spring", stiffness: 300, damping: 20 }}
                                />
                              </div>
                              <span className="text-xs text-text-muted font-mono">{Math.round(volume * 100)}%</span>
                            </div>
                            
                            <div className="flex flex-col sm:flex-row sm:items-center gap-3">
                              {!testRecording && (
                                <Button size="sm" variant="outline" onClick={startMicTest} className="h-8 text-xs">
                                  <Mic size={14} className="mr-1.5" /> Test Mic (3s)
                                </Button>
                              )}
                              
                              {testRecording && (
                                <Button size="sm" variant="secondary" disabled className="h-8 text-xs animate-pulse">
                                  <Square size={14} className="mr-1.5 fill-current" /> Recording...
                                </Button>
                              )}
                              
                              {audioURL && !testRecording && (
                                <div className="flex items-center gap-2 w-full">
                                  <audio src={audioURL} controls className="h-8 flex-1 min-w-0 sm:max-w-[200px]" />
                                  <Button size="sm" variant="ghost" onClick={() => resetRec()} className="h-8 px-2">
                                    <RefreshCw size={14} />
                                  </Button>
                                </div>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  </Card>
                </motion.div>
              ))}

              {hfFallback && (
                <motion.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="p-4 bg-surface-overlay border border-border rounded-md flex items-start gap-3"
                >
                  <Info size={18} className="text-text-muted flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-text-secondary">
                    <span className="font-medium">System Note:</span> Hugging Face Inference is currently at capacity. 
                    We are falling back to <span className="text-veridian">local CPU models</span> for scoring and question selection. 
                  </p>
                </motion.div>
              )}

              {genError && (
                <motion.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="p-4 bg-semantic-warning-bg border border-semantic-warning/20 rounded-md flex items-start gap-3"
                >
                  <AlertCircle size={18} className="text-semantic-warning flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-semantic-warning">{genError} - You can still proceed with default questions.</p>
                </motion.div>
              )}

              {/* Begin Button */}
              <div className="pt-6 border-t border-border flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <p className="text-sm text-text-secondary">
                  <span className="text-veridian font-medium">{completedChecks}</span> of <span className="font-medium">{checklistItems.length}</span> checks complete
                </p>
                <Button 
                  onClick={begin}
                  disabled={starting || (generating && !genError) || (checks.mic && !micCalibrated)}
                  className="flex items-center gap-2 w-full sm:w-auto"
                  size="lg"
                >
                  {starting ? (
                    <>
                      <motion.div
                        animate={{ rotate: 360 }}
                        transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                      >
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <circle cx="12" cy="12" r="10" strokeDasharray="60" strokeDashoffset="20" />
                        </svg>
                      </motion.div>
                      Starting...
                    </>
                  ) : (
                    <>
                      <Play size={16} fill="currentColor" />
                      Begin Interview
                    </>
                  )}
                </Button>
              </div>
            </div>

            {/* Camera Preview & Session Details (40%) */}
            <div className="lg:col-span-5 space-y-6 min-w-0">
              {/* Camera Preview */}
              <Card className="overflow-hidden">
                <div className="aspect-video bg-text-primary relative flex items-center justify-center">
                  {camError ? (
                    <div className="text-center text-white/60">
                      <Video size={48} className="mx-auto mb-2 opacity-50" />
                      <p className="text-sm">Camera Preview</p>
                      <p className="text-xs mt-2 opacity-60">{camError}</p>
                    </div>
                  ) : (
                    <video 
                      ref={videoRef} 
                      autoPlay 
                      playsInline 
                      muted 
                      className="w-full h-full object-cover scale-x-[-1]"
                    />
                  )}
                  <div className="absolute top-3 right-3 flex items-center gap-2">
                    <span className="w-2 h-2 bg-semantic-error rounded-full animate-pulse" />
                    <span className="text-xs text-white/80 font-mono">REC</span>
                  </div>
                  <div className="absolute bottom-3 left-3 text-xs text-white/60 font-mono">
                    Posture monitoring active
                  </div>
                </div>
                <div className="p-4 border-t border-border">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-text-secondary">Skeleton overlay</span>
                    <button 
                      onClick={() => setSkeletonEnabled(!skeletonEnabled)}
                      className={cn(
                        "relative w-11 h-6 rounded-sm transition-colors",
                        skeletonEnabled ? "bg-veridian" : "bg-surface-overlay"
                      )}
                    >
                      <span className={cn(
                        "absolute top-1 w-4 h-4 bg-white rounded-sm shadow-sm transition-all",
                        skeletonEnabled ? "right-1" : "left-1"
                      )} />
                    </button>
                  </div>
                </div>
              </Card>

              {/* Session Card */}
              <Card className="bg-surface-overlay border-border">
                <CardHeader className="pb-3">
                  <CardTitle className="text-xs font-semibold text-text-secondary uppercase tracking-wide">
                    Session Configuration
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3 text-sm">
                    {setupData?.name && (
                      <div className="flex justify-between">
                        <span className="text-text-secondary">Candidate</span>
                        <span className="font-medium text-text-primary">{setupData.name}</span>
                      </div>
                    )}
                    {setupData?.jobRole && (
                      <div className="flex justify-between">
                        <span className="text-text-secondary">Target Role</span>
                        <span className="font-medium text-text-primary">{setupData.jobRole}</span>
                      </div>
                    )}
                    {setupData?.company && (
                      <div className="flex justify-between">
                        <span className="text-text-secondary">Company</span>
                        <span className="font-medium text-text-primary">{setupData.company}</span>
                      </div>
                    )}
                    {setupData?.expertiseLevel && (
                      <div className="flex justify-between">
                        <span className="text-text-secondary">Level</span>
                        <span className="font-medium text-text-primary capitalize">{setupData.expertiseLevel}</span>
                      </div>
                    )}
                    <div className="flex justify-between pt-2 border-t border-border">
                      <span className="text-text-secondary">Expected Duration</span>
                      <span className="font-medium text-text-primary font-mono">25-35 min</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </motion.div>
      </main>
    </div>
  );
}
