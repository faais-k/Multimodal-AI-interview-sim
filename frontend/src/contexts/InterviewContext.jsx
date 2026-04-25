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
const INTERVIEW_STATE_KEY = "ai_interview_state";

const INIT = {
  sessionId:      null,
  step:           "landing", // landing | dashboard | setup | pre-interview | interview | processing | results
  question:       null,
  questionNumber: 0,
  totalQuestions: 0,
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
    case "SET_STEP":
      sessionStorage.setItem("ai_interview_step", a.v);
      return { ...s, step: a.v };
    case "SET_QUESTION": return { ...s, question: a.v, questionNumber: a.questionNumber || s.questionNumber + 1, totalQuestions: a.total || s.totalQuestions, loading: false, evaluating: false };
    case "RESTORE_STATE":
      if (a.state.step) sessionStorage.setItem("ai_interview_step", a.state.step);
      return { ...s, ...a.state, loading: false, evaluating: false };
    case "SET_TOTAL_QUESTIONS": return { ...s, totalQuestions: a.v };
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

  // Load session from storage on mount and recover state from backend
  useEffect(() => {
    const sid = sessionStorage.getItem(SESSION_KEY);
    const storedStep = sessionStorage.getItem("ai_interview_step");
    
    if (sid) {
      setSession(sid);
      
      // If we have a stored step, restore it immediately for better UX
      if (storedStep && storedStep !== "landing") {
        dispatch({
          type: "RESTORE_STATE",
          state: { step: storedStep, sessionId: sid }
        });
      }
      
      // Recover interview state from backend after page refresh
      const recoverState = async () => {
        try {
          const status = await api.getSessionStatus(sid);
          
          // If there's an active interview in progress
          if (status.has_active_question && status.current_question) {
            // Restore to interview step with current question
            dispatch({
              type: "RESTORE_STATE",
              state: {
                step: "interview",
                question: status.current_question,
                questionNumber: status.question_number,
                totalQuestions: status.total_questions,
                sessionId: sid
              }
            });
          } else if (status.status === "completed") {
            // Interview was completed
            dispatch({
              type: "RESTORE_STATE",
              state: {
                step: "dashboard",
                sessionId: sid
              }
            });
          }
          // If no active question, user stays at their current step
        } catch (e) {
          console.warn("Failed to recover session state:", e);
        }
      };
      
      recoverState();
    }
  }, []);

  const startInterview = useCallback(async () => {
    if (!state.sessionId) return;
    setLoading(true);
    try {
      await api.startInterview(state.sessionId);
      const res = await api.nextQuestion(state.sessionId);
      dispatch({ type: "SET_QUESTION", v: res.question, total: res.total_questions || 0 });
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
        dispatch({ type: "SET_QUESTION", v: next.question, total: next.total_questions || state.totalQuestions });
      }
    } catch (e) {
      setError(e.message || "Evaluation failed.");
    }
  }, [state.sessionId, state.question, state.totalQuestions]);

  const submitAudio = useCallback(async (blob) => {
    if (!state.sessionId || !state.question) return;
    setEvaluating(true);
    try {
      const res = await api.scoreAudio(state.sessionId, state.question.id, blob);
      
      if (res.is_final) {
        setStep("processing");
      } else {
        const next = await api.nextQuestion(state.sessionId);
        dispatch({ type: "SET_QUESTION", v: next.question, total: next.total_questions || state.totalQuestions });
      }
    } catch (e) {
      setError(e.message || "Audio evaluation failed.");
    }
  }, [state.sessionId, state.question, state.totalQuestions]);

  const restart = useCallback(() => {
    sessionStorage.removeItem(SESSION_KEY);
    dispatch({ type: "RESET" });
  }, []);

  const skipQuestion = useCallback(async () => {
    if (!state.sessionId || !state.question) return;
    setEvaluating(true);
    try {
      // Use formal skip endpoint that properly updates backend state
      const result = await api.skipQuestion(state.sessionId, state.question.id);
      dispatch({ 
        type: "SET_QUESTION", 
        v: result.next_question, 
        total: result.total_questions || state.totalQuestions,
        questionNumber: state.questionNumber // Keep same number since we're just replacing
      });
    } catch (e) {
      setError(e.message || "Failed to skip question.");
    } finally {
      setEvaluating(false);
    }
  }, [state.sessionId, state.question, state.totalQuestions, state.questionNumber]);

  const value = {
    ...state,
    setStep,
    setReport,
    setSession,
    setError,
    startInterview,
    submitText,
    submitAudio,
    skipQuestion,
    restart,
    saveSetup: (data) => dispatch({ type: "SAVE_SETUP", v: data })
  };

  return (
    <InterviewContext.Provider value={value}>
      {children}
    </InterviewContext.Provider>
  );
}
