import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";

export function useAntiCheat(sessionId, enabled = false) {
  const [violations,      setViolations]      = useState([]);
  const [showWarning,     setShowWarning]     = useState(false);
  const [warningMessage,  setWarningMessage]  = useState("");
  const countRef = useRef(0);

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
    try { await api.logViolation({ session_id: sessionId, type, details }); } catch (_) {}
  }, [sessionId, enabled]);

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

  return { violations, showWarning, warningMessage, enterFullscreen, exitFullscreen };
}
