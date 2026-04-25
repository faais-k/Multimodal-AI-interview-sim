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
  step:           "landing", // landing | dashboard | setup | pre-interview | interview | processing | results
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
    case "SET_REPORT":         return { ...s, report: a.v, loading: false, evaluating: false };
    case "SAVE_SETUP":         return { ...s, setupData: a.v };
    case "RESET":              return { ...INIT, step: "dashboard" };
    default:                   return s;
  }
}

export function InterviewProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, INIT);

  const setLoading    = v => dispatch({ type: "SET_LOADING",    v });
  const setEvaluating = v => dispatch({ type: "SET_EVALUATING", v });
  const setError      = v => dispatch({ type: "SET_ERROR",      v });
  const setStep       = v => dispatch({ type: "SET_STEP",       v });
  const setReport     = v => dispatch({ type: "SET_REPORT",     v });
  const setSession    = v => dispatch({ type: "SET_SESSION",    v });

  // Load session from storage on mount
  useEffect(() => {
    const sid = sessionStorage.getItem(SESSION_KEY);
    if (sid) setSession(sid);
  }, []);

  const startInterview = useCallback(async () => {
    if (!state.sessionId) return;
    setLoading(true);
    try {
      await api.startInterview(state.sessionId);
      const res = await api.nextQuestion(state.sessionId);
      dispatch({ type: "SET_QUESTION", v: res.question });
      setStep("interview");
    } catch (e) {
      setError(e.message || "Could not start interview.");
    }
  }, [state.sessionId]);

  const submitText = useCallback(async (text) => {
    if (!state.sessionId || !state.question) return;
    setEvaluating(true);
    try {
      const res = await api.scoreText({
        session_id: state.sessionId,
        question_id: state.question.id,
        answer: text
      });
      
      if (res.is_final) {
        setStep("processing");
      } else {
        const next = await api.nextQuestion(state.sessionId);
        dispatch({ type: "SET_QUESTION", v: next.question });
      }
    } catch (e) {
      setError(e.message || "Evaluation failed.");
    }
  }, [state.sessionId, state.question]);

  const submitAudio = useCallback(async (blob) => {
    if (!state.sessionId || !state.question) return;
    setEvaluating(true);
    try {
      const res = await api.scoreAudio(state.sessionId, state.question.id, blob);
      
      if (res.is_final) {
        setStep("processing");
      } else {
        const next = await api.nextQuestion(state.sessionId);
        dispatch({ type: "SET_QUESTION", v: next.question });
      }
    } catch (e) {
      setError(e.message || "Audio evaluation failed.");
    }
  }, [state.sessionId, state.question]);

  const restart = useCallback(() => {
    sessionStorage.removeItem(SESSION_KEY);
    dispatch({ type: "RESET" });
  }, []);

  const value = {
    ...state,
    setStep,
    setReport,
    setSession,
    setError,
    startInterview,
    submitText,
    submitAudio,
    restart,
    saveSetup: (data) => dispatch({ type: "SAVE_SETUP", v: data })
  };

  return (
    <InterviewContext.Provider value={value}>
      {children}
    </InterviewContext.Provider>
  );
}
