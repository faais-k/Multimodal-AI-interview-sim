import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ArrowRight, TrendingUp, Clock, ChevronRight } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { api } from "../api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { cn, formatScore, getScoreVariant, getVerdict, getVerdictColor } from "@/lib/utils";

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.08,
    },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 12 },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.6,
      ease: [0.16, 1, 0.3, 1],
    },
  },
};

export default function Dashboard({ onStartNew, onViewResults }) {
  const { currentUser, logout } = useAuth();
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        setLoading(true);
        const res = await api.getUserHistory();
        if (res.status === "ok") {
          setHistory(res.history || []);
        } else {
          setError(res.detail || "Failed to load history");
        }
      } catch (err) {
        setError("Error connecting to server. Please try again later.");
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchHistory();
  }, []);

  const formatDate = (dateStr) => {
    if (!dateStr) return "Unknown date";
    const date = new Date(dateStr);
    const now = new Date();
    const diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24));
    
    if (diffDays === 0) return "Today";
    if (diffDays === 1) return "Yesterday";
    if (diffDays < 7) return `${diffDays} days ago`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
    
    return date.toLocaleDateString("en-US", { 
      month: "short", 
      day: "numeric"
    });
  };

  const getAvgScore = () => {
    if (history.length === 0) return 0;
    const total = history.reduce((acc, item) => acc + (item.report?.final_score || 0), 0);
    return (total / history.length).toFixed(1);
  };

  const getTrend = () => {
    if (history.length < 2) return null;
    const recent = history[0].report?.final_score || 0;
    const previous = history[1].report?.final_score || 0;
    const diff = recent - previous;
    return { diff: diff.toFixed(1), up: diff > 0 };
  };

  const readinessScore = parseFloat(getAvgScore()) || 0;
  const trend = getTrend();

  // Skill trajectory mock data (would come from API in real implementation)
  const skills = [
    { name: "System Design", score: 7.8, change: +2.1, color: "veridian" },
    { name: "Code Architecture", score: 8.1, change: +1.8, color: "veridian" },
    { name: "Communication", score: 6.2, change: +0.4, color: "warning" },
    { name: "Problem Solving", score: 7.5, change: +1.2, color: "veridian" },
  ];

  return (
    <div className="min-h-screen bg-surface-base">
      {/* Header */}
      <header className="fixed top-0 left-0 right-0 bg-surface-base/90 backdrop-blur-sm border-b border-border z-50">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <svg width="28" height="28" viewBox="0 0 36 36" fill="none">
              <rect width="36" height="36" rx="6" fill="#059669"/>
              <path d="M8 26 L14 18 L18 22 L22 14 L28 26" stroke="white" strokeWidth="2.5" strokeLinejoin="round" fill="none"/>
            </svg>
            <span className="font-semibold text-lg tracking-tight">Ascent</span>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-text-secondary">{currentUser?.displayName || "Candidate"}</span>
            <div className="w-8 h-8 bg-surface-overlay rounded-sm flex items-center justify-center text-sm font-medium">
              {(currentUser?.displayName || "C").charAt(0).toUpperCase()}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="pt-24 pb-16 px-6 max-w-6xl mx-auto">
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="visible"
        >
          {/* Hero Metric */}
          <motion.section variants={itemVariants} className="mb-12">
            <div className="flex items-end justify-between mb-6">
              <div>
                <p className="text-sm text-text-secondary mb-1 font-medium">Current Readiness Index</p>
                <div className="flex items-baseline gap-3">
                  <span className="font-mono font-bold text-5xl text-text-primary">{formatScore(readinessScore)}</span>
                  {trend && (
                    <span className={cn(
                      "text-sm font-medium flex items-center gap-1",
                      trend.up ? "text-veridian" : "text-semantic-error"
                    )}>
                      {trend.up ? <TrendingUp size={14} /> : <TrendingUp size={14} className="rotate-180" />}
                      {trend.up ? "+" : ""}{trend.diff} from last session
                    </span>
                  )}
                </div>
              </div>
              <Button onClick={onStartNew} className="flex items-center gap-2">
                <ArrowRight size={16} />
                New Session
              </Button>
            </div>
            
            {/* Progress bar */}
            <div className="h-2 bg-surface-overlay rounded-sm overflow-hidden">
              <motion.div 
                className="h-full bg-veridian rounded-sm"
                initial={{ width: 0 }}
                animate={{ width: `${(readinessScore / 10) * 100}%` }}
                transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}
              />
            </div>
            <div className="flex justify-between mt-2 text-xs text-text-muted font-mono">
              <span>Novice</span>
              <span>Interview Ready</span>
              <span>Expert</span>
            </div>
          </motion.section>

          {/* Two Column Layout */}
          <div className="grid grid-cols-12 gap-6">
            
            {/* Session History (70%) */}
            <motion.section variants={itemVariants} className="col-span-8">
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-semibold text-lg">Session History</h2>
                {history.length > 0 && (
                  <button className="text-sm text-text-secondary hover:text-text-primary transition-colors">
                    View All
                  </button>
                )}
              </div>
              
              {loading ? (
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="h-24 bg-white border border-border rounded-md animate-pulse" />
                  ))}
                </div>
              ) : error ? (
                <Card className="p-6 text-center">
                  <p className="text-semantic-error mb-2">{error}</p>
                  <Button variant="outline" onClick={() => window.location.reload()}>Retry</Button>
                </Card>
              ) : history.length === 0 ? (
                <Card className="p-8 text-center">
                  <p className="text-text-secondary mb-4">No sessions yet. Start your first interview to begin tracking your progress.</p>
                  <Button onClick={onStartNew}>Start First Interview</Button>
                </Card>
              ) : (
                <div className="space-y-3">
                  {history.slice(0, 5).map((item, idx) => {
                    const report = item.report || {};
                    const score = report.final_score || 0;
                    const variant = getScoreVariant(score);
                    
                    return (
                      <motion.div
                        key={item.session_id || idx}
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: idx * 0.1 }}
                      >
                        <Card 
                          className="p-5 flex items-center justify-between cursor-pointer"
                          onClick={() => onViewResults(item.session_id)}
                        >
                          <div className="flex items-center gap-4">
                            <div className={cn(
                              "w-12 h-12 rounded-sm flex items-center justify-center",
                              variant === 'high' ? "bg-veridian-subtle" : 
                              variant === 'mid' ? "bg-semantic-warning-bg" : "bg-semantic-error-bg"
                            )}>
                              <span className={cn(
                                "font-mono font-bold text-xl",
                                variant === 'high' ? "text-veridian" : 
                                variant === 'mid' ? "text-semantic-warning" : "text-semantic-error"
                              )}>
                                {formatScore(score)}
                              </span>
                            </div>
                            <div>
                              <p className="font-medium text-text-primary">Senior Full Stack Interview</p>
                              <p className="text-sm text-text-secondary flex items-center gap-2">
                                <Clock size={12} />
                                {formatDate(item.saved_at)} • {report.questions_counted || 0} questions
                              </p>
                            </div>
                          </div>
                          <div className="flex items-center gap-3">
                            <Badge variant={variant === 'high' ? 'success' : variant === 'mid' ? 'warning' : 'error'}>
                              {getVerdict(score)}
                            </Badge>
                            <ChevronRight size={16} className="text-text-muted" />
                          </div>
                        </Card>
                      </motion.div>
                    );
                  })}
                </div>
              )}
            </motion.section>

            {/* Skill Trajectory (30%) */}
            <motion.section variants={itemVariants} className="col-span-4">
              <h2 className="font-semibold text-lg mb-4">Skill Trajectory</h2>
              <Card className="p-5">
                <div className="space-y-4">
                  {skills.map((skill, idx) => (
                    <div key={skill.name}>
                      <div className="flex justify-between text-sm mb-2">
                        <span className="text-text-secondary">{skill.name}</span>
                        <div className="flex items-center gap-2">
                          <span className={cn(
                            "font-mono font-medium",
                            skill.color === 'veridian' ? "text-veridian" : "text-semantic-warning"
                          )}>
                            {skill.change > 0 ? "+" : ""}{skill.change}
                          </span>
                        </div>
                      </div>
                      <div className="h-1.5 bg-surface-overlay rounded-sm overflow-hidden">
                        <motion.div 
                          className={cn(
                            "h-full rounded-sm",
                            skill.color === 'veridian' ? "bg-veridian" : "bg-semantic-warning"
                          )}
                          initial={{ width: 0 }}
                          animate={{ width: `${skill.score * 10}%` }}
                          transition={{ delay: 0.5 + idx * 0.1, duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
                
                <div className="mt-6 pt-5 border-t border-border">
                  <p className="text-xs text-text-secondary leading-relaxed">
                    Focus area: <span className="text-semantic-warning font-medium">Communication clarity</span> 
                    — practice structured responses using the STAR method.
                  </p>
                </div>
              </Card>
            </motion.section>
          </div>
        </motion.div>
      </main>
    </div>
  );
}

