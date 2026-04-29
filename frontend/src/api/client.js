/**
 * API client with comprehensive error handling, timeouts, and retry logic.
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

// Request configuration
const REQUEST_TIMEOUT = 30000; // 30 seconds default timeout
const MAX_RETRIES = 2;
const RETRY_DELAY = 1000; // 1 second between retries
const RETRYABLE_STATUSES = [408, 429, 500, 502, 503, 504]; // Statuses that warrant retry

/**
 * Create an AbortController with timeout
 */
function createTimeoutController(timeoutMs = REQUEST_TIMEOUT) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  return { controller, timeoutId };
}

/**
 * Determine if an error is retryable
 */
function isRetryableError(error, status) {
  // Network errors (no connection, DNS failure, etc.)
  if (error.name === 'TypeError' || error.name === 'AbortError') {
    return true;
  }
  // Server errors that might be transient
  if (status && RETRYABLE_STATUSES.includes(status)) {
    return true;
  }
  return false;
}

/**
 * Sleep helper for retry delays
 */
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function reqWithRetry(path, options = {}, attempt = 0) {
  const token = localStorage.getItem("firebaseToken");
  const headers = { 
    "Content-Type": "application/json", 
    ...(token ? { "Authorization": `Bearer ${token}` } : {}),
    ...(options.headers || {}) 
  };

  const { controller, timeoutId } = createTimeoutController(options.timeout);
  
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
      signal: controller.signal,
    });
    
    clearTimeout(timeoutId);
    
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      const error = new Error(data.detail || data.message || `API error ${res.status}`);
      error.status = res.status;
      error.data = data;
      
      // Check if we should retry
      if (attempt < MAX_RETRIES && isRetryableError(error, res.status)) {
        console.warn(`API request failed (attempt ${attempt + 1}), retrying...`, error.message);
        await sleep(RETRY_DELAY * (attempt + 1)); // Exponential backoff
        return reqWithRetry(path, options, attempt + 1);
      }
      
      throw error;
    }
    
    return res.json();
  } catch (error) {
    clearTimeout(timeoutId);
    
    // Handle abort/timeout specifically
    if (error.name === 'AbortError') {
      const timeoutError = new Error('Request timed out. Please check your connection and try again.');
      timeoutError.status = 408;
      timeoutError.isTimeout = true;
      
      if (attempt < MAX_RETRIES) {
        console.warn(`Request timeout (attempt ${attempt + 1}), retrying...`);
        await sleep(RETRY_DELAY * (attempt + 1));
        return reqWithRetry(path, options, attempt + 1);
      }
      
      throw timeoutError;
    }
    
    // Handle network errors with retry
    if (attempt < MAX_RETRIES && isRetryableError(error)) {
      console.warn(`Network error (attempt ${attempt + 1}), retrying...`, error.message);
      await sleep(RETRY_DELAY * (attempt + 1));
      return reqWithRetry(path, options, attempt + 1);
    }
    
    // Enhance network error message
    if (error.name === 'TypeError' && error.message.includes('fetch')) {
      error.message = 'Network error. Please check your internet connection and try again.';
      error.isNetworkError = true;
    }
    
    throw error;
  }
}

async function reqMultipartWithRetry(url, body, attempt = 0) {
  const token = localStorage.getItem("firebaseToken");
  const headers = { 
    ...(token ? { "Authorization": `Bearer ${token}` } : {})
  };

  const { controller, timeoutId } = createTimeoutController(60000); // Longer timeout for file uploads

  try {
    const res = await fetch(url, { 
      method: "POST", 
      body,
      headers,
      signal: controller.signal,
    });
    
    clearTimeout(timeoutId);
    
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      const error = new Error(data.detail || data.message || `API error ${res.status}`);
      error.status = res.status;
      error.data = data;
      
      // Check if we should retry (but be more conservative with file uploads)
      if (attempt < MAX_RETRIES && isRetryableError(error, res.status) && res.status !== 413) {
        console.warn(`Multipart request failed (attempt ${attempt + 1}), retrying...`, error.message);
        await sleep(RETRY_DELAY * (attempt + 1));
        return reqMultipartWithRetry(url, body, attempt + 1);
      }
      
      throw error;
    }
    
    return res.json();
  } catch (error) {
    clearTimeout(timeoutId);
    
    if (error.name === 'AbortError') {
      const timeoutError = new Error('Upload timed out. The file may be too large or your connection is slow.');
      timeoutError.status = 408;
      timeoutError.isTimeout = true;
      throw timeoutError;
    }
    
    if (attempt < MAX_RETRIES && isRetryableError(error)) {
      console.warn(`Multipart network error (attempt ${attempt + 1}), retrying...`, error.message);
      await sleep(RETRY_DELAY * (attempt + 1));
      return reqMultipartWithRetry(url, body, attempt + 1);
    }
    
    if (error.name === 'TypeError' && error.message.includes('fetch')) {
      error.message = 'Network error during upload. Please check your connection and try again.';
      error.isNetworkError = true;
    }
    
    throw error;
  }
}

// Maintain backward compatibility with original function names
async function req(path, options = {}) {
  return reqWithRetry(path, options);
}

async function reqMultipart(url, body) {
  return reqMultipartWithRetry(url, body);
}

/**
 * Check if an error is a network error (for UI handling)
 */
export function isNetworkError(error) {
  return error?.isNetworkError === true || error?.isTimeout === true || 
         error?.name === 'TypeError' || error?.name === 'AbortError';
}

/**
 * Check if an error is retryable (for UI retry buttons)
 */
export function isRetryable(error) {
  return isNetworkError(error) || RETRYABLE_STATUSES.includes(error?.status);
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
  getHealth:     ()         => req("/health"),
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
  
  // Session state recovery and skip support
  getSessionStatus: (sid)  => req(`/session/status/${encodeURIComponent(sid)}`),
  skipQuestion: (sid, qid) => req(`/session/skip/${encodeURIComponent(sid)}?question_id=${encodeURIComponent(qid || "")}`, { method: "POST" }),
};
