import { useEffect, useState } from "react";
import { useInterview } from "./hooks/useInterview";
import { api, AUDIO_OVERRIDE_OFF } from "./api/client";
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
    api.health()
      .then(h => {
        if (cancelled) return;
        setBackendCaps({
          audioEnabled: !AUDIO_OVERRIDE_OFF && h.audio_transcribe === "enabled",
          mode: h.mode || null,
          llmMode: h.llm_mode || null,
        });
      })
      .catch(() => {
        // Backend unreachable — keep defaults (audio off)
        if (!cancelled) {
          setBackendCaps(prev => ({ ...prev, audioEnabled: false }));
        }
      });
    return () => { cancelled = true; };
  }, []);

  if (iv.step === "landing")
    return <Landing onStart={() => iv.setStep("setup")} />;

  if (iv.step === "setup")
    return <Setup onSubmit={iv.setup} loading={iv.loading} error={iv.error} />;

  if (iv.step === "preinterview")
    return <PreInterview onBegin={iv.startInterview} setupData={iv.setupData} />;

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
    return <Results report={iv.report} onRestart={() => window.location.reload()} />;

  return null;
}
