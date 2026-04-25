import { useEffect, useState } from "react";
import { useInterview } from "./hooks/useInterview";
import { api } from "./api/client";
import Landing      from "./pages/Landing";
import Setup        from "./pages/Setup";
import PreInterview from "./pages/PreInterview";
import Interview    from "./pages/Interview";
import Processing   from "./pages/Processing";
import Results      from "./pages/Results";

export default function App() {
  const iv = useInterview();

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

  if (iv.step === "landing")
    return <Landing onStart={() => iv.setStep("setup")} />;

  if (iv.step === "setup")
    return <Setup onSubmit={iv.setup} loading={iv.loading} error={iv.error} />;

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
