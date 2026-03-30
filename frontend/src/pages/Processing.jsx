export default function Processing({ error, onRetry }) {
  // Detect retry-able finalization errors (vs permanent errors)
  const isRetryError = error && error.startsWith("FINALIZE_RETRY:");
  const errorMessage = isRetryError
    ? error.replace("FINALIZE_RETRY:", "").trim()
    : error;

  if (isRetryError) {
    return (
      <div style={S.page}>
        <div style={S.card}>
          <div style={S.errorIcon}>⚠️</div>
          <h2 style={S.title}>Report Generation Failed</h2>
          <p style={S.sub}>
            Your interview answers are fully saved. The report could not be generated.
            <br /><br />
            <strong style={{ color: "#e2e8f0" }}>Error:</strong>{" "}
            <span style={{ color: "#fc8181" }}>{errorMessage}</span>
          </p>
          <button style={S.retryBtn} onClick={onRetry}>
            🔄 Retry Generating Report
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={S.page}>
      <div style={S.card}>
        <div style={S.spinner} />
        <h2 style={S.title}>Analysing Your Interview</h2>
        <p style={S.sub}>
          Aggregating scores, computing analytics, and generating your personalised report…
        </p>
        <div style={S.steps}>
          {[
            "Aggregating question scores",
            "Running skill analysis",
            "Computing readiness index",
            "Generating final decision",
            "Building your scorecard",
          ].map((s, i) => (
            <div key={i} style={S.step}>
              <span style={S.dot} />
              <span style={S.stepText}>{s}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

const S = {
  page:      { minHeight: "100vh", background: "#0f1117", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "'Segoe UI',system-ui,sans-serif" },
  card:      { background: "#1a1d2e", border: "1px solid #2a2d3e", borderRadius: "16px", padding: "48px", maxWidth: "440px", textAlign: "center" },
  spinner:   { width: "56px", height: "56px", border: "4px solid #2a2d3e", borderTop: "4px solid #667eea", borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto 24px" },
  errorIcon: { fontSize: "48px", margin: "0 0 16px" },
  title:     { color: "#e2e8f0", fontSize: "22px", fontWeight: 700, margin: "0 0 10px" },
  sub:       { color: "#a0a3b1", fontSize: "14px", margin: "0 0 28px", lineHeight: 1.6 },
  steps:     { display: "flex", flexDirection: "column", gap: "12px", textAlign: "left" },
  step:      { display: "flex", alignItems: "center", gap: "12px" },
  dot:       { width: "8px", height: "8px", borderRadius: "50%", background: "#667eea", flexShrink: 0, animation: "pulse 1.5s infinite" },
  stepText:  { color: "#a0a3b1", fontSize: "13px" },
  retryBtn:  { background: "linear-gradient(135deg,#667eea,#764ba2)", color: "#fff", border: "none", borderRadius: "10px", padding: "14px 28px", fontSize: "15px", fontWeight: 600, cursor: "pointer", width: "100%", marginTop: "8px" },
};
