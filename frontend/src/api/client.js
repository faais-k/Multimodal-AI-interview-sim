/**
 * API client.
 *
 * VITE_API_BASE — set in frontend/.env (local) or Vercel env vars (production).
 * Production example: VITE_API_BASE=https://your-space.hf.space/api
 * Default (local dev): http://127.0.0.1:8000/api
 *
 * All calls throw on non-ok responses so callers always catch errors.
 * scoreAudio derives extension from actual blob MIME type.
 *
 * Audio input:
 *   VITE_ENABLE_AUDIO_INPUT — manual override. If "false", audio is always off.
 *   If unset or "true", the frontend checks the backend /health endpoint at
 *   startup to determine if ASR is actually available.
 */
const API_BASE = (import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000/api").replace(/\/$/, "");

export const AUDIO_INPUT_HINT =
  import.meta.env.VITE_AUDIO_INPUT_HINT ||
  "Audio mode uses Whisper for speech-to-text. Speak clearly for best results.";

async function req(path, options = {}) {
  const token = localStorage.getItem("firebaseToken");
  const headers = { 
    "Content-Type": "application/json", 
    ...(token ? { "Authorization": `Bearer ${token}` } : {}),
    ...(options.headers || {}) 
  };
  
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `API error ${res.status}`);
  }
  return res.json();
}

async function reqMultipart(url, body) {
  const token = localStorage.getItem("firebaseToken");
  const headers = { 
    ...(token ? { "Authorization": `Bearer ${token}` } : {})
  };

  const res = await fetch(url, { 
    method: "POST", 
    body,
    headers
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `API error ${res.status}`);
  }
  return res.json();
}

/** Map a MIME type string to a file extension for audio blobs. */
function audioExtFromMime(mimeType) {
  if (!mimeType) return ".webm";
  if (mimeType.includes("mp4"))  return ".mp4";
  if (mimeType.includes("ogg"))  return ".ogg";
  if (mimeType.includes("wav"))  return ".wav";
  return ".webm";
}

export const api = {
  health:        ()         => req("/health"),
  createSession: ()         => req("/session/create", { method: "POST" }),

  uploadResume: (sid, file) => {
    const fd = new FormData();
    fd.append("session_id", sid);
    fd.append("file", file);
    return reqMultipart(`${API_BASE}/upload/resume`, fd);
  },

  parseResume:         (sid)     => req(`/parse/resume/${sid}`,         { method: "POST" }),
  
  // New: Parse and extract for resume autofill
  parseAndExtract: (sid, file) => {
    const fd = new FormData();
    fd.append("session_id", sid);
    fd.append("resume", file);
    return reqMultipart(`${API_BASE}/parse-and-extract`, fd);
  },
  
  // New: Dynamic interview generation (company research + LLM questions)
  generateDynamicInterview: (sid) => req(`/interview/generate-dynamic/${sid}`, { method: "POST" }),
  
  setJobDescription:   (payload) => req("/session/job_description",     { method: "POST", body: JSON.stringify(payload) }),
  setCandidateProfile: (payload) => req("/session/candidate_profile",   { method: "POST", body: JSON.stringify(payload) }),
  generatePlan:        (sid)     => req(`/interview/plan/${sid}`,       { method: "POST" }),
  startInterview:      (sid)     => req(`/session/start_interview?session_id=${encodeURIComponent(sid)}`, { method: "POST" }),
  nextQuestion:        (sid)     => req(`/session/next_question?session_id=${encodeURIComponent(sid)}`,  { method: "POST" }),
  scoreText:           (payload) => req("/score/text",                  { method: "POST", body: JSON.stringify(payload) }),

  scoreAudio: (sid, qid, blob) => {
    // Use the correct extension based on the actual MIME type (Safari uses audio/mp4)
    const ext      = audioExtFromMime(blob.type);
    const filename = `answer${ext}`;
    const fd       = new FormData();
    fd.append("file", blob, filename);
    return reqMultipart(
      `${API_BASE}/answer/audio?session_id=${encodeURIComponent(sid)}&question_id=${encodeURIComponent(qid)}`,
      fd
    );
  },

  sendPosture:  (payload) => req("/posture/report",    { method: "POST", body: JSON.stringify(payload) }),
  logViolation: (payload) => req("/session/violation", { method: "POST", body: JSON.stringify(payload) }),
  aggregate:    (sid)     => req(`/aggregate/${sid}`,  { method: "POST" }),
  analytics:    (sid)     => req(`/analytics/${sid}`,  { method: "POST" }),
  decision:     (sid)     => req(`/decision/${sid}`,   { method: "POST" }),
  getReport:    (sid)     => req(`/report/${sid}`),
  getUserHistory: ()      => req("/user/history"),
};
