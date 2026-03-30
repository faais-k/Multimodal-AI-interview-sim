import { useRef, useState } from "react";

const LEVELS = ["fresher", "intermediate", "experienced"];

export default function Setup({ onSubmit, loading, error }) {
  const [form, setForm]     = useState({
    name: "", jobRole: "", expertiseLevel: "fresher",
    jobDescription: "", company: "", experience: "", education: "",
  });
  const [file, setFile]     = useState(null);
  const [drag, setDrag]     = useState(false);
  const fileRef             = useRef();

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));
  const canSubmit = form.name.trim() && form.jobRole.trim() && file;

  const handleDrop = e => {
    e.preventDefault(); setDrag(false);
    const f = e.dataTransfer.files[0];
    const allowed = ["application/pdf",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "application/msword"];
    if (f && (allowed.includes(f.type) || f.name.match(/\.(pdf|docx|doc)$/i))) setFile(f);
  };

  const submit = e => {
    e.preventDefault();
    if (!canSubmit) return;
    onSubmit({ ...form, resumeFile: file });
  };

  return (
    <div style={S.page}>
      <div style={S.card}>
        {/* Header */}
        <div style={S.header}>
          <div style={S.logo}>🤖</div>
          <h1 style={S.title}>AI Interview Simulator</h1>
          <p style={S.subtitle}>Practice real interviews. Get detailed feedback.</p>
        </div>

        <form onSubmit={submit} style={S.form}>
          {/* Required fields */}
          <div style={S.section}>
            <div style={S.sectionLabel}>REQUIRED</div>
            <div style={S.row}>
              <div style={S.field}>
                <label style={S.label}>Full Name</label>
                <input style={S.input} placeholder="Your full name"
                  value={form.name} onChange={e => set("name", e.target.value)} />
              </div>
              <div style={S.field}>
                <label style={S.label}>Target Job Role</label>
                <input style={S.input} placeholder="e.g. Machine Learning Engineer"
                  value={form.jobRole} onChange={e => set("jobRole", e.target.value)} />
              </div>
            </div>

            <div style={S.field}>
              <label style={S.label}>Expertise Level</label>
              <div style={S.levelRow}>
                {LEVELS.map(l => (
                  <button key={l} type="button"
                    style={{ ...S.levelBtn, ...(form.expertiseLevel === l ? S.levelActive : {}) }}
                    onClick={() => set("expertiseLevel", l)}>
                    {l.charAt(0).toUpperCase() + l.slice(1)}
                  </button>
                ))}
              </div>
            </div>

            {/* Resume upload */}
            <div style={S.field}>
              <label style={S.label}>Resume (PDF)</label>
              <div
                style={{ ...S.dropzone, ...(drag ? S.dropActive : {}), ...(file ? S.dropDone : {}) }}
                onDragOver={e => { e.preventDefault(); setDrag(true); }}
                onDragLeave={() => setDrag(false)}
                onDrop={handleDrop}
                onClick={() => fileRef.current.click()}>
                <input ref={fileRef} type="file" accept=".pdf,.docx,.doc" style={{ display: "none" }}
                  onChange={e => { if (e.target.files[0]) setFile(e.target.files[0]); }} />
                {file
                  ? <><span style={S.dropIcon}>✅</span><span>{file.name}</span></>
                  : <><span style={S.dropIcon}>📄</span><span>Drop your resume PDF or DOCX here or click to browse</span></>
                }
              </div>
            </div>
          </div>

          {/* Optional fields */}
          <div style={S.section}>
            <div style={S.sectionLabel}>OPTIONAL — IMPROVES QUESTION QUALITY</div>
            <div style={S.row}>
              <div style={S.field}>
                <label style={S.label}>Company</label>
                <input style={S.input} placeholder="Target company (optional)"
                  value={form.company} onChange={e => set("company", e.target.value)} />
              </div>
              <div style={S.field}>
                <label style={S.label}>Education</label>
                <input style={S.input} placeholder="e.g. B.Sc Computer Science"
                  value={form.education} onChange={e => set("education", e.target.value)} />
              </div>
            </div>
            <div style={S.field}>
              <label style={S.label}>Job Description</label>
              <textarea style={S.textarea} rows={3}
                placeholder="Paste the job description here for highly targeted questions…"
                value={form.jobDescription} onChange={e => set("jobDescription", e.target.value)} />
            </div>
            <div style={S.field}>
              <label style={S.label}>Experience Summary</label>
              <textarea style={S.textarea} rows={2}
                placeholder="Brief summary of your work experience…"
                value={form.experience} onChange={e => set("experience", e.target.value)} />
            </div>
          </div>

          {error && <div style={S.error}>❌ {error}</div>}

          <button style={{ ...S.submitBtn, ...((!canSubmit || loading) ? S.submitDisabled : {}) }}
            type="submit" disabled={!canSubmit || loading}>
            {loading ? "⏳ Setting up your interview…" : "🚀 Proceed to Interview Setup"}
          </button>
        </form>
      </div>
    </div>
  );
}

const S = {
  page:        { minHeight:"100vh", background:"#0f1117", display:"flex", alignItems:"center", justifyContent:"center", padding:"24px", fontFamily:"'Segoe UI',system-ui,sans-serif" },
  card:        { background:"#1a1d2e", border:"1px solid #2a2d3e", borderRadius:"16px", width:"100%", maxWidth:"720px", overflow:"hidden" },
  header:      { background:"linear-gradient(135deg,#667eea,#764ba2)", padding:"32px", textAlign:"center" },
  logo:        { fontSize:"48px", marginBottom:"8px" },
  title:       { color:"#fff", fontSize:"28px", fontWeight:700, margin:"0 0 8px" },
  subtitle:    { color:"rgba(255,255,255,0.8)", margin:0, fontSize:"15px" },
  form:        { padding:"32px" },
  section:     { marginBottom:"28px" },
  sectionLabel:{ fontSize:"11px", fontWeight:700, color:"#667eea", letterSpacing:"1.5px", marginBottom:"16px" },
  row:         { display:"grid", gridTemplateColumns:"1fr 1fr", gap:"16px" },
  field:       { marginBottom:"16px" },
  label:       { display:"block", color:"#a0a3b1", fontSize:"13px", fontWeight:600, marginBottom:"6px" },
  input:       { width:"100%", background:"#0f1117", border:"1px solid #2a2d3e", borderRadius:"8px", padding:"10px 14px", color:"#e2e8f0", fontSize:"14px", outline:"none", boxSizing:"border-box" },
  textarea:    { width:"100%", background:"#0f1117", border:"1px solid #2a2d3e", borderRadius:"8px", padding:"10px 14px", color:"#e2e8f0", fontSize:"14px", outline:"none", resize:"vertical", boxSizing:"border-box" },
  levelRow:    { display:"flex", gap:"12px" },
  levelBtn:    { flex:1, padding:"10px", background:"#0f1117", border:"1px solid #2a2d3e", borderRadius:"8px", color:"#a0a3b1", cursor:"pointer", fontSize:"14px", fontWeight:600, transition:"all .2s" },
  levelActive: { background:"#667eea22", border:"1px solid #667eea", color:"#667eea" },
  dropzone:    { border:"2px dashed #2a2d3e", borderRadius:"10px", padding:"28px", textAlign:"center", cursor:"pointer", color:"#a0a3b1", fontSize:"14px", display:"flex", alignItems:"center", justifyContent:"center", gap:"10px", transition:"all .2s" },
  dropActive:  { borderColor:"#667eea", background:"#667eea11" },
  dropDone:    { borderColor:"#48bb78", background:"#48bb7811", color:"#48bb78" },
  dropIcon:    { fontSize:"24px" },
  error:       { background:"#ff4d4d22", border:"1px solid #ff4d4d44", borderRadius:"8px", padding:"12px", color:"#ff7070", marginBottom:"16px", fontSize:"14px" },
  submitBtn:   { width:"100%", padding:"16px", background:"linear-gradient(135deg,#667eea,#764ba2)", border:"none", borderRadius:"10px", color:"#fff", fontSize:"16px", fontWeight:700, cursor:"pointer", transition:"opacity .2s" },
  submitDisabled: { opacity:0.5, cursor:"not-allowed" },
};
