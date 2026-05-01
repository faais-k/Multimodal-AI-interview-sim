import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

export function ProcessingVisualization({ className, size = "md" }) {
  const sizes = {
    sm: { container: 100, center: 16, orbit: 30, node: 8 },
    md: { container: 160, center: 24, orbit: 50, node: 12 },
    lg: { container: 240, center: 32, orbit: 80, node: 16 },
  };

  const s = sizes[size];

  return (
    <div 
      className={cn("relative flex items-center justify-center", className)}
      style={{ width: s.container, height: s.container }}
    >
      {/* Center node */}
      <motion.div
        className="absolute rounded-full bg-ascent-blue shadow-lg z-20"
        style={{ 
          width: s.center, 
          height: s.center,
          boxShadow: "0 0 30px rgba(37, 99, 235, 0.4)"
        }}
        animate={{
          scale: [1, 1.05, 1],
        }}
        transition={{
          duration: 2,
          ease: "easeInOut",
          repeat: Infinity,
        }}
      />

      {/* Orbit ring */}
      <div 
        className="absolute rounded-full border border-border-subtle"
        style={{ width: s.orbit * 2, height: s.orbit * 2 }}
      />

      {/* Orbiting nodes */}
      {[0, 1, 2].map((i) => (
        <motion.div
          key={i}
          className="absolute rounded-full z-10"
          style={{
            width: s.node,
            height: s.node,
            background: i === 0 ? "#D97706" : i === 1 ? "#6B6B66" : "#9B9B95",
          }}
          animate={{
            rotate: 360,
          }}
          transition={{
            duration: 3 + i,
            ease: "linear",
            repeat: Infinity,
          }}
        >
          <motion.div
            style={{
              position: "absolute",
              top: "50%",
              left: "50%",
              transform: `translate(-50%, -50%) translateX(${s.orbit}px)`,
            }}
          >
            <div 
              className="rounded-full"
              style={{
                width: s.node,
                height: s.node,
                background: i === 0 ? "#D97706" : i === 1 ? "#6B6B66" : "#9B9B95",
              }}
            />
          </motion.div>
        </motion.div>
      ))}

      {/* Connection lines */}
      <svg 
        className="absolute inset-0 w-full h-full pointer-events-none"
        viewBox={`0 0 ${s.container} ${s.container}`}
      >
        {[0, 1, 2].map((i) => (
          <motion.line
            key={i}
            x1={s.container / 2}
            y1={s.container / 2}
            x2={s.container / 2 + Math.cos((i * 120 * Math.PI) / 180) * s.orbit}
            y2={s.container / 2 + Math.sin((i * 120 * Math.PI) / 180) * s.orbit}
            stroke="#2563EB"
            strokeWidth="1"
            strokeOpacity="0.3"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{
              duration: 0.5,
              delay: i * 0.3,
              repeat: Infinity,
              repeatDelay: 2,
            }}
          />
        ))}
      </svg>

      {/* Pulse rings from center */}
      {[0, 1].map((i) => (
        <motion.div
          key={i}
          className="absolute rounded-full border border-ascent-blue/30"
          style={{
            width: s.center,
            height: s.center,
          }}
          animate={{
            scale: [1, 3],
            opacity: [0.6, 0],
          }}
          transition={{
            duration: 2,
            ease: "easeOut",
            repeat: Infinity,
            delay: i * 1,
          }}
        />
      ))}
    </div>
  );
}
