import { motion, useSpring, useTransform } from "framer-motion";
import { useEffect, useState } from "react";
import { cn, formatScore } from "@/lib/utils";

export function ScoreReveal({ 
  score, 
  className, 
  size = "lg",
  showVerdict = true,
  delay = 0.3
}) {
  const [displayScore, setDisplayScore] = useState(0);
  
  const spring = useSpring(0, {
    stiffness: 50,
    damping: 20,
    duration: 1.5,
  });
  
  useEffect(() => {
    const timer = setTimeout(() => {
      spring.set(score);
    }, delay * 1000);
    return () => clearTimeout(timer);
  }, [score, spring, delay]);
  
  useEffect(() => {
    const unsubscribe = spring.on("change", (latest) => {
      setDisplayScore(latest);
    });
    return unsubscribe;
  }, [spring]);

  const circumference = 2 * Math.PI * 45;
  const strokeDashoffset = useTransform(
    spring,
    [0, 10],
    [circumference, circumference * (1 - score / 10)]
  );

  const sizes = {
    sm: { container: 80, fontSize: "text-2xl", ringWidth: 4 },
    md: { container: 140, fontSize: "text-4xl", ringWidth: 6 },
    lg: { container: 200, fontSize: "text-6xl", ringWidth: 8 },
  };

  const s = sizes[size];
  const verdict = score >= 8 ? "EXCELLENT" : score >= 6.5 ? "SOLID" : score >= 5 ? "BORDERLINE" : "NEEDS WORK";
  const verdictColor = score >= 8 ? "bg-veridian-subtle text-veridian" : score >= 6.5 ? "bg-veridian-subtle text-veridian" : score >= 5 ? "bg-semantic-warning-bg text-semantic-warning" : "bg-semantic-error-bg text-semantic-error";

  return (
    <div className={cn("flex flex-col items-center", className)}>
      <div 
        className="relative flex items-center justify-center"
        style={{ width: s.container, height: s.container }}
      >
        {/* Background ring */}
        <svg 
          className="absolute inset-0 w-full h-full -rotate-90"
          viewBox="0 0 100 100"
        >
          <circle
            cx="50"
            cy="50"
            r="45"
            fill="none"
            stroke="#F0EFEA"
            strokeWidth={s.ringWidth}
          />
          <motion.circle
            cx="50"
            cy="50"
            r="45"
            fill="none"
            stroke="#059669"
            strokeWidth={s.ringWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            style={{ strokeDashoffset }}
            initial={{ strokeDashoffset: circumference }}
          />
        </svg>

        {/* Score display */}
        <motion.div
          className={cn("font-mono font-bold text-text-primary", s.fontSize)}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay, duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        >
          {formatScore(displayScore)}
        </motion.div>
      </div>

      {showVerdict && (
        <motion.div
          className={cn("mt-3 px-3 py-1.5 rounded-sm text-xs font-semibold", verdictColor)}
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: delay + 0.8, duration: 0.4, ease: [0.34, 1.56, 0.64, 1] }}
        >
          {verdict}
        </motion.div>
      )}
    </div>
  );
}
