import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";

const MAX_RETRY_ATTEMPTS = 3;
const RETRY_DELAYS = [1000, 3000, 5000]; // Exponential backoff: 1s, 3s, 5s

export function useAntiCheat(sessionId, enabled = false) {
  const [violations,      setViolations]      = useState([]);
  const [showWarning,     setShowWarning]     = useState(false);
  const [warningMessage,  setWarningMessage]  = useState("");
  const [failedCount,    setFailedCount]     = useState(0);
  const countRef = useRef(0);
  const pendingQueueRef = useRef([]);
  const retryTimerRef = useRef(null);

  // Process the pending queue with retry logic
  const processQueue = useCallback(async () => {
    if (pendingQueueRef.current.length === 0 || !sessionId) return;

    const item = pendingQueueRef.current[0];
    
    try {
      await api.logViolation({
        session_id: sessionId,
        type: item.type,
        details: item.details
      });
      
      // Success - remove from queue
      pendingQueueRef.current.shift();
      setFailedCount(pendingQueueRef.current.length);
      
      // Process next item if any
      if (pendingQueueRef.current.length > 0) {
        processQueue();
      }
    } catch (err) {
      // Failed - increment retry count
      item.attempts = (item.attempts || 0) + 1;
      
      if (item.attempts >= MAX_RETRY_ATTEMPTS) {
        // Max retries reached - drop this violation and log to console
        console.warn(`Anti-cheat: Dropping violation after ${MAX_RETRY_ATTEMPTS} retries:`, item);
        pendingQueueRef.current.shift();
        setFailedCount(pendingQueueRef.current.length);
      } else {
        // Schedule retry with exponential backoff
        const delay = RETRY_DELAYS[Math.min(item.attempts - 1, RETRY_DELAYS.length - 1)];
        if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
        retryTimerRef.current = setTimeout(processQueue, delay);
      }
    }
  }, [sessionId]);

  const log = useCallback(async (type, details = "") => {
    if (!sessionId || !enabled) return;
    
    countRef.current += 1;
    const entry = { type, details, timestamp: new Date().toISOString() };
    setViolations(v => [...v, entry]);
    setWarningMessage(
      countRef.current >= 3
        ? "⚠️ Multiple violations detected. This has been logged."
        : `⚠️ ${type.replace(/_/g, " ")} detected — please stay in the interview window.`
    );
    setShowWarning(true);
    setTimeout(() => setShowWarning(false), 4000);
    
    // Add to queue and process immediately
    pendingQueueRef.current.push({ type, details, attempts: 0 });
    setFailedCount(pendingQueueRef.current.length);
    processQueue();
  }, [sessionId, enabled, processQueue]);

  // Flush remaining violations on unmount
  useEffect(() => {
    return () => {
      if (retryTimerRef.current) {
        clearTimeout(retryTimerRef.current);
      }
      // Attempt to send any remaining violations synchronously (best effort)
      if (pendingQueueRef.current.length > 0 && sessionId) {
        const remaining = [...pendingQueueRef.current];
        // Use sendBeacon if available, otherwise fire-and-forget fetch
        remaining.forEach(item => {
          const payload = JSON.stringify({
            session_id: sessionId,
            type: item.type,
            details: item.details
          });
          
          if (navigator.sendBeacon) {
            navigator.sendBeacon('/api/session/violation', new Blob([payload], { type: 'application/json' }));
          }
        });
      }
    };
  }, [sessionId]);

  useEffect(() => {
    if (!enabled) return;

    const onVisibility = () => {
      if (document.hidden) log("TAB_SWITCH", "Candidate switched tabs or minimised window");
    };

    // Debounce blur: only log if focus doesn't return within 500ms
    // Prevents false positives when clicking between page elements
    let blurTimer = null;
    const onBlur  = () => {
      blurTimer = setTimeout(() => log("WINDOW_BLUR", "Window lost focus"), 500);
    };
    const onFocus = () => {
      if (blurTimer) { clearTimeout(blurTimer); blurTimer = null; }
    };

    const onFsChange = () => {
      if (!document.fullscreenElement) log("FULLSCREEN_EXIT", "Exited fullscreen");
    };

    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("blur",  onBlur);
    window.addEventListener("focus", onFocus);
    document.addEventListener("fullscreenchange", onFsChange);

    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("blur",  onBlur);
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("fullscreenchange", onFsChange);
      if (blurTimer) clearTimeout(blurTimer);
    };
  }, [enabled, log]);

  const enterFullscreen = useCallback(() => {
    document.documentElement.requestFullscreen?.();
  }, []);

  const exitFullscreen = useCallback(() => {
    document.exitFullscreen?.();
  }, []);

  return { 
    violations, 
    showWarning, 
    warningMessage, 
    failedCount,
    enterFullscreen, 
    exitFullscreen 
  };
}
