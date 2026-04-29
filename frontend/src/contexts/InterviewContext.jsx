import React, { createContext, useContext, useCallback, useReducer, useEffect, useRef } from "react";
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
    case "SET_SESSION":
      sessionStorage.setItem(SESSION_KEY, a.v);
      return { ...s, sessionId: a.v };
    case "SET_STEP":
      sessionStorage.setItem("ai_interview_step", a.v);
      return { ...s, step: a.v };
    case "SET_QUESTION": 
      const isSameQ = s.question && a.v && s.question.id === a.v.id;
      return { 
        ...s, 
        question: a.v, 
        questionNumber: a.questionNumber || (isSameQ ? s.questionNumber : s.questionNumber + 1), 
        totalQuestions: a.total || s.totalQuestions, 
        loading: false, 
        evaluating: false 
      };
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
  const startInFlightRef = useRef(false);
  const submitInFlightRef = useRef(false);
  const skipInFlightRef = useRef(false);

  const setLoading    = v => dispatch({ type: "SET_LOADING",    v });
  const setEvaluating = v => dispatch({ type: "SET_EVALUATING", v });
  const setError      = v => dispatch({ type: "SET_ERROR",      v });
  const setStep       = v => dispatch({ type: "SET_STEP",       v });
  const setReport     = v => dispatch({ type: "SET_REPORT",     v });
  const setSession    = v => dispatch({ type: "SET_SESSION",    v });

  // Adaptive Polling Logic
  useEffect(() => {
    let timer;
    let pollCount = 0;

    const pollStatus = async () => {
      if (!state.sessionId || !state.evaluating) return;

      try {
        pollCount++;
        const status = await api.getSessionStatus(state.sessionId);

        // If backend says question is active again, or interview is complete
        if (status.status === "question_active" || status.status === "followup_pending") {
          const next = await api.nextQuestion(state.sessionId);
          if (next.status === "completed" || next.status === "awaiting_wrapup_answer" || !next.question) {
            setStep("processing");
          } else {
            dispatch({ type: "SET_QUESTION", v: next.question, total: next.total_questions || state.totalQuestions });
          }
        } else if (status.status === "interview_complete" || status.status === "report_generated") {
          setStep("processing");
        } else if (status.status === "failed") {
          setError(status.error || "The evaluation failed. Please try again or contact support.");
          setEvaluating(false);
        } else {
          // Still pending (answer_pending or scoring_pending)
          scheduleNext();
        }
      } catch (e) {
        console.warn("Polling error:", e);
        scheduleNext();
      }
    };

    const scheduleNext = () => {
      if (!state.evaluating) return;
      // Adaptive interval: 1s for first 10 tries, then 2s, then 5s
      const interval = pollCount < 10 ? 1000 : pollCount < 20 ? 2000 : 5000;
      timer = setTimeout(pollStatus, interval);
    };

    if (state.evaluating) {
      scheduleNext();
    }

    return () => {
      if (timer) clearTimeout(timer);
    };
  }, [state.evaluating, state.sessionId, state.totalQuestions]);

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

          // Handle expired sessions
          if (status.status === "expired") {
            console.warn("Session expired:", status.message);
            sessionStorage.removeItem(SESSION_KEY);
            sessionStorage.removeItem("ai_interview_step");
            dispatch({ type: "SET_ERROR", v: "Your session has expired. Please start a new interview." });
            dispatch({ type: "SET_STEP", v: "landing" });
            return;
          }

          // Handle sessions that don't exist on backend (cleaned up or invalid)
          if (status.status === "not_started" && storedStep === "interview") {
            console.warn("Session not found on backend, clearing local state");
            sessionStorage.removeItem(SESSION_KEY);
            sessionStorage.removeItem("ai_interview_step");
            dispatch({ type: "SET_ERROR", v: "Session not found. Please start a new interview." });
            dispatch({ type: "SET_STEP", v: "landing" });
            return;
          }

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
            // Interview was completed - trigger results pipeline
            dispatch({
              type: "RESTORE_STATE",
              state: {
                step: "processing",
                sessionId: sid
              }
            });
          } else if (storedStep === "interview" && status.status === "active") {
            // Last answer was already saved, but no unanswered question is active.
            // This happens after a refresh between scoring and fetching the next question.
            const next = await api.nextQuestion(sid);
            if (next.status === "completed" || next.status === "awaiting_wrapup_answer" || !next.question) {
              dispatch({ type: "CLEAR_QUESTION" });
              dispatch({ type: "SET_STEP", v: "processing" });
            } else {
              dispatch({
                type: "RESTORE_STATE",
                state: {
                  step: "interview",
                  question: next.question,
                  questionNumber: (status.questions_asked_count || 0) + 1,
                  totalQuestions: next.total_questions || status.total_questions,
                  sessionId: sid
                }
              });
            }
          }
          // If the interview failed
          if (status.status === "failed") {
            setError(status.error || "The interview encountered an error. You can try to resume or restart.");
            // If we have an active question, we can still try to stay on interview step
            if (status.has_active_question && status.current_question) {
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
            }
            return;
          }

          // If no active question, user stays at their current step
        } catch (e) {
          console.warn("Failed to recover session state:", e);
          // If 404, session doesn't exist - clear and redirect
          if (e.status === 404) {
            sessionStorage.removeItem(SESSION_KEY);
            sessionStorage.removeItem("ai_interview_step");
            dispatch({ type: "SET_ERROR", v: "Session not found. Please start a new interview." });
            dispatch({ type: "SET_STEP", v: "landing" });
          }
        }
      };

      recoverState();
    }
  }, []);

  const startInterview = useCallback(async () => {
    if (!state.sessionId) return;
    if (startInFlightRef.current) return;
    startInFlightRef.current = true;
    setLoading(true);
    try {
      await api.startInterview(state.sessionId);
      const res = await api.nextQuestion(state.sessionId);
      if (res.status === "completed" || res.status === "awaiting_wrapup_answer" || !res.question) {
        setLoading(false);
        setStep("processing");
      } else {
        dispatch({ type: "SET_QUESTION", v: res.question, total: res.total_questions || 0 });
        setStep("interview");
      }
    } catch (e) {
      setError(e.message || "Could not start interview.");
    } finally {
      startInFlightRef.current = false;
    }
  }, [state.sessionId]);

  const submitText = useCallback(async (text) => {
    if (!state.sessionId || !state.question) return;
    if (submitInFlightRef.current) return;
    submitInFlightRef.current = true;
    setEvaluating(true);
    try {
      const res = await api.scoreText({
        session_id: state.sessionId,
        question_id: state.question.id,
        answer_text: text
      });
      
      // HALT: If anti-cheat triggered, do not advance. Let the user try again.
      if (res.scoring_method === "cheating_detected") {
        setEvaluating(false);
        submitInFlightRef.current = false;
        return res; // Return so Interview.jsx can show the toast
      }

      if (res.is_final || res.is_completed) {
        setStep("processing");
      } else {
        const next = await api.nextQuestion(state.sessionId);
        if (next.status === "completed" || next.status === "awaiting_wrapup_answer" || !next.question) {
          setStep("processing");
        } else {
          dispatch({ type: "SET_QUESTION", v: next.question, total: next.total_questions || state.totalQuestions });
        }
      }
      setEvaluating(false);
      return res;
    } catch (e) {
      // If it's a timeout or network error, we DON'T stop evaluating.
      // We let the polling effect take over to see if it eventually completes.
      if (e.status === 408 || e.isTimeout || e.isNetworkError) {
        console.warn("Submission timed out/failed, but staying in evaluating state for polling recovery.");
      } else {
        setError(e.message || "Evaluation failed.");
        setEvaluating(false);
      }
    } finally {
      submitInFlightRef.current = false;
    }
  }, [state.sessionId, state.question, state.totalQuestions]);

  const submitAudio = useCallback(async (blob) => {
    if (!state.sessionId || !state.question) return;
    if (submitInFlightRef.current) return;
    submitInFlightRef.current = true;
    setEvaluating(true);
    try {
      const res = await api.scoreAudio(state.sessionId, state.question.id, blob);
      
      // HALT: If anti-cheat triggered, do not advance.
      if (res.scoring_method === "cheating_detected") {
        setEvaluating(false);
        submitInFlightRef.current = false;
        return res;
      }

      if (res.is_final || res.is_completed) {
        setStep("processing");
      } else {
        const next = await api.nextQuestion(state.sessionId);
        if (next.status === "completed" || next.status === "awaiting_wrapup_answer" || !next.question) {
          setStep("processing");
        } else {
          dispatch({ type: "SET_QUESTION", v: next.question, total: next.total_questions || state.totalQuestions });
        }
      }
      setEvaluating(false);
      return res;
    } catch (e) {
      if (e.status === 408 || e.isTimeout || e.isNetworkError) {
        console.warn("Audio submission timed out/failed, staying in evaluating state for polling recovery.");
      } else {
        setError(e.message || "Audio evaluation failed.");
        setEvaluating(false);
      }
    } finally {
      submitInFlightRef.current = false;
    }
  }, [state.sessionId, state.question, state.totalQuestions]);

  const restart = useCallback(() => {
    sessionStorage.removeItem(SESSION_KEY);
    dispatch({ type: "RESET" });
  }, []);

  const skipQuestion = useCallback(async () => {
    if (!state.sessionId || !state.question) return;
    if (skipInFlightRef.current || submitInFlightRef.current) return;
    skipInFlightRef.current = true;
    setEvaluating(true);
    try {
      // Use formal skip endpoint that properly updates backend state
      const result = await api.skipQuestion(state.sessionId, state.question.id);
      if (!result.next_question) {
        setStep("processing");
        return;
      }
      dispatch({ 
        type: "SET_QUESTION", 
        v: result.next_question, 
        total: result.total_questions || state.totalQuestions
      });
    } catch (e) {
      setError(e.message || "Failed to skip question.");
    } finally {
      skipInFlightRef.current = false;
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
