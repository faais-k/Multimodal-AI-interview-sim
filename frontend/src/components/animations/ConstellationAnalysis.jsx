import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

export function ConstellationAnalysis({ 
  nodes = 6, 
  analyzedNodes = 3,
  processingNode = 3,
  className 
}) {
  const radius = 60;
  const center = { x: 100, y: 100 };
  
  const nodePositions = Array.from({ length: nodes }, (_, i) => {
    const angle = (i * 360 / nodes - 90) * (Math.PI / 180);
    return {
      x: center.x + Math.cos(angle) * radius,
      y: center.y + Math.sin(angle) * radius,
      label: `Q${i + 1}`,
    };
  });

  return (
    <div className={cn("relative w-[200px] h-[200px]", className)}>
      <svg className="w-full h-full" viewBox="0 0 200 200">
        {/* Connection lines */}
        {nodePositions.map((node, i) => (
          <line
            key={`line-${i}`}
            x1={center.x}
            y1={center.y}
            x2={node.x}
            y2={node.y}
            stroke="#E5E4DF"
            strokeWidth="1"
            strokeDasharray="4 2"
          />
        ))}

        {/* Central core */}
        <motion.circle
          cx={center.x}
          cy={center.y}
          r="12"
          fill="#2563EB"
          className="constellation-node"
          animate={{
            scale: [1, 1.1, 1],
          }}
          transition={{
            duration: 2,
            ease: "easeInOut",
            repeat: Infinity,
          }}
        />

        {/* Orbiting particle */}
        <motion.circle
          cx={center.x}
          cy={center.y - radius}
          r="3"
          fill="#2563EB"
          opacity="0.6"
          animate={{
            rotate: 360,
          }}
          transition={{
            duration: 8,
            ease: "linear",
            repeat: Infinity,
          }}
          style={{
            transformOrigin: `${center.x}px ${center.y}px`,
          }}
        />

        {/* Satellite nodes */}
        {nodePositions.map((node, i) => {
          const isAnalyzed = i < analyzedNodes;
          const isProcessing = i === processingNode;
          
          return (
            <motion.circle
              key={`node-${i}`}
              cx={node.x}
              cy={node.y}
              r="6"
              fill={isAnalyzed ? "#2563EB" : isProcessing ? "#D97706" : "#9B9B95"}
              className="constellation-node"
              animate={isProcessing ? {
                scale: [1, 1.3, 1],
                opacity: [0.8, 1, 0.8],
              } : {}}
              transition={isProcessing ? {
                duration: 0.8,
                ease: "easeInOut",
                repeat: Infinity,
              } : {}}
            />
          );
        })}
      </svg>

      {/* Node labels */}
      {nodePositions.map((node, i) => {
        const isAnalyzed = i < analyzedNodes;
        const isProcessing = i === processingNode;
        
        return (
          <div
            key={`label-${i}`}
            className={cn(
              "absolute text-xs transform -translate-x-1/2",
              isAnalyzed ? "text-text-muted" : isProcessing ? "text-semantic-warning font-medium" : "text-text-muted"
            )}
            style={{
              left: `${(node.x / 200) * 100}%`,
              top: `${(node.y / 200) * 100}%`,
              marginTop: node.y > center.y ? 12 : -20,
            }}
          >
            {node.label}
          </div>
        );
      })}
    </div>
  );
}
