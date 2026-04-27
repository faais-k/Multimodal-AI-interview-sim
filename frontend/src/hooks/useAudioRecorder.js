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
  const [volume,     setVolume]     = useState(0); // 0.0 to 1.0
  
  const mediaRef  = useRef(null);
  const chunksRef = useRef([]);
  const audioCtxRef = useRef(null);
  const analyserRef = useRef(null);
  const rafRef = useRef(null);

  const updateVolume = useCallback(() => {
    if (!analyserRef.current) return;
    const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
    analyserRef.current.getByteFrequencyData(dataArray);

    // Calculate average volume
    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) {
      sum += dataArray[i];
    }
    const avg = sum / dataArray.length;
    setVolume(Math.min(1, avg / 128)); // Normalize roughly to 0-1

    // Use mediaRef to check recording state (avoids stale closure)
    if (mediaRef.current && mediaRef.current.state === "recording") {
      rafRef.current = requestAnimationFrame(updateVolume);
    }
  }, []);

  const start = useCallback(async () => {
    setMicError(null);
    
    if (audioURL) URL.revokeObjectURL(audioURL);
    setAudioBlob(null);
    setAudioURL(null);
    setVolume(0);
    
    try {
      const stream   = await navigator.mediaDevices.getUserMedia({ audio: true });
      chunksRef.current = [];
      const mimeType = getSupportedMimeType();
      const opts     = mimeType ? { mimeType } : {};
      const mr       = new MediaRecorder(stream, opts);

      // Setup audio analysis for volume
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (AudioContext) {
        audioCtxRef.current = new AudioContext();
        analyserRef.current = audioCtxRef.current.createAnalyser();
        const source = audioCtxRef.current.createMediaStreamSource(stream);
        source.connect(analyserRef.current);
        analyserRef.current.fftSize = 256;
      }

      mr.ondataavailable = e => { 
        if (e.data && e.data.size > 0) {
          chunksRef.current.push(e.data); 
        }
      };

      mr.onstop = () => {
        try {
          if (chunksRef.current.length === 0) {
            console.warn("No audio chunks collected.");
            setMicError("No audio was captured. Please speak into the microphone.");
            setRecording(false);
            return;
          }

          const blob = new Blob(chunksRef.current, { type: mimeType || "audio/webm" });
          const newURL = URL.createObjectURL(blob);
          setAudioBlob(blob);
          setAudioURL(newURL);
        } catch (err) {
          console.error("Error creating audio blob:", err);
          setMicError("Failed to process audio recording.");
        } finally {
          stream.getTracks().forEach(t => t.stop());
          chunksRef.current = [];
          
          if (rafRef.current) cancelAnimationFrame(rafRef.current);
          if (audioCtxRef.current && audioCtxRef.current.state !== 'closed') {
            audioCtxRef.current.close().catch(() => {});
          }
          setVolume(0);
          setRecording(false);
        }
      };
      
      // Start recording with 1s timeslice to ensure data is periodically pushed
      mr.start(1000);
      mediaRef.current = mr;
      setRecording(true);
    } catch (e) {
      console.error("Mic access failed:", e);
      setMicError("Microphone access denied. Please allow microphone access and try again.");
    }
  }, [audioURL]);

  useEffect(() => {
    if (recording) {
      rafRef.current = requestAnimationFrame(updateVolume);
    } else {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      setVolume(0);
    }
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [recording]);

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
    setVolume(0);
    chunksRef.current = [];
  }, [audioURL]);

  useEffect(() => {
    return () => {
      if (audioURL) URL.revokeObjectURL(audioURL);
    };
  }, [audioURL]);

  return { 
    recording, 
    audioBlob, 
    audioURL, 
    micError, 
    volume, 
    startRecording: start, 
    stopRecording: stop, 
    reset,
    mediaRef
  };
}
