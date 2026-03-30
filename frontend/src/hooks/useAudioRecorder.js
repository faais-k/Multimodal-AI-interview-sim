import { useRef, useState, useCallback, useEffect } from "react";

function getSupportedMimeType() {
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
    "audio/ogg",
    "audio/mp4",
  ];
  if (typeof MediaRecorder === "undefined") return "";
  for (const type of candidates) {
    if (MediaRecorder.isTypeSupported(type)) return type;
  }
  return "";
}

export function useAudioRecorder() {
  const [recording,  setRecording]  = useState(false);
  const [audioBlob,  setAudioBlob]  = useState(null);
  const [audioURL,   setAudioURL]   = useState(null);
  const [micError,   setMicError]   = useState(null);
  const mediaRef  = useRef(null);
  const chunksRef = useRef([]);

  const start = useCallback(async () => {
    setMicError(null);
    try {
      const stream   = await navigator.mediaDevices.getUserMedia({ audio: true });
      chunksRef.current = [];
      const mimeType = getSupportedMimeType();
      const opts     = mimeType ? { mimeType } : {};
      const mr       = new MediaRecorder(stream, opts);

      mr.ondataavailable = e => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      mr.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: mimeType || "audio/webm" });
        if (audioURL) URL.revokeObjectURL(audioURL);
        const newURL = URL.createObjectURL(blob);
        setAudioBlob(blob);
        setAudioURL(newURL);
        stream.getTracks().forEach(t => t.stop());
      };
      mr.start();
      mediaRef.current = mr;
      setRecording(true);
      setAudioBlob(null);
      setAudioURL(null);
    } catch (e) {
      console.error("Mic access failed:", e);
      setMicError("Microphone access denied. Please allow microphone access and try again.");
    }
  }, [audioURL]);

  const stop = useCallback(() => {
    if (mediaRef.current && mediaRef.current.state !== "inactive") {
      mediaRef.current.stop();
      setRecording(false);
    }
  }, []);

  const reset = useCallback(() => {
    if (audioURL) URL.revokeObjectURL(audioURL);
    setAudioBlob(null);
    setAudioURL(null);
    setRecording(false);
    setMicError(null);
  }, [audioURL]);

  useEffect(() => {
    return () => {
      if (audioURL) URL.revokeObjectURL(audioURL);
    };
  }, [audioURL]);

  return { recording, audioBlob, audioURL, micError, start, stop, reset };
}
