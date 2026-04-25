/**
 * useInterview — full session lifecycle.
 *
 * sessionId is persisted to sessionStorage so a page refresh does not lose
 * the session. On mount, the hook attempts to restore from sessionStorage.
 *
 * P3-B: evaluating state — true while the LLM is scoring an answer.
 *        Separate from loading so the UI can show a specific "Evaluating…" indicator.
 */
import { useCallback, useReducer, useEffect } from "react";
import { api } from "../api/client";

const SESSION_KEY = "ai_interview_session_id";

const INIT = {
  sessionId:      null,
  step:           "landing",  // landing | setup | preinterview | interview | processing | results
  question:       null,
  questionNumber: 0,
  loading:        false,
  evaluating:     false,
  error:          null,
  report:         null,
  setupData:      null,
};

function reducer(s, a) {
  switch (a.type) {
    case "SET_LOADING":        return { ...s, loading: a.v };
    case "SET_EVALUATING":     return { ...s, evaluating: a.v };
    case "SET_ERROR":          return { ...s, error: a.v, loading: false, evaluating: false };
    case "CLEAR_ERROR":        return { ...s, error: null };
    case "SET_SESSION":        return { ...s, sessionId: a.v };
    case "SET_STEP":           return { ...s, step: a.v };
    case "SET_QUESTION":       return { ...s, question: a.v, questionNumber: s.questionNumber + 1, loading: false, evaluating: false };
    case "CLEAR_QUESTION":      return { ...s, question: null, loading: false, evaluating: false };
    case "RESET_QUESTION_NUM": return { ...s, questionNumber: 0 };
    case "SET_REPORT":         return { ...s, report: a.v, loading: false, evaluating: false, step: "results" };
    case "SAVE_SETUP":         return { ...s, setupData: a.v };
    default:                   return s;
  }
}

export function useInterview() {
  const [state, dispatch] = useReducer(reducer, INIT);

  const setLoading    = v => dispatch({ type: "SET_LOADING",    v });
  const setEvaluating = v => dispatch({ type: "SET_EVALUATING", v });
  const setError      = v => dispatch({ type: "SET_ERROR",      v });
  const setStep       = v => dispatch({ type: "SET_STEP",       v });

  // ── Restore persisted session on mount ─────────────────────────────────────
  useEffect(() => {
    let cancelled = false;

    const restoreSession = async () => {
      let sid = null;
      try {
        sid = sessionStorage.getItem(SESSION_KEY);
      } catch (_) {
        return;
      }
      if (!sid) return;

      try {
        const report = await api.getReport(sid);
        if (cancelled) return;

        if (!report || report.final_score == null) {
          throw new Error("final_report.json not found");
        }
        dispatch({ type: "SET_SESSION", v: sid });
        dispatch({ type: "SET_REPORT",  v: report });
        return;
      } catch (e) {
        const msg = String(e?.message || "").toLowerCase();

        if (msg.includes("session not found")) {
          try { sessionStorage.removeItem(SESSION_KEY); } catch (_) {}
          return;
        }

        if (msg.includes("final_report.json not found")) {
          try {
            const res = await api.startInterview(sid);
            if (cancelled) return;

            dispatch({ type: "SET_SESSION", v: sid });
            const backendMsg       = String(res?.message || "").toLowerCase();
            const isAlreadyActive  = backendMsg.includes("already in progress");

            dispatch({
              type: "SET_STEP",
              v: isAlreadyActive ? "interview" : "preinterview",
            });

            if (isAlreadyActive) {
              try {
                const q = await _fetchQuestionRaw(sid);
                if (cancelled) return;
                if (q) dispatch({ type: "SET_QUESTION", v: q });
              } catch (qErr) {
                if (cancelled) return;
                dispatch({ type: "SET_STEP", v: "setup" });
                setError(qErr?.message || "Could not restore the current question. Please start again.");
              }
            }
            return;
          } catch (inner) {
            const innerMsg = String(inner?.message || "").toLowerCase();
            if (innerMsg.includes("session not found")) {
              try { sessionStorage.removeItem(SESSION_KEY); } catch (_) {}
            }
          }
        }
      }
    };

    restoreSession();
    return () => { cancelled = true; };
  }, []);

  // ── Setup ──────────────────────────────────────────────────────────────────
  const setup = useCallback(async (data) => {
    setLoading(true);
    try {
      const { session_id } = await api.createSession();
      if (!session_id) throw new Error("Server did not return a session_id");

      try { sessionStorage.setItem(SESSION_KEY, session_id); } catch (_) {}
      dispatch({ type: "SET_SESSION", v: session_id });

      // Use parseAndExtract to autofill data and parse resume
      if (data.resumeFile) {
        const parseResult = await api.parseAndExtract(session_id, data.resumeFile);
        if (parseResult.status === "ok") {
          // Merge autofill with user edits
          data = {
            ...data,
            name: data.name || parseResult.extracted.name,
            education: data.education || parseResult.extracted.education_summary,
            expertiseLevel: data.expertiseLevel || parseResult.extracted.expertise_level,
            parsedData: parseResult.extracted,
          };
        }
      }

      if (data.jobRole || data.jobDescription || data.company) {
        await api.setJobDescription({
          session_id:      session_id,
          job_role:        data.jobRole        || "",
          job_description: data.jobDescription || "",
          company:         data.company        || "",
        });
      }

      // Note: Dynamic interview generation happens in PreInterview page
      // so user can set up camera/mic while questions are being generated

      setLoading(false);
      dispatch({ type: "SAVE_SETUP", v: data });
      dispatch({ type: "SET_STEP", v: "preinterview" });
    } catch (e) {
      setError(e.message || "Setup failed. Please try again.");
    }
  }, []);

  // ── Start interview ────────────────────────────────────────────────────────
  const startInterview = useCallback(async () => {
    const sid = state.sessionId;
    if (!sid) {
      setError("Session ID is missing. Please refresh the page and start again.");
      return;
    }
    dispatch({ type: "RESET_QUESTION_NUM" });
    setLoading(true);
    try {
      await api.startInterview(sid);
      const firstQ = await _fetchQuestionRaw(sid);
      if (!firstQ) return;
      dispatch({ type: "SET_QUESTION", v: firstQ });
      dispatch({ type: "SET_STEP",     v: "interview" });
    } catch (e) {
      setError(e.message || "Could not start interview.");
    }
  }, [state.sessionId]);

  // ── Internal: fetch one question ───────────────────────────────────────────
  async function _fetchQuestionRaw(sid) {
    if (!sid) throw new Error("No session ID");
    const res = await api.nextQuestion(sid);
    const q   = res.question;
    if (q?.status === "completed" || q?.status === "awaiting_wrapup_answer") {
      dispatch({ type: "CLEAR_QUESTION" }); // clear before finalization prevents stale question display
      await _finalize(sid);
      return null;
    }
    return q;
  }

  // ── Internal: finalize interview ───────────────────────────────────────────
  async function _finalize(sid) {
    dispatch({ type: "SET_STEP",     v: "processing" });
    dispatch({ type: "CLEAR_QUESTION" }); // clear stale question so it cannot re-appear
    let finalizeError = null;
    try {
      await api.aggregate(sid);
      await api.analytics(sid);
      try {
        await api.decision(sid);
      } catch (e) {
        finalizeError = e;
      }
      const report = await api.getReport(sid);
      if (finalizeError) {
        report.reviewer_summary = {
          ...(report.reviewer_summary || {}),
          overall: (report.reviewer_summary?.overall || "Interview report generated.")
            + " Final decision generation had a transient issue, but the scorecard is available.",
        };
      }
      dispatch({ type: "SET_REPORT", v: report });
    } catch (e) {
      // Stay on "processing" — never go back to "interview" (prevents wrapup re-display)
      setError(e.message || "Failed to generate report.");
    }
  }

  // ── Retry finalization (called from Processing page retry button) ─────────
  const retryFinalize = useCallback(async () => {
    const sid = state.sessionId;
    if (!sid) return;
    setError(null);
    await _finalize(sid);
  }, [state.sessionId]);

  // ── Fetch next question ────────────────────────────────────────────────────
  const fetchNext = useCallback(async (sid) => {
    const useSid = sid || state.sessionId;
    if (!useSid) { setError("Session ID is missing."); return; }
    setLoading(true);
    try {
      const q = await _fetchQuestionRaw(useSid);
      if (q) dispatch({ type: "SET_QUESTION", v: q });
    } catch (e) {
      setError(e.message || "Failed to fetch next question.");
    }
  }, [state.sessionId]);

  // ── Submit text answer — P3-B: set evaluating=true during LLM scoring ──────
  const submitText = useCallback(async (answerText) => {
    if (!state.question || !state.sessionId) return;
    setLoading(true);
    setEvaluating(true);   // P3-B: show LLM evaluation indicator
    try {
      await api.scoreText({
        session_id:  state.sessionId,
        question_id: state.question.id,
        answer_text: answerText,
      });
      setEvaluating(false);   // P3-B: scoring done, clear before fetching next
      await fetchNext(state.sessionId);
    } catch (e) {
      setEvaluating(false);
      setError(e.message || "Failed to submit answer.");
    }
  }, [state.question, state.sessionId, fetchNext]);

  // ── Submit audio answer — P3-B: set evaluating=true during ASR + scoring ───
  const submitAudio = useCallback(async (audioBlob) => {
    if (!state.question || !audioBlob || !state.sessionId) return;
    setLoading(true);
    setEvaluating(true);   // P3-B: show LLM evaluation indicator
    try {
      await api.scoreAudio(state.sessionId, state.question.id, audioBlob);
      setEvaluating(false);
      await fetchNext(state.sessionId);
    } catch (e) {
      setEvaluating(false);
      setError(e.message || "Failed to submit audio answer.");
    }
  }, [state.question, state.sessionId, fetchNext]);

  // ── Restart interview ──────────────────────────────────────────────────────
  const restart = useCallback(() => {
    try { sessionStorage.removeItem(SESSION_KEY); } catch (_) {}
    dispatch({ type: "SET_SESSION", v: null });
    dispatch({ type: "SET_REPORT", v: null });
    dispatch({ type: "CLEAR_QUESTION" });
    dispatch({ type: "SET_STEP", v: "dashboard" }); // Default to dashboard on restart if logged in
  }, []);

  const viewReport = useCallback(async (sid) => {
    setLoading(true);
    try {
      const report = await api.getReport(sid);
      dispatch({ type: "SET_SESSION", v: sid });
      dispatch({ type: "SET_REPORT", v: report });
      dispatch({ type: "SET_STEP", v: "results" });
    } catch (e) {
      setError("Failed to load report history.");
    } finally {
      setLoading(false);
    }
  }, []);

  return {
    ...state,
    setup, startInterview, submitText, submitAudio, fetchNext, retryFinalize, setStep, restart, viewReport
  };
}
