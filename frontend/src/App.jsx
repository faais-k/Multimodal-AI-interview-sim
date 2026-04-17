import { useInterview } from "./hooks/useInterview";
import Landing      from "./pages/Landing";
import Setup        from "./pages/Setup";
import PreInterview from "./pages/PreInterview";
import Interview    from "./pages/Interview";
import Processing   from "./pages/Processing";
import Results      from "./pages/Results";

export default function App() {
  const iv = useInterview();

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
      />
    );

  if (iv.step === "processing")
    return <Processing error={iv.error} onRetry={iv.retryFinalize} />;

  if (iv.step === "results")
    return <Results report={iv.report} onRestart={() => window.location.reload()} />;

  return null;
}
