import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ArrowRight, TrendingUp, Clock, ChevronRight, LogOut, BarChart3, Activity } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { api } from "../api/client";
import { getGuestHistory } from "@/lib/guestStorage";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn, formatScore, getScoreVariant, getVerdict } from "@/lib/utils";
import logo from "../assets/logo.jpg";

const containerVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.08 } },
};

const itemVariants = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.45, ease: "easeOut" } },
};

export default function Dashboard({ onStartNew, onViewResults }) {
  const { currentUser, isGuest, logout } = useAuth();
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchHistory = async () => {
    try {
      setLoading(true);
      setError("");

      if (isGuest) {
        const guestHistory = await getGuestHistory();
        setHistory(guestHistory || []);
        setLoading(false);
        return;
      }

      const res = await api.getUserHistory();
      if (res.status === "ok") {
        setHistory(res.history || []);
      } else {
        setError(res.detail || "Failed to load history");
      }
    } catch (err) {
      setError(err.message || "Error connecting to server. Please try again later.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, [isGuest]);

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

  const extractSkillsFromHistory = () => {
    if (history.length === 0) return [];
    const latestReport = history[0]?.report;
    if (!latestReport || !latestReport.skill_scores) return [];

    return Object.entries(latestReport.skill_scores).map(([name, score]) => ({
      name: name.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase()),
      score,
      color: score >= 7 ? "ascent-blue" : score >= 5 ? "warning" : "error",
    })).slice(0, 4);
  };

  const readinessScore = parseFloat(getAvgScore()) || 0;
  const trend = getTrend();
  const derivedSkills = extractSkillsFromHistory();

  return (
    <div className="app-page font-sans">
      <header className="app-header">
        <div className="app-header-inner justify-between">
          <div className="app-brand">
            <img src={logo} alt="Ascent Logo" className="w-8 h-8 rounded-sm object-cover" />
            <span>Ascent</span>
          </div>

          <div className="flex items-center gap-3 min-w-0">
            <div className="hidden sm:flex items-center gap-3 min-w-0">
              <div className="w-8 h-8 rounded-sm bg-surface-overlay border border-border flex items-center justify-center text-sm font-medium">
                {(currentUser?.displayName || "C").charAt(0).toUpperCase()}
              </div>
              <span className="text-sm font-medium text-text-secondary truncate max-w-[180px]">{currentUser?.displayName || "Candidate"}</span>
            </div>
            <Button variant="outline" onClick={logout} className="h-9">
              <LogOut size={16} /> <span className="hidden sm:inline">Sign Out</span>
            </Button>
          </div>
        </div>
      </header>

      <main className="app-container">
        <motion.div variants={containerVariants} initial="hidden" animate="visible">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-10">
            <div>
              <div className="app-kicker mb-4">
                <span className="w-2 h-2 bg-ascent-blue rounded-full" />
                Dashboard
              </div>
              <h1 className="text-2xl sm:text-3xl font-semibold tracking-normal mb-2">Welcome back</h1>
              <p className="text-text-secondary">Track readiness and review past interview performance.</p>
            </div>
            <Button onClick={onStartNew} className="w-full md:w-auto" size="lg">
              Start New Interview <ArrowRight size={16} />
            </Button>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8">
            <div className="lg:col-span-8 space-y-8 min-w-0">
              <motion.div variants={itemVariants}>
                <Card className="overflow-hidden">
                  <div className="p-6 sm:p-8">
                    <div className="flex flex-col sm:flex-row sm:items-end justify-between mb-8 gap-4">
                      <div>
                        <p className="text-text-secondary font-medium mb-2 flex items-center gap-2">
                          <Activity size={16} /> Current Readiness Index
                        </p>
                        <div className="flex items-baseline gap-4">
                          <span className="font-semibold text-5xl sm:text-6xl tracking-normal text-text-primary">
                            {formatScore(readinessScore)}
                          </span>
                          {trend && (
                            <span className={cn(
                              "text-sm font-medium flex items-center gap-1.5 px-2.5 py-1 rounded-sm",
                              trend.up ? "bg-ascent-blue-subtle text-ascent-blue" : "bg-semantic-error-bg text-semantic-error"
                            )}>
                              <TrendingUp size={14} className={trend.up ? "" : "rotate-180"} />
                              {trend.up ? "+" : ""}{trend.diff} pts
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="relative h-2 bg-surface-overlay rounded-sm overflow-hidden mb-3">
                      <motion.div
                        className="absolute inset-y-0 left-0 bg-ascent-blue rounded-sm"
                        initial={{ width: 0 }}
                        animate={{ width: `${(readinessScore / 10) * 100}%` }}
                        transition={{ duration: 1.2, ease: "easeOut" }}
                      />
                    </div>
                    <div className="flex justify-between text-xs font-medium text-text-muted uppercase tracking-wide">
                      <span>Novice</span>
                      <span>Ready</span>
                      <span>Expert</span>
                    </div>
                  </div>
                </Card>
              </motion.div>

              <motion.div variants={itemVariants}>
                <div className="flex items-center justify-between mb-5">
                  <h2 className="text-xl font-semibold flex items-center gap-2">
                    <Clock size={20} className="text-ascent-blue" /> Session History
                  </h2>
                </div>

                {loading ? (
                  <div className="space-y-4">
                    {[1, 2, 3].map((i) => (
                      <div key={i} className="h-24 bg-white rounded-md border border-border animate-pulse" />
                    ))}
                  </div>
                ) : error ? (
                  <Card className="p-8 text-center border-semantic-error/20 bg-semantic-error-bg/30">
                    <p className="text-semantic-error mb-4">{error}</p>
                    <Button variant="outline" onClick={fetchHistory} disabled={loading}>
                      {loading ? "Retrying..." : "Retry"}
                    </Button>
                  </Card>
                ) : history.length === 0 ? (
                  <Card className="p-8 sm:p-12 text-center border-dashed">
                    <div className="w-14 h-14 bg-surface-overlay rounded-sm flex items-center justify-center mx-auto mb-4 text-text-muted">
                      <BarChart3 size={28} />
                    </div>
                    <p className="text-text-secondary mb-6 max-w-sm mx-auto">No sessions yet. Your history and skill breakdown will appear after your first interview.</p>
                    <Button onClick={onStartNew}>Start First Interview</Button>
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
                          transition={{ delay: idx * 0.06 }}
                        >
                          <Card
                            className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 cursor-pointer group"
                            onClick={() => onViewResults(item.session_id)}
                          >
                            <div className="flex items-center gap-4 min-w-0">
                              <div className={cn(
                                "w-14 h-14 rounded-sm flex items-center justify-center border flex-shrink-0",
                                variant === "high" ? "bg-ascent-blue-subtle border-ascent-blue/20 text-ascent-blue" :
                                variant === "mid" ? "bg-semantic-warning-bg border-semantic-warning/20 text-semantic-warning" :
                                "bg-semantic-error-bg border-semantic-error/20 text-semantic-error"
                              )}>
                                <span className="font-semibold text-xl">{formatScore(score)}</span>
                              </div>
                              <div className="min-w-0">
                                <p className="font-semibold text-text-primary mb-1 group-hover:text-ascent-blue transition-colors">Technical Interview</p>
                                <p className="text-sm text-text-muted truncate">
                                  {formatDate(item.saved_at)} - {report.questions_counted || 0} questions
                                </p>
                              </div>
                            </div>
                            <div className="flex items-center justify-between sm:justify-end gap-4 w-full sm:w-auto">
                              <Badge
                                className={cn(
                                  "px-3 py-1 font-medium bg-transparent border",
                                  variant === "high" ? "text-ascent-blue border-ascent-blue/30" :
                                  variant === "mid" ? "text-semantic-warning border-semantic-warning/30" :
                                  "text-semantic-error border-semantic-error/30"
                                )}
                              >
                                {getVerdict(score)}
                              </Badge>
                              <div className="w-8 h-8 rounded-sm bg-surface-overlay flex items-center justify-center group-hover:bg-ascent-blue-subtle transition-colors">
                                <ChevronRight size={16} className="text-text-secondary group-hover:text-ascent-blue group-hover:translate-x-0.5 transition-all" />
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

            <div className="lg:col-span-4 min-w-0">
              <motion.div variants={itemVariants} className="lg:sticky lg:top-24">
                <h2 className="text-xl font-semibold mb-5 flex items-center gap-2">
                  <BarChart3 size={20} className="text-ascent-blue" /> Skill Assessment
                </h2>

                <Card className="p-6 relative overflow-hidden">
                  {history.length === 0 ? (
                    <div className="py-8 text-center">
                      <div className="w-12 h-12 rounded-sm border border-border flex items-center justify-center mx-auto mb-3 bg-surface-overlay">
                        <Activity size={20} className="text-text-muted" />
                      </div>
                      <p className="text-sm text-text-secondary">Complete an interview to see your skill breakdown.</p>
                    </div>
                  ) : derivedSkills.length > 0 ? (
                    <div className="space-y-6">
                      {derivedSkills.map((skill, idx) => (
                        <div key={skill.name}>
                          <div className="flex justify-between text-sm mb-3 gap-3">
                            <span className="font-medium text-text-primary truncate">{skill.name}</span>
                            <span className="font-mono text-text-secondary">{skill.score.toFixed(1)}/10</span>
                          </div>
                          <div className="h-2 bg-surface-overlay rounded-sm overflow-hidden">
                            <motion.div
                              className={cn(
                                "h-full rounded-sm",
                                skill.color === "ascent-blue" ? "bg-ascent-blue" :
                                skill.color === "warning" ? "bg-semantic-warning" :
                                "bg-semantic-error"
                              )}
                              initial={{ width: 0 }}
                              animate={{ width: `${(skill.score / 10) * 100}%` }}
                              transition={{ delay: 0.2 + idx * 0.08, duration: 0.8, ease: "easeOut" }}
                            />
                          </div>
                        </div>
                      ))}
                      <div className="pt-5 border-t border-border">
                        <p className="text-sm text-text-secondary leading-relaxed">
                          Scores reflect your most recent performance across technical and communication dimensions.
                        </p>
                      </div>
                    </div>
                  ) : (
                    <div className="py-8 text-center text-sm text-text-secondary">
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
