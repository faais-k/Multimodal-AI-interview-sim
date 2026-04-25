import React, { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowRight, TrendingUp, Clock, ChevronRight, LogOut, BarChart3, Activity } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { api } from "../api/client";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn, formatScore, getScoreVariant, getVerdict } from "@/lib/utils";

const containerVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.1 } },
};

const itemVariants = {
  hidden: { opacity: 0, y: 15 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: "easeOut" } },
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
    
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
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

  // Derive skills from actual history if available
  const extractSkillsFromHistory = () => {
    if (history.length === 0) return [];
    const latestReport = history[0]?.report;
    if (!latestReport || !latestReport.skill_scores) return [];
    
    return Object.entries(latestReport.skill_scores).map(([name, score]) => ({
      name: name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
      score: score,
      color: score >= 7 ? "veridian" : score >= 5 ? "warning" : "error"
    })).slice(0, 4); // Take top 4
  };

  const readinessScore = parseFloat(getAvgScore()) || 0;
  const trend = getTrend();
  const derivedSkills = extractSkillsFromHistory();

  return (
    <div className="min-h-screen bg-[#0a0a0e] text-white selection:bg-veridian/30 font-sans">
      {/* Background Gradients */}
      <div className="fixed inset-0 z-0 pointer-events-none">
        <div className="absolute top-[-20%] left-[-10%] w-[50%] h-[50%] rounded-full bg-veridian/5 blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-indigo-900/10 blur-[150px]" />
        <div className="absolute inset-0 bg-[url('/noise.png')] opacity-10 mix-blend-overlay" />
      </div>

      {/* Header */}
      <header className="relative z-50 border-b border-white/5 bg-[#0a0a0e]/80 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-veridian to-teal-600 rounded-xl flex items-center justify-center shadow-lg shadow-veridian/20">
              <svg width="24" height="24" viewBox="0 0 36 36" fill="none">
                <path d="M8 26 L14 18 L18 22 L22 14 L28 26" stroke="white" strokeWidth="2.5" strokeLinejoin="round" fill="none"/>
              </svg>
            </div>
            <span className="font-bold text-xl tracking-tight text-white">Ascent</span>
          </div>
          <div className="flex items-center gap-4">
            <div className="hidden sm:flex items-center gap-3 mr-4">
              <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center text-sm font-medium border border-white/20">
                {(currentUser?.displayName || "C").charAt(0).toUpperCase()}
              </div>
              <span className="text-sm font-medium text-white/80">{currentUser?.displayName || "Candidate"}</span>
            </div>
            <Button 
              variant="outline" 
              onClick={logout} 
              className="border-white/10 hover:bg-white/5 text-white/80 hover:text-white transition-colors h-10"
            >
              <LogOut size={16} className="mr-2 opacity-70" /> Sign Out
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="relative z-10 pt-16 pb-24 px-6 max-w-7xl mx-auto">
        <motion.div variants={containerVariants} initial="hidden" animate="visible">
          
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-12">
            <div>
              <h1 className="text-3xl font-bold tracking-tight mb-2">Welcome back</h1>
              <p className="text-white/50">Track your interview readiness and review past performances.</p>
            </div>
            <Button 
              onClick={onStartNew} 
              className="bg-gradient-to-r from-veridian to-teal-500 hover:from-veridian/90 hover:to-teal-500/90 text-white rounded-full px-8 h-12 shadow-lg shadow-veridian/20 hover:scale-105 transition-all w-full md:w-auto"
            >
              Start New Interview <ArrowRight size={16} className="ml-2" />
            </Button>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            
            {/* Left Column: Readiness & History */}
            <div className="lg:col-span-8 space-y-8">
              
              {/* Readiness Card */}
              <motion.div variants={itemVariants}>
                <Card className="bg-white/[0.02] border-white/5 overflow-hidden relative">
                  <div className="absolute top-0 right-0 w-64 h-64 bg-veridian/10 rounded-full blur-[80px] -mr-32 -mt-32 pointer-events-none" />
                  <div className="p-8 relative z-10">
                    <div className="flex flex-col sm:flex-row sm:items-end justify-between mb-8 gap-4">
                      <div>
                        <p className="text-white/50 font-medium mb-2 flex items-center gap-2">
                          <Activity size={16} /> Current Readiness Index
                        </p>
                        <div className="flex items-baseline gap-4">
                          <span className="font-bold text-6xl tracking-tighter text-white">
                            {formatScore(readinessScore)}
                          </span>
                          {trend && (
                            <span className={cn(
                              "text-sm font-medium flex items-center gap-1.5 px-2.5 py-1 rounded-full",
                              trend.up ? "bg-veridian/10 text-veridian" : "bg-red-500/10 text-red-400"
                            )}>
                              <TrendingUp size={14} className={trend.up ? "" : "rotate-180"} />
                              {trend.up ? "+" : ""}{trend.diff} pts
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    
                    {/* Progress bar */}
                    <div className="relative h-3 bg-white/5 rounded-full overflow-hidden mb-3 border border-white/5">
                      <motion.div 
                        className="absolute inset-y-0 left-0 bg-gradient-to-r from-teal-500 to-veridian rounded-full"
                        initial={{ width: 0 }}
                        animate={{ width: `${(readinessScore / 10) * 100}%` }}
                        transition={{ duration: 1.5, ease: "easeOut" }}
                      />
                    </div>
                    <div className="flex justify-between text-xs font-medium text-white/40 uppercase tracking-wider">
                      <span>Novice</span>
                      <span>Ready</span>
                      <span>Expert</span>
                    </div>
                  </div>
                </Card>
              </motion.div>

              {/* History Section */}
              <motion.div variants={itemVariants}>
                <div className="flex items-center justify-between mb-6">
                  <h2 className="text-xl font-semibold flex items-center gap-2">
                    <Clock size={20} className="text-veridian" /> Session History
                  </h2>
                </div>
                
                {loading ? (
                  <div className="space-y-4">
                    {[1, 2, 3].map((i) => (
                      <div key={i} className="h-24 bg-white/5 rounded-2xl border border-white/5 animate-pulse" />
                    ))}
                  </div>
                ) : error ? (
                  <Card className="p-8 text-center bg-red-500/5 border-red-500/20">
                    <p className="text-red-400 mb-4">{error}</p>
                    <Button variant="outline" className="border-red-500/30 text-red-400 hover:bg-red-500/10" onClick={() => window.location.reload()}>Retry</Button>
                  </Card>
                ) : history.length === 0 ? (
                  <Card className="p-12 text-center bg-white/[0.02] border-white/5 border-dashed">
                    <div className="w-16 h-16 bg-white/5 rounded-full flex items-center justify-center mx-auto mb-4 text-white/20">
                      <BarChart3 size={32} />
                    </div>
                    <p className="text-white/60 mb-6 max-w-sm mx-auto">No sessions yet. Your performance history and skill breakdown will appear here after your first interview.</p>
                    <Button onClick={onStartNew} className="bg-white text-black hover:bg-white/90 rounded-full">
                      Start First Interview
                    </Button>
                  </Card>
                ) : (
                  <div className="space-y-4">
                    {history.slice(0, 5).map((item, idx) => {
                      const report = item.report || {};
                      const score = report.final_score || 0;
                      const variant = getScoreVariant(score);
                      
                      return (
                        <motion.div
                          key={item.session_id || idx}
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: idx * 0.1 }}
                        >
                          <Card 
                            className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 cursor-pointer bg-white/[0.02] border-white/5 hover:bg-white/[0.05] hover:border-white/10 transition-all group rounded-2xl"
                            onClick={() => onViewResults(item.session_id)}
                          >
                            <div className="flex items-center gap-5">
                              <div className={cn(
                                "w-14 h-14 rounded-xl flex items-center justify-center border shadow-inner",
                                variant === 'high' ? "bg-veridian/10 border-veridian/20 text-veridian" : 
                                variant === 'mid' ? "bg-yellow-500/10 border-yellow-500/20 text-yellow-500" : 
                                "bg-red-500/10 border-red-500/20 text-red-500"
                              )}>
                                <span className="font-bold text-xl">{formatScore(score)}</span>
                              </div>
                              <div>
                                <p className="font-semibold text-white/90 mb-1 group-hover:text-veridian transition-colors">Technical Interview</p>
                                <p className="text-sm text-white/40 flex items-center gap-2">
                                  {formatDate(item.saved_at)} • {report.questions_counted || 0} questions
                                </p>
                              </div>
                            </div>
                            <div className="flex items-center justify-between sm:justify-end gap-4 w-full sm:w-auto mt-2 sm:mt-0">
                              <Badge 
                                className={cn(
                                  "px-3 py-1 font-medium bg-transparent border",
                                  variant === 'high' ? "text-veridian border-veridian/30" : 
                                  variant === 'mid' ? "text-yellow-500 border-yellow-500/30" : 
                                  "text-red-400 border-red-400/30"
                                )}
                              >
                                {getVerdict(score)}
                              </Badge>
                              <div className="w-8 h-8 rounded-full bg-white/5 flex items-center justify-center group-hover:bg-white/10 transition-colors">
                                <ChevronRight size={16} className="text-white/60 group-hover:text-white group-hover:translate-x-0.5 transition-all" />
                              </div>
                            </div>
                          </Card>
                        </motion.div>
                      );
                    })}
                  </div>
                )}
              </motion.div>
            </div>

            {/* Right Column: Skills */}
            <div className="lg:col-span-4">
              <motion.div variants={itemVariants} className="sticky top-28">
                <h2 className="text-xl font-semibold mb-6 flex items-center gap-2">
                  <BarChart3 size={20} className="text-veridian" /> Skill Assessment
                </h2>
                
                <Card className="p-6 bg-white/[0.02] border-white/5 rounded-2xl relative overflow-hidden">
                  <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-veridian to-teal-500 opacity-50" />
                  
                  {history.length === 0 ? (
                    <div className="py-8 text-center">
                      <div className="w-12 h-12 rounded-full border border-white/10 flex items-center justify-center mx-auto mb-3 opacity-50">
                        <Activity size={20} className="text-white/40" />
                      </div>
                      <p className="text-sm text-white/50">Complete an interview to see your skill breakdown.</p>
                    </div>
                  ) : derivedSkills.length > 0 ? (
                    <div className="space-y-6">
                      {derivedSkills.map((skill, idx) => (
                        <div key={skill.name}>
                          <div className="flex justify-between text-sm mb-3">
                            <span className="font-medium text-white/80">{skill.name}</span>
                            <span className="font-mono text-white/60">{skill.score.toFixed(1)}/10</span>
                          </div>
                          <div className="h-2 bg-white/5 rounded-full overflow-hidden border border-white/5">
                            <motion.div 
                              className={cn(
                                "h-full rounded-full",
                                skill.color === 'veridian' ? "bg-veridian shadow-[0_0_10px_rgba(20,184,166,0.5)]" : 
                                skill.color === 'warning' ? "bg-yellow-500 shadow-[0_0_10px_rgba(234,179,8,0.5)]" : 
                                "bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.5)]"
                              )}
                              initial={{ width: 0 }}
                              animate={{ width: `${(skill.score / 10) * 100}%` }}
                              transition={{ delay: 0.3 + idx * 0.1, duration: 1, ease: "easeOut" }}
                            />
                          </div>
                        </div>
                      ))}
                      <div className="mt-8 pt-6 border-t border-white/5">
                        <p className="text-sm text-white/50 leading-relaxed">
                          Scores based on your most recent performance. Keep practicing to improve specific technical and soft skills.
                        </p>
                      </div>
                    </div>
                  ) : (
                    <div className="py-8 text-center text-sm text-white/50">
                      No specific skills extracted from your recent session.
                    </div>
                  )}
                </Card>
              </motion.div>
            </div>
            
          </div>
        </motion.div>
      </main>
    </div>
  );
}

