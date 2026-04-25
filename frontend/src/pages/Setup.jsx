import { useRef, useState, useCallback } from "react";
import { api } from "../api/client";
import "./Setup.css";

const Logo = () => (
  <svg width="28" height="28" viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
    <rect width="36" height="36" rx="10" fill="url(#sb-lg)"/>
    <path d="M8 26 L18 10 L28 26" stroke="white" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" fill="none" opacity="0.4"/>
    <path d="M8 26 L14 18 L18 22 L22 14 L28 26" stroke="white" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" fill="none"/>
    <defs><linearGradient id="sb-lg" x1="0" y1="0" x2="36" y2="36"><stop offset="0%" stopColor="#14B8A6"/><stop offset="100%" stopColor="#0D9488"/></linearGradient></defs>
  </svg>
);

const LEVELS = ["fresher", "intermediate", "experienced"];
const LEVEL_DESC = {
  fresher:      "Fundamentals, projects & learning approach",
  intermediate: "Previous work, deeper concepts & trade-offs",
  experienced:  "Architecture, leadership & production decisions",
};

export default function Setup({ onSubmit, loading, error }) {
  const [form, setForm] = useState({
    name: "",
    jobRole: "",
    expertiseLevel: "fresher",
    jobDescription: "",
    company: "",
    experience: "",
    education: "",
  });
  const [file, setFile] = useState(null);
  const [drag, setDrag] = useState(false);
  const [parsing, setParsing] = useState(false);
  const [parsedData, setParsedData] = useState(null);
  const [parseError, setParseError] = useState(null);
  const fileRef = useRef();

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  // Create session and parse resume
  const handleFileSelect = useCallback(async (selectedFile) => {
    if (!selectedFile) return;
    
    setFile(selectedFile);
    setParsing(true);
    setParseError(null);
    setParsedData(null);

    try {
      // Create session first
      const sessionRes = await api.createSession();
      const sessionId = sessionRes.session_id;

      // Parse and extract
      const parseRes = await api.parseAndExtract(sessionId, selectedFile);
      
      if (parseRes.status === "ok") {
        setParsedData(parseRes);
        
        // Autofill form
        const extracted = parseRes.extracted;
        setForm(prev => ({
          ...prev,
          name: extracted.name || prev.name,
          expertiseLevel: extracted.expertise_level || prev.expertiseLevel,
          education: extracted.education_summary || prev.education,
        }));
      }
    } catch (err) {
      setParseError(err.message || "Failed to parse resume");
    } finally {
      setParsing(false);
    }
  }, []);

  const handleDrop = e => {
    e.preventDefault();
    setDrag(false);
    const f = e.dataTransfer.files[0];
    const ok = f && (
      ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword"].includes(f.type)
      || f.name.match(/\.(pdf|docx|doc)$/i)
    );
    if (ok) handleFileSelect(f);
  };

  const handleInputChange = e => {
    const f = e.target.files?.[0];
    if (f) handleFileSelect(f);
  };

  const canSubmit = form.name.trim() && form.jobRole.trim() && file && !parsing;

  return (
    <div className="setup-shell">
      <header className="setup-bar">
        <a href="#" className="setup-bar__brand" onClick={e => { e.preventDefault(); window.location.reload(); }}>
          <Logo /><span>Ascent</span>
        </a>
        <span className="setup-bar__step">Setup · Step 1 of 3</span>
      </header>

      <div className="setup-body">
        <aside className="setup-aside">
          <div className="setup-aside__title">Interview Setup</div>
          <p className="setup-aside__sub">Upload your resume to autofill details, then customize for your target role.</p>

          <div className="setup-aside__tip">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10" /><path d="M12 16v-4m0-4h.01" /></svg>
            Resume autofill extracts: name, skills, projects, education, and suggests a difficulty level.
          </div>
        </aside>

        <main className="setup-main">
          <form
            onSubmit={e => { 
              e.preventDefault(); 
              if (canSubmit && !loading) {
                onSubmit({ ...form, resumeFile: file, parsedData });
              }
            }}
            noValidate
          >
            <div className="setup-section animate-in">
              <div className="setup-section__title">
                <span className="section-number">1</span>
                Upload Resume
              </div>
              <p className="setup-section__note">PDF or DOCX. We'll extract your details automatically.</p>

              <div className="input-group">
                <div
                  className={`dropzone${drag ? " dropzone--drag" : ""}${file ? " dropzone--done" : ""}${parsing ? " dropzone--parsing" : ""}`}
                  onDragOver={e => { e.preventDefault(); setDrag(true); }}
                  onDragLeave={() => setDrag(false)}
                  onDrop={handleDrop}
                  onClick={() => fileRef.current.click()}
                  role="button"
                  tabIndex={0}
                  onKeyDown={e => { if (e.key === "Enter" || e.key === " ") fileRef.current.click(); }}
                  aria-label="Upload resume"
                >
                  <input
                    ref={fileRef}
                    type="file"
                    accept=".pdf,.docx,.doc"
                    style={{ display: "none" }}
                    onChange={handleInputChange}
                  />
                  {parsing ? (
                    <>
                      <div className="dropzone__icon dropzone__icon--spin">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10" strokeDasharray="60" strokeDashoffset="10"/></svg>
                      </div>
                      <div className="dropzone__name">Parsing resume…</div>
                      <div className="dropzone__sub">Extracting skills, projects, and experience</div>
                    </>
                  ) : file ? (
                    <>
                      <div className="dropzone__icon dropzone__icon--done">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
                      </div>
                      <div className="dropzone__name">{file.name}</div>
                      <div className="dropzone__sub">{(file.size / 1024).toFixed(0)} KB · Click to replace</div>
                      {parsedData?.extracted?.skills?.length > 0 && (
                        <div className="dropzone__meta">
                          <span className="badge">{parsedData.extracted.skills.length} skills found</span>
                          <span className="badge">{parsedData.extracted.projects?.length || 0} projects</span>
                        </div>
                      )}
                    </>
                  ) : (
                    <>
                      <div className="dropzone__icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></svg>
                      </div>
                      <div className="dropzone__label">Drop your resume here, or <span>browse</span></div>
                      <div className="dropzone__sub">PDF, DOC, DOCX · Max 10 MB</div>
                    </>
                  )}
                </div>
                {parseError && (
                  <div className="input-hint input-hint--error">{parseError}</div>
                )}
              </div>

              <div className="setup-section__title">
                <span className="section-number">2</span>
                Your Details
              </div>
              <p className="setup-section__note">Review and edit the autofilled information.</p>

              <div className="setup-row">
                <div className="input-group">
                  <label className="input-label">Full Name *</label>
                  <input
                    value={form.name}
                    onChange={e => set("name", e.target.value)}
                    placeholder="e.g. John Doe"
                    required
                  />
                </div>
                <div className="input-group">
                  <label className="input-label">Target Role *</label>
                  <input
                    value={form.jobRole}
                    onChange={e => set("jobRole", e.target.value)}
                    placeholder="e.g. Full Stack Developer"
                    required
                  />
                </div>
              </div>

              <div className="setup-row">
                <div className="input-group">
                  <label className="input-label">Target Company</label>
                  <input
                    value={form.company}
                    onChange={e => set("company", e.target.value)}
                    placeholder="e.g. Google, Microsoft, startup…"
                  />
                  <div className="input-hint">We'll research their interview style and common questions</div>
                </div>
                <div className="input-group">
                  <label className="input-label">Education</label>
                  <input
                    value={form.education}
                    onChange={e => set("education", e.target.value)}
                    placeholder="e.g. B.Tech Computer Science, 2023"
                  />
                </div>
              </div>

              <div className="input-group">
                <label className="input-label">Experience Level *</label>
                <div className="level-grid">
                  {LEVELS.map(l => (
                    <button
                      key={l}
                      type="button"
                      className={`level-btn${form.expertiseLevel === l ? " level-btn--active" : ""}`}
                      onClick={() => set("expertiseLevel", l)}
                    >
                      <span className="level-btn__name">{l.charAt(0).toUpperCase() + l.slice(1)}</span>
                      <span className="level-btn__desc">{LEVEL_DESC[l]}</span>
                    </button>
                  ))}
                </div>
                <div className="input-hint">
                  {form.expertiseLevel === "fresher" && "Questions focus on fundamentals, projects, and learning approach — not production scaling."}
                  {form.expertiseLevel === "intermediate" && "Questions focus on real-world problems, debugging, and optimization."}
                  {form.expertiseLevel === "experienced" && "Questions focus on system design, trade-offs, scalability, and architecture decisions."}
                </div>
              </div>

              <div className="setup-section__title">
                <span className="section-number">3</span>
                Job Context
              </div>
              <p className="setup-section__note">Paste the job description to get highly relevant questions.</p>

              <div className="input-group">
                <label className="input-label">Job Description</label>
                <textarea
                  value={form.jobDescription}
                  onChange={e => set("jobDescription", e.target.value)}
                  placeholder="Paste the job posting here. We'll match questions to the required skills and responsibilities."
                  rows={6}
                  style={{ resize: "vertical" }}
                />
              </div>

              <div className="input-group">
                <label className="input-label">Experience Summary</label>
                <textarea
                  value={form.experience}
                  onChange={e => set("experience", e.target.value)}
                  placeholder="Brief summary of your work experience (optional)…"
                  rows={3}
                  style={{ resize: "vertical" }}
                />
              </div>

              {error && (
                <div className="setup-error">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10" /><path d="M12 8v4m0 4h.01" /></svg>
                  {error}
                </div>
              )}

              <div className="setup-actions">
                <button
                  type="submit"
                  className="btn-primary btn-primary--large"
                  disabled={!canSubmit || loading}
                >
                  {loading ? (
                    <><span className="spinner" />&nbsp;Creating Session…</>
                  ) : (
                    <>Continue to Setup<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M12 5l7 7-7 7" /></svg></>
                  )}
                </button>
              </div>
            </div>
          </form>
        </main>
      </div>
    </div>
  );
}
