import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

export function ListeningIndicator({ className, size = "md", volume = 0 }) {
  const sizes = {
    sm: { container: 48, ring1: 48, ring2: 36, ring3: 24, core: 10 },
    md: { container: 80, ring1: 80, ring2: 60, ring3: 40, core: 16 },
    lg: { container: 120, ring1: 120, ring2: 90, ring3: 60, core: 24 },
  };

  const s = sizes[size];
  
  // Calculate dynamic scale based on volume (0 to 1)
  // Base scale + (volume * multiplier)
  const volScale = 1 + (volume * 1.5);

  return (
    <div 
      className={cn("relative flex items-center justify-center", className)}
      style={{ width: s.container, height: s.container }}
    >
      {/* Outer ring */}
      <motion.div
        className="absolute rounded-full border-2 border-ascent-blue/40"
        style={{ width: s.ring1, height: s.ring1 }}
        animate={{
          scale: [1, 1.3, 1],
          opacity: [0.3, 0.6, 0.3],
        }}
        transition={{
          duration: 2.4,
          ease: "easeInOut",
          repeat: Infinity,
        }}
      />
      
      {/* Middle ring */}
      <motion.div
        className="absolute rounded-full border-2 border-ascent-blue/60"
        style={{ width: s.ring2, height: s.ring2 }}
        animate={{
          scale: [1, 1.2, 1],
          opacity: [0.2, 0.4, 0.2],
        }}
        transition={{
          duration: 2.4,
          ease: "easeInOut",
          repeat: Infinity,
          delay: 0.4,
        }}
      />
      
      {/* Inner ring */}
      <motion.div
        className="absolute rounded-full border-2 border-ascent-blue/50"
        style={{ width: s.ring3, height: s.ring3 }}
        animate={{
          scale: [1, 1.15, 1],
          opacity: [0.3, 0.5, 0.3],
        }}
        transition={{
          duration: 2.4,
          ease: "easeInOut",
          repeat: Infinity,
          delay: 0.8,
        }}
      />
      
      {/* Core - Reactive to Volume */}
      <motion.div
        className="absolute rounded-full bg-ascent-blue z-10"
        style={{ width: s.core, height: s.core }}
        animate={{ scale: volScale }}
        transition={{ type: "spring", stiffness: 300, damping: 20 }}
      />
      
      {/* Core ring effect - Reactive to volume */}
      <motion.div
        className="absolute rounded-full border-2 border-ascent-blue/30 z-10"
        style={{ width: s.core + 8, height: s.core + 8 }}
        animate={{ scale: volScale * 1.2 }}
        transition={{ type: "spring", stiffness: 300, damping: 20 }}
      />
    </div>
  );
}
