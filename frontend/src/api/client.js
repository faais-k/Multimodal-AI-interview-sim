/**
 * API client.
 *
 * VITE_API_BASE — set in frontend/.env for Colab/ngrok.
 * Default: http://127.0.0.1:8000/api
 *
 * All calls throw on non-ok responses so callers always catch errors.
 * scoreAudio derives extension from actual blob MIME type.
 */
const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000/api";

async function req(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `API error ${res.status}`);
  }
  return res.json();
}

async function reqMultipart(url, body) {
  const res = await fetch(url, { method: "POST", body });
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
};
