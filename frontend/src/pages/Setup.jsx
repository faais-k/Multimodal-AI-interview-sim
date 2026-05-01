import { useRef, useState, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Upload, Check, AlertCircle, ArrowRight, FileText, ChevronLeft } from "lucide-react";
import { useInterview } from "../contexts/InterviewContext";
import { api } from "../api/client";
import { Button } from "@/components/ui/button";
import logo from "../assets/logo.jpg";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const LEVELS = ["fresher", "intermediate", "experienced"];
const LEVEL_DESC = {
  fresher: "Fundamentals, projects & learning approach",
  intermediate: "Previous work, deeper concepts & trade-offs",
  experienced: "Architecture, leadership & production decisions",
};

// Resume parsing animation component
function ResumeParsingAnimation({ fileName, extracted, onComplete }) {
  const fields = [
    { key: "name", label: "Name detected", value: extracted?.name || "Processing..." },
    { key: "level", label: "Experience level", value: extracted?.expertise_level || "Analyzing..." },
    { key: "skills", label: "Technical skills", value: extracted?.skills?.length ? `${extracted.skills.length} found` : "Scanning..." },
    { key: "projects", label: "Projects analyzed", value: extracted?.projects?.length ? `${extracted.projects.length} documented` : "Extracting..." },
  ];

  return (
    <Card className="p-5 border-ascent-blue/30 bg-ascent-blue-subtle/30">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-8 h-8 bg-ascent-blue rounded-sm flex items-center justify-center">
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
              <circle cx="12" cy="12" r="10" strokeDasharray="60" strokeDashoffset="20" />
            </svg>
          </motion.div>
        </div>
        <div>
          <p className="font-medium text-text-primary">Analyzing resume...</p>
          <p className="text-sm text-text-secondary">Extracting skills, projects, experience</p>
        </div>
      </div>

      <div className="space-y-2">
        {fields.map((field, idx) => (
          <motion.div
            key={field.key}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: idx * 0.2, duration: 0.4 }}
            className="flex items-center justify-between text-sm"
          >
            <span className="text-text-secondary">{field.label}</span>
            <motion.span
              className={cn(
                "font-medium",
                field.value && !field.value.includes("...") ? "text-ascent-blue" : "text-text-muted"
              )}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: idx * 0.2 + 0.3 }}
            >
              {field.value}
            </motion.span>
          </motion.div>
        ))}
      </div>
    </Card>
  );
}

export default function Setup({ onSubmit, loading: outerLoading, error: outerError, onBack }) {
  const iv = useInterview();
  const [form, setForm] = useState({
    name: "",
    jobRole: "",
    expertiseLevel: "intermediate",
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
  const [showDetails, setShowDetails] = useState(null); // 'skills' | 'projects' | null
  const fileRef = useRef();

  // Ensure session exists on mount (for direct navigation or refresh)
  useEffect(() => {
    const ensureSession = async () => {
      if (!iv.sessionId) {
        try {
          const sessionRes = await api.createSession();
          iv.setSession(sessionRes.session_id);
        } catch (err) {
          console.error("Failed to create session:", err);
          setParseError("Failed to initialize session. Please refresh and try again.");
        }
      }
    };
    ensureSession();
  }, []);

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const handleFileSelect = useCallback(async (selectedFile) => {
    if (!selectedFile) return;

    setFile(selectedFile);
    setParsing(true);
    setParseError(null);
    setParsedData(null);

    try {
      const sessionRes = await api.createSession();
      const sessionId = sessionRes.session_id;
      iv.setSession(sessionId);

      const parseRes = await api.parseAndExtract(sessionId, selectedFile);

      if (parseRes.status === "ok") {
        setParsedData(parseRes);
        const extracted = parseRes.extracted;

        // Attempt to extract latest role if jobRole is empty
        let defaultRole = form.jobRole;
        if (extracted.current_role) defaultRole = extracted.current_role;
        else if (extracted.target_role) defaultRole = extracted.target_role;

        setForm(prev => ({
          ...prev,
          name: extracted.name || prev.name,
          jobRole: defaultRole || prev.jobRole,
          expertiseLevel: extracted.expertise_level || "fresher",
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
    <div className="min-h-screen bg-surface-base">
      {/* Minimal Header */}
      <header className="border-b border-border">
        <div className="max-w-2xl mx-auto px-4 sm:px-6 h-14 flex items-center">
          <div className="flex items-center gap-2">
            {onBack && (
              <button
                onClick={onBack}
                className="mr-2 p-1.5 hover:bg-surface-overlay rounded-sm transition-colors"
              >
                <ChevronLeft size={20} />
              </button>
            )}
            <img src={logo} alt="Ascent Logo" className="w-8 h-8 rounded-sm object-cover" />
            <span className="font-semibold">Ascent</span>
          </div>
          <div className="ml-auto flex items-center gap-2 text-sm text-text-muted">
            <span className="w-2 h-2 bg-ascent-blue rounded-full" />
            Step 1 of 3
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-2xl mx-auto px-4 sm:px-6 py-8 sm:py-12">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        >
          {/* Header */}
          <div className="mb-10">
            <h1 className="text-2xl font-semibold mb-2">Configure Session</h1>
            <p className="text-text-secondary">Upload your resume. Our AI will parse your technical profile and tailor the interview.</p>
          </div>

          {/* Upload Zone */}
          <AnimatePresence mode="wait">
            {!file && !parsing && (
              <motion.div
                key="upload"
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.98 }}
                transition={{ duration: 0.3 }}
              >
                <div
                  className={cn(
                    "border-2 border-dashed border-border rounded-md p-8 sm:p-12 text-center transition-all duration-250 cursor-pointer bg-surface-base",
                    drag && "border-ascent-blue bg-ascent-blue-subtle/20"
                  )}
                  onDragOver={e => { e.preventDefault(); setDrag(true); }}
                  onDragLeave={() => setDrag(false)}
                  onDrop={handleDrop}
                  onClick={() => fileRef.current.click()}
                >
                  <input
                    ref={fileRef}
                    type="file"
                    accept=".pdf,.docx,.doc"
                    className="hidden"
                    onChange={handleInputChange}
                  />
                  <div className="w-16 h-16 mx-auto mb-4 bg-surface-overlay rounded-md flex items-center justify-center">
                    <Upload size={28} className="text-text-secondary" />
                  </div>
                  <p className="font-medium text-text-primary mb-1">Drop your resume here</p>
                  <p className="text-sm text-text-secondary">PDF or DOCX • Max 10MB</p>
                </div>
              </motion.div>
            )}

            {parsing && (
              <motion.div
                key="parsing"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
              >
                <ResumeParsingAnimation
                  fileName={file?.name}
                  extracted={parsedData?.extracted}
                />
              </motion.div>
            )}

            {file && !parsing && (
              <motion.div
                key="uploaded"
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                className="mb-8"
              >
                <div className="border border-ascent-blue bg-ascent-blue-subtle/20 rounded-md p-5">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 bg-ascent-blue rounded-md flex items-center justify-center">
                      <Check size={24} className="text-white" />
                    </div>
                    <div className="flex-1">
                      <p className="font-medium text-ascent-blue">Resume uploaded</p>
                      <p className="text-sm text-text-secondary">{file.name} • {(file.size / 1024).toFixed(0)} KB</p>
                    </div>
                    <button
                      onClick={() => { setFile(null); setParsedData(null); }}
                      className="text-sm text-text-secondary hover:text-text-primary transition-colors"
                    >
                      Remove
                    </button>
                  </div>
                  {parsedData?.extracted?.skills?.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-ascent-blue/20">
                      <div className="flex gap-2">
                        <Badge
                          variant={showDetails === 'skills' ? "default" : "secondary"}
                          className="cursor-pointer transition-colors"
                          onClick={() => setShowDetails(prev => prev === 'skills' ? null : 'skills')}
                        >
                          {parsedData.extracted.skills.length} skills found
                        </Badge>
                        <Badge
                          variant={showDetails === 'projects' ? "default" : "secondary"}
                          className="cursor-pointer transition-colors"
                          onClick={() => setShowDetails(prev => prev === 'projects' ? null : 'projects')}
                        >
                          {parsedData.extracted.projects?.length || 0} projects
                        </Badge>
                      </div>

                      <AnimatePresence>
                        {showDetails === 'skills' && (
                          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                            <div className="mt-3 flex flex-wrap gap-1.5 p-3 bg-white/50 rounded-sm text-xs">
                              {parsedData.extracted.skills.map((s, i) => (
                                <span key={i} className="px-2 py-1 bg-surface-base border border-border rounded-sm">{s}</span>
                              ))}
                            </div>
                          </motion.div>
                        )}
                        {showDetails === 'projects' && (
                          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                            <div className="mt-3 space-y-2 p-3 bg-white/50 rounded-sm text-xs max-h-48 overflow-y-auto">
                              {Array.isArray(parsedData.extracted.projects) ? (
                                parsedData.extracted.projects.map((p, i) => (
                                  <div key={i} className="p-2 bg-surface-base border border-border rounded-sm">
                                    {typeof p === 'string' ? p : (p.title || p.description || JSON.stringify(p))}
                                  </div>
                                ))
                              ) : (
                                <div className="p-2 bg-surface-base border border-border rounded-sm text-text-muted italic">
                                  No specific projects identified
                                </div>
                              )}
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {parseError && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="mb-6 p-4 bg-semantic-error-bg border border-semantic-error/20 rounded-md flex items-center gap-3"
            >
              <AlertCircle size={18} className="text-semantic-error" />
              <p className="text-sm text-semantic-error">{parseError}</p>
            </motion.div>
          )}

          {/* Form */}
          <motion.form
            initial={{ opacity: 0 }}
            animate={{ opacity: file && !parsing ? 1 : 0.5 }}
            transition={{ delay: 0.2 }}
            className={cn("space-y-6", (!file || parsing) && "pointer-events-none")}
            onSubmit={e => {
              e.preventDefault();
              if (canSubmit && !outerLoading) {
                onSubmit({ ...form, resumeFile: file, parsedData });
              }
            }}
          >
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1.5">Full Name *</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={e => set("name", e.target.value)}
                  placeholder="Your name"
                  className="w-full px-4 py-2.5 bg-white border border-border rounded-sm text-sm focus:outline-none focus:border-ascent-blue focus:ring-2 focus:ring-ascent-blue/10 transition-all"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1.5">Target Role *</label>
                <input
                  type="text"
                  value={form.jobRole}
                  onChange={e => set("jobRole", e.target.value)}
                  placeholder="e.g. Senior Full Stack Engineer"
                  className="w-full px-4 py-2.5 bg-white border border-border rounded-sm text-sm focus:outline-none focus:border-ascent-blue focus:ring-2 focus:ring-ascent-blue/10 transition-all"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1.5">
                  Target Company <span className="text-text-muted font-normal">(optional)</span>
                </label>
                <input
                  type="text"
                  value={form.company}
                  onChange={e => set("company", e.target.value)}
                  placeholder="e.g. Stripe, Google"
                  className="w-full px-4 py-2.5 bg-white border border-border rounded-sm text-sm focus:outline-none focus:border-ascent-blue focus:ring-2 focus:ring-ascent-blue/10 transition-all"
                />
                <p className="text-xs text-text-muted mt-1.5">We'll research their interview style</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1.5">Experience Level</label>
                <select
                  value={form.expertiseLevel}
                  onChange={e => set("expertiseLevel", e.target.value)}
                  className="w-full px-4 py-2.5 bg-white border border-border rounded-sm text-sm focus:outline-none focus:border-ascent-blue focus:ring-2 focus:ring-ascent-blue/10 transition-all"
                >
                  <option value="fresher">Fresher (0-2 years)</option>
                  <option value="intermediate">Intermediate (2-5 years)</option>
                  <option value="experienced">Experienced (5+ years)</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1.5">
                Job Description <span className="text-text-muted font-normal">(paste for precision)</span>
              </label>
              <textarea
                value={form.jobDescription}
                onChange={e => set("jobDescription", e.target.value)}
                placeholder="Paste the job posting here. We'll match questions to required skills and responsibilities..."
                rows={4}
                className="w-full px-4 py-3 bg-white border border-border rounded-sm text-sm resize-none focus:outline-none focus:border-ascent-blue focus:ring-2 focus:ring-ascent-blue/10 transition-all"
              />
            </div>

            <div className="pt-4">
              <Button
                type="submit"
                className="w-full flex items-center justify-center gap-2"
                disabled={!canSubmit || outerLoading}
              >
                {outerLoading ? (
                  <>
                    <motion.div
                      animate={{ rotate: 360 }}
                      transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="12" cy="12" r="10" strokeDasharray="60" strokeDashoffset="20" />
                      </svg>
                    </motion.div>
                    Creating Session...
                  </>
                ) : (
                  <>
                    Continue to Calibration
                    <ArrowRight size={16} />
                  </>
                )}
              </Button>
            </div>
          </motion.form>
        </motion.div>
      </main>
    </div>
  );
}
