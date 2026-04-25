import React, { createContext, useContext, useCallback, useReducer, useEffect } from "react";
import { api } from "../api/client";

const InterviewContext = createContext();

export function useInterview() {
  const context = useContext(InterviewContext);
  if (!context) {
    throw new Error("useInterview must be used within an InterviewProvider");
  }
  return context;
}

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

export function InterviewProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, INIT);

  const setLoading    = v => dispatch({ type: "SET_LOADING",    v });
  const setEvaluating = v => dispatch({ type: "SET_EVALUATING", v });
  const setError      = v => dispatch({ type: "SET_ERROR",      v });
  const setStep       = v => dispatch({ type: "SET_STEP",       v });

  // ── Restore persisted session on mount ─────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    const restoreSession = async () => {
      const sid = sessionStorage.getItem(SESSION_KEY);
      if (!sid) return;
      try {
        const report = await api.getReport(sid);
        if (cancelled) return;
        if (report && report.final_score != null) {
          dispatch({ type: "SET_SESSION", v: sid });
          dispatch({ type: "SET_REPORT",  v: report });
        }
      } catch (e) {
        console.warn("Could not restore session:", e);
      }
    };
    restoreSession();
    return () => { cancelled = true; };
  }, []);

  const setup = useCallback(async (data) => {
    setLoading(true);
    try {
      const { session_id } = await api.createSession();
      sessionStorage.setItem(SESSION_KEY, session_id);
      dispatch({ type: "SET_SESSION", v: session_id });
      setLoading(false);
      dispatch({ type: "SAVE_SETUP", v: data });
      dispatch({ type: "SET_STEP", v: "preinterview" });
    } catch (e) {
      setError(e.message || "Setup failed.");
    }
  }, []);

  const startInterview = useCallback(async () => {
    if (!state.sessionId) return;
    setLoading(true);
    try {
      await api.startInterview(state.sessionId);
      const res = await api.nextQuestion(state.sessionId);
      dispatch({ type: "SET_QUESTION", v: res.question });
      dispatch({ type: "SET_STEP",     v: "interview" });
    } catch (e) {
      setError(e.message || "Could not start interview.");
    }
  }, [state.sessionId]);

  const restart = useCallback(() => {
    sessionStorage.removeItem(SESSION_KEY);
    dispatch({ type: "SET_SESSION", v: null });
    dispatch({ type: "SET_STEP", v: "dashboard" });
  }, []);

  const value = {
    ...state,
    setup,
    startInterview,
    restart,
    setStep,
    setError
  };

  return (
    <InterviewContext.Provider value={value}>
      {children}
    </InterviewContext.Provider>
  );
}
