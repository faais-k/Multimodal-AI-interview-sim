/**
 * PostureMonitor — MediaPipe BlazePose in-browser.
 * GPU delegate with automatic CPU fallback.
 * Video stream assigned immediately; pose is optional overlay.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";

const POSE_LABELS = {
  GOOD:             { color: "#48bb78", text: "✅ Good Posture"      },
  SLOUCHING:        { color: "#ed8936", text: "⚠️ Sit Up Straight"   },
  HEAD_FORWARD:     { color: "#ed8936", text: "⚠️ Head Forward"      },
  LOOKING_AWAY:     { color: "#fc8181", text: "👀 Looking Away"      },
  FACE_NOT_VISIBLE: { color: "#fc8181", text: "👁 Face Not Visible"  },
  NO_POSE:          { color: "#a0a3b1", text: "📷 Loading Camera…"   },
};

export default function PostureMonitor({ sessionId, stream }) {
  const videoRef   = useRef(null);
  const canvasRef  = useRef(null);
  const poseRef    = useRef(null);
  const timerRef   = useRef(null);
  const sendRef    = useRef(null);
  const metricsRef = useRef([]);
  const lastTsRef  = useRef(0);
  const baselineRef = useRef({ count: 0, noseShoulderOffset: 0 });

  const [status,    setStatus]    = useState("NO_POSE");
  const [poseReady, setPoseReady] = useState(false);
  const [poseError, setPoseError] = useState(null);

  // Assign stream to video immediately — even if pose fails, camera still shows
  useEffect(() => {
    if (!stream || !videoRef.current) return;
    videoRef.current.srcObject = stream;
    videoRef.current.play().catch(() => {});
  }, [stream]);

  const analysePosture = useCallback((landmarks) => {
    // Q1: Head-forward check uses NOSE (0), LEFT_SHOULDER (11), RIGHT_SHOULDER (12),
    // and torso/slouching also uses LEFT_HIP (23), RIGHT_HIP (24).
    // Q2: Previous HEAD_FORWARD threshold was nose.z < lS.z - 0.15.
    // Q3: Previous torso_angle was not calculated from landmarks here; metrics used a hardcoded 90.
    if (!landmarks || landmarks.length < 25) {
      return { label: "FACE_NOT_VISIBLE", score: 0.1, torsoAngle: 0 };
    }

    const NOSE = 0;
    const LEFT_SHOULDER = 11;
    const RIGHT_SHOULDER = 12;
    const LEFT_HIP = 23;
    const RIGHT_HIP = 24;

    const nose = landmarks[NOSE];
    const lS = landmarks[LEFT_SHOULDER];
    const rS = landmarks[RIGHT_SHOULDER];
    const lH = landmarks[LEFT_HIP];
    const rH = landmarks[RIGHT_HIP];

    if (!nose || !lS || !rS || !lH || !rH) {
      return { label: "FACE_NOT_VISIBLE", score: 0.1, torsoAngle: 0 };
    }
    if (nose.visibility < 0.5) {
      return { label: "LOOKING_AWAY", score: 0.1, torsoAngle: 0 };
    }

    const shoulderMidX = (lS.x + rS.x) / 2;
    const shoulderMidY = (lS.y + rS.y) / 2;
    const hipMidY = (lH.y + rH.y) / 2;
    const shoulderDiffY = Math.abs(lS.y - rS.y);
    const noseForwardOffset = Math.abs(nose.x - shoulderMidX);
    const torsoHeight = hipMidY - shoulderMidY;
    const torsoAngle = Math.round(Math.abs(shoulderMidY - hipMidY) * 100);

    // First 3 snapshots: calibrate baseline nose-to-shoulder horizontal offset.
    if (baselineRef.current.count < 3) {
      baselineRef.current.noseShoulderOffset += noseForwardOffset;
      baselineRef.current.count += 1;
      return { label: "NO_POSE", score: 0.5, torsoAngle };
    }
    const baselineOffset = baselineRef.current.noseShoulderOffset / baselineRef.current.count;

    // Relaxed thresholds to reduce false positives
    const isHeadForward = (noseForwardOffset - baselineOffset) > 0.12;
    const isSlouching = torsoHeight < 0.18 || shoulderDiffY > 0.12;
    const isHeadUp = nose.y < shoulderMidY;
    const shouldersLevel = shoulderDiffY < 0.10;
    const headAligned = (noseForwardOffset - baselineOffset) <= 0.08;

    if (isHeadForward) {
      return { label: "HEAD_FORWARD", score: 0.4, torsoAngle };
    }
    if (isSlouching) {
      return { label: "SLOUCHING", score: 0.3, torsoAngle };
    }
    if (headAligned && shouldersLevel && isHeadUp) {
      return { label: "GOOD", score: 0.9, torsoAngle };
    }
    return { label: "SLOUCHING", score: 0.3, torsoAngle };
  }, []);

  const drawSkeleton = useCallback((canvas, landmarks) => {
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!landmarks) return;

    const W = canvas.width, H = canvas.height;
    const CONNECTIONS = [
      [11,12],[11,23],[12,24],[23,24],
      [11,13],[13,15],[12,14],[14,16],
      [0,11],[0,12],
    ];

    ctx.strokeStyle = "rgba(102,126,234,0.85)";
    ctx.lineWidth   = 2.5;
    for (const [a, b] of CONNECTIONS) {
      const pa = landmarks[a], pb = landmarks[b];
      if (!pa || !pb || pa.visibility < 0.45 || pb.visibility < 0.45) continue;
      ctx.beginPath();
      ctx.moveTo(pa.x * W, pa.y * H);
      ctx.lineTo(pb.x * W, pb.y * H);
      ctx.stroke();
    }
    for (const i of [0, 11, 12, 23, 24]) {
      const p = landmarks[i];
      if (!p || p.visibility < 0.45) continue;
      ctx.beginPath();
      ctx.arc(p.x * W, p.y * H, 5, 0, Math.PI * 2);
      ctx.fillStyle = "#667eea";
      ctx.fill();
    }
  }, []);

  // MediaPipe init — GPU first, CPU fallback
  useEffect(() => {
    if (!stream) return;
    let cancelled = false;

    (async () => {
      for (const delegate of ["GPU", "CPU"]) {
        if (cancelled) return;
        try {
          const { PoseLandmarker, FilesetResolver } =
            await import("@mediapipe/tasks-vision");

          const vision = await FilesetResolver.forVisionTasks(
            "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm"
          );

          const landmarker = await PoseLandmarker.createFromOptions(vision, {
            baseOptions: {
              modelAssetPath:
                "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task",
              delegate,
            },
            runningMode: "VIDEO",
            numPoses:    1,
          });

          poseRef.current = landmarker;
          setPoseReady(true);
          setPoseError(null);
          console.log(`✅ MediaPipe pose ready (delegate=${delegate})`);
          return;
        } catch (e) {
          console.warn(`MediaPipe init failed (delegate=${delegate}):`, e);
          if (delegate === "CPU") {
            setPoseError("Pose detection unavailable — camera shown without skeleton.");
          }
        }
      }
    })();

    return () => {
      cancelled = true;
      // Close PoseLandmarker to free resources
      if (poseRef.current && poseRef.current.close) {
        poseRef.current.close();
        poseRef.current = null;
      }
    };
  }, [stream]);

  // Analysis loop
  useEffect(() => {
    if (!poseReady || !poseRef.current) return;
    baselineRef.current = { count: 0, noseShoulderOffset: 0 };

    timerRef.current = setInterval(() => {
      const video  = videoRef.current;
      const canvas = canvasRef.current;
      if (!video || !canvas || video.readyState < 2 || video.paused) return;

      canvas.width  = video.videoWidth  || 320;
      canvas.height = video.videoHeight || 240;

      const now = performance.now();
      if (now <= lastTsRef.current) return;
      lastTsRef.current = now;

      try {
        const result = poseRef.current.detectForVideo(video, now);
        const lm     = result.landmarks?.[0];
        drawSkeleton(canvas, lm);
        const posture = analysePosture(lm);
        setStatus(posture.label);
        metricsRef.current.push({
          posture_score: posture.score,
          posture_label: posture.label,
          spine_height:  posture.torsoAngle,
          hands_visible: true,
          timestamp:     Date.now(),
        });
      } catch (_) {}
    }, 500);

    // Metrics buffer with retry logic
    const metricsBuffer = [];
    let consecutiveFailures = 0;
    const MAX_BUFFER_SIZE = 100; // Prevent unbounded growth

    sendRef.current = setInterval(async () => {
      if (!sessionId || metricsRef.current.length === 0) return;

      // Add new metrics to buffer
      metricsBuffer.push(...metricsRef.current);
      if (metricsBuffer.length > MAX_BUFFER_SIZE) {
        // Keep only the most recent metrics if buffer overflows
        metricsBuffer.splice(0, metricsBuffer.length - MAX_BUFFER_SIZE);
      }
      metricsRef.current = [];

      // Send latest metric from buffer
      const latest = metricsBuffer[metricsBuffer.length - 1];
      if (!latest) return;

      try {
        await api.sendPosture({ session_id: sessionId, metrics: latest });
        // Success - clear buffer and reset failure count
        metricsBuffer.length = 0;
        consecutiveFailures = 0;
      } catch (err) {
        consecutiveFailures++;
        console.warn(`Posture metrics send failed (${consecutiveFailures}x):`, err);

        // After 3 consecutive failures, send a batch of aggregated data
        if (consecutiveFailures >= 3 && metricsBuffer.length > 1) {
          try {
            // Calculate average metrics for batch
            const avgScore = metricsBuffer.reduce((sum, m) => sum + (m.posture_score || 0), 0) / metricsBuffer.length;
            const modeLabel = metricsBuffer
              .map(m => m.posture_label)
              .sort((a, b) =>
                metricsBuffer.filter(m => m.posture_label === a).length -
                metricsBuffer.filter(m => m.posture_label === b).length
              ).pop();

            const batchMetric = {
              posture_score: avgScore,
              posture_label: modeLabel,
              spine_height: metricsBuffer[metricsBuffer.length - 1].spine_height,
              hands_visible: true,
              timestamp: Date.now(),
              batch_size: metricsBuffer.length,
              batch_aggregated: true
            };

            await api.sendPosture({ session_id: sessionId, metrics: batchMetric });
            metricsBuffer.length = 0;
            consecutiveFailures = 0;
          } catch (batchErr) {
            console.warn("Batch posture send also failed:", batchErr);
          }
        }
      }
    }, 30000);

    return () => {
      clearInterval(timerRef.current);
      clearInterval(sendRef.current);
      
      // Attempt to flush remaining metrics on unmount
      if (sessionId && metricsBuffer.length > 0) {
        const latest = metricsBuffer[metricsBuffer.length - 1];
        const payload = JSON.stringify({
          session_id: sessionId,
          metrics: {
            ...latest,
            flush_on_unmount: true,
            timestamp: Date.now()
          }
        });
        
        // Use sendBeacon for best-effort delivery on unmount
        if (navigator.sendBeacon) {
          navigator.sendBeacon('/api/posture/report', new Blob([payload], { type: 'application/json' }));
        }
        
        metricsBuffer.length = 0;
      }
    };
  }, [poseReady, sessionId, analysePosture, drawSkeleton]);

  const badge = POSE_LABELS[status] || POSE_LABELS.GOOD;

  return (
    <div style={S.wrap}>
      <div style={S.videoWrap}>
        <video ref={videoRef} muted playsInline style={S.video} />
        <canvas ref={canvasRef} style={S.canvas} />
        <div style={{ ...S.badge, background: badge.color + "22", border: `1px solid ${badge.color}55`, color: badge.color }}>
          {badge.text}
        </div>
        {poseError && <div style={S.errorNote}>⚠️ {poseError}</div>}
      </div>
    </div>
  );
}

const S = {
  wrap:      { width: "100%" },
  videoWrap: { position: "relative", background: "#0f1117", borderRadius: "12px", overflow: "hidden", aspectRatio: "4/3" },
  video:     { width: "100%", height: "100%", objectFit: "cover", transform: "scaleX(-1)" },
  canvas:    { position: "absolute", inset: 0, width: "100%", height: "100%", transform: "scaleX(-1)", pointerEvents: "none" },
  badge:     { position: "absolute", bottom: "8px", left: "8px", right: "8px", borderRadius: "6px", padding: "5px 10px", fontSize: "12px", fontWeight: 600, textAlign: "center" },
  errorNote: { position: "absolute", top: "8px", left: "8px", right: "8px", background: "rgba(0,0,0,0.75)", color: "#a0a3b1", fontSize: "11px", textAlign: "center", borderRadius: "4px", padding: "4px 8px" },
};
