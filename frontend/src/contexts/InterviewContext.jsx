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
  step:           "landing",
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
  const setError      = v => dispatch({ type: "SET_ERROR",      v });
  const setStep       = v => dispatch({ type: "SET_STEP",       v });
  const setReport     = v => dispatch({ type: "SET_REPORT",     v });

  useEffect(() => {
    const sid = sessionStorage.getItem(SESSION_KEY);
    if (sid) dispatch({ type: "SET_SESSION", v: sid });
  }, []);

  const setup = useCallback(async (data) => {
    setLoading(true);
    try {
      const { session_id } = await api.createSession();
      sessionStorage.setItem(SESSION_KEY, session_id);
      dispatch({ type: "SET_SESSION", v: session_id });
      dispatch({ type: "SAVE_SETUP", v: data });
      setStep("pre-interview");
      setLoading(false);
    } catch (e) {
      setError(e.message || "Setup failed.");
    }
  }, []);

  const restart = useCallback(() => {
    sessionStorage.removeItem(SESSION_KEY);
    dispatch({ type: "RESET" });
  }, []);

  const value = {
    ...state,
    setup,
    restart,
    setStep,
    setReport,
    setError
  };

  return (
    <InterviewContext.Provider value={value}>
      {children}
    </InterviewContext.Provider>
  );
}
