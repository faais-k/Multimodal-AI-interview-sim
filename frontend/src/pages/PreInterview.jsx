import { useEffect, useRef, useState } from "react";

const CHECKS = [
  { id: "camera", label: "Camera access",     icon: "📷" },
  { id: "mic",    label: "Microphone access", icon: "🎤" },
  { id: "full",   label: "Fullscreen ready",  icon: "⛶"  },
];

export default function PreInterview({ onBegin, setupData }) {
  const [checks, setChecks] = useState({ camera: false, mic: false, full: false });
  const [stream, setStream] = useState(null);
  const [starting, setStarting] = useState(false);
  const [camError, setCamError] = useState(null);
  const videoRef  = useRef();
  const streamRef = useRef(null);   // ref so cleanup always sees latest stream

  useEffect(() => {
    (async () => {
      try {
        const s = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
        streamRef.current = s;
        setStream(s);
        setChecks(c => ({ ...c, camera: true, mic: true }));
        if (videoRef.current) videoRef.current.srcObject = s;
      } catch (e) {
        console.warn("Camera/mic:", e);
        setCamError("Camera or microphone not accessible. You can still proceed.");
      }
    })();
    // Use ref so cleanup always has the latest stream regardless of closure
    return () => streamRef.current?.getTracks().forEach(t => t.stop());
  }, []);

  const begin = async () => {
    setStarting(true);
    setChecks(c => ({ ...c, full: true }));
    try { await document.documentElement.requestFullscreen(); } catch (_) {}
    if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop());
    onBegin();
  };

  // Allow proceeding with camera warning rather than hard-blocking
  const allReady = true;

  return (
    <div style={S.page}>
      <div style={S.card}>
        <div style={S.header}>
          <h2 style={S.title}>Ready to Start?</h2>
          <p style={S.sub}>Hi <strong style={{color:"#667eea"}}>{setupData?.name || "Candidate"}</strong> — let's run a quick check before your interview begins.</p>
        </div>

        <div style={S.body}>
          <div style={S.previewWrap}>
            <video ref={videoRef} autoPlay muted playsInline style={S.video} />
            {!checks.camera && <div style={S.noCamera}>📷 Camera not detected</div>}
          </div>

          <div style={S.checks}>
            {CHECKS.map(c => (
              <div key={c.id} style={{ ...S.checkRow, ...(checks[c.id] ? S.checkOk : {}) }}>
                <span style={S.checkIcon}>{c.icon}</span>
                <span style={S.checkLabel}>{c.label}</span>
                <span style={S.checkStatus}>{checks[c.id] ? "✅ Ready" : "⏳ Checking…"}</span>
              </div>
            ))}
          </div>

          {camError && <div style={{background:"#ed893622",border:"1px solid #ed893655",borderRadius:"8px",padding:"10px 14px",color:"#ed8936",fontSize:"13px",marginBottom:"16px"}}>⚠️ {camError}</div>}
          <div style={S.rules}>
            <div style={S.rulesTitle}>📋 Interview Rules</div>
            <ul style={S.rulesList}>
              <li>This is a <strong>proctored interview</strong> — tab switches and fullscreen exits are logged.</li>
              <li>Answer each question clearly — you can type or speak your answer.</li>
              <li>Follow-up questions may be asked based on your responses.</li>
              <li>Stay seated in front of your camera throughout the interview.</li>
            </ul>
          </div>

          <button style={{ ...S.btn, ...(!allReady || starting ? S.btnDisabled : {}) }}
            onClick={begin} disabled={!allReady || starting}>
            {starting ? "⏳ Starting interview…" : "🎯 Begin Interview (Fullscreen)"}
          </button>
        </div>
      </div>
    </div>
  );
}

const S = {
  page:        { minHeight:"100vh", background:"#0f1117", display:"flex", alignItems:"center", justifyContent:"center", padding:"24px", fontFamily:"'Segoe UI',system-ui,sans-serif" },
  card:        { background:"#1a1d2e", border:"1px solid #2a2d3e", borderRadius:"16px", width:"100%", maxWidth:"600px", overflow:"hidden" },
  header:      { background:"linear-gradient(135deg,#667eea,#764ba2)", padding:"28px 32px" },
  title:       { color:"#fff", margin:"0 0 8px", fontSize:"24px", fontWeight:700 },
  sub:         { color:"rgba(255,255,255,0.85)", margin:0, fontSize:"15px" },
  body:        { padding:"28px 32px" },
  previewWrap: { position:"relative", background:"#0f1117", borderRadius:"12px", overflow:"hidden", aspectRatio:"16/9", marginBottom:"24px" },
  video:       { width:"100%", height:"100%", objectFit:"cover", transform:"scaleX(-1)" },
  noCamera:    { position:"absolute", inset:0, display:"flex", alignItems:"center", justifyContent:"center", color:"#a0a3b1", fontSize:"16px" },
  checks:      { display:"flex", flexDirection:"column", gap:"10px", marginBottom:"24px" },
  checkRow:    { display:"flex", alignItems:"center", gap:"12px", background:"#0f1117", border:"1px solid #2a2d3e", borderRadius:"8px", padding:"12px 16px", transition:"all .3s" },
  checkOk:     { border:"1px solid #48bb7833", background:"#48bb7811" },
  checkIcon:   { fontSize:"20px" },
  checkLabel:  { flex:1, color:"#e2e8f0", fontSize:"14px", fontWeight:500 },
  checkStatus: { color:"#a0a3b1", fontSize:"13px" },
  rules:       { background:"#0f1117", borderRadius:"10px", padding:"16px 20px", marginBottom:"24px" },
  rulesTitle:  { fontWeight:700, color:"#e2e8f0", marginBottom:"10px", fontSize:"14px" },
  rulesList:   { margin:0, paddingLeft:"20px", color:"#a0a3b1", fontSize:"13px", lineHeight:1.7 },
  btn:         { width:"100%", padding:"16px", background:"linear-gradient(135deg,#667eea,#764ba2)", border:"none", borderRadius:"10px", color:"#fff", fontSize:"16px", fontWeight:700, cursor:"pointer" },
  btnDisabled: { opacity:0.5, cursor:"not-allowed" },
};
