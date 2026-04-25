import React, { useEffect, useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import { api } from "../api/client";
import "./Dashboard.css";

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
    return date.toLocaleDateString("en-US", { 
      month: "short", 
      day: "numeric", 
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    });
  };

  const getScoreColor = (score) => {
    if (score >= 8) return "#34c759";
    if (score >= 6) return "#ffcc00";
    return "#ff3b30";
  };

  const getAvgScore = () => {
    if (history.length === 0) return 0;
    const total = history.reduce((acc, item) => acc + (item.report?.final_score || 0), 0);
    return (total / history.length).toFixed(1);
  };

  const getSuccessRate = () => {
    if (history.length === 0) return 0;
    const passed = history.filter(item => item.report?.verdict === "PASS").length;
    return Math.round((passed / history.length) * 100);
  };

  return (
    <div className="dashboard-container">
      <nav className="dashboard-nav">
        <div className="nav-brand">
          <span className="logo-icon">🚀</span>
          <h1>Ascent AI</h1>
        </div>
        <div className="nav-user">
          <div className="user-info">
            <img src={currentUser?.photoURL || "https://ui-avatars.com/api/?name=" + (currentUser?.displayName || "User")} alt="Avatar" />
            <div className="user-text">
              <span className="user-name">{currentUser?.displayName || "Candidate"}</span>
              <span className="user-email">{currentUser?.email}</span>
            </div>
          </div>
          <button className="logout-btn" onClick={logout}>Sign Out</button>
        </div>
      </nav>

      <main className="dashboard-content">
        <header className="dashboard-header">
          <div className="header-text">
            <h1>Your Interview Hub</h1>
            <p>Review your past performances and start new sessions.</p>
          </div>
          <button className="new-interview-btn" onClick={onStartNew}>
            <span className="btn-icon">+</span>
            Start New Interview
          </button>
        </header>

        {history.length > 0 && (
          <section className="dashboard-stats-grid">
            <div className="summary-card">
              <span className="summary-label">Total Sessions</span>
              <span className="summary-value">{history.length}</span>
            </div>
            <div className="summary-card">
              <span className="summary-label">Average Score</span>
              <span className="summary-value">{getAvgScore()}<span className="unit">/10</span></span>
            </div>
            <div className="summary-card">
              <span className="summary-label">Success Rate</span>
              <span className="summary-value">{getSuccessRate()}<span className="unit">%</span></span>
            </div>
          </section>
        )}

        {loading ? (
          <div className="dashboard-loader">
            <div className="spinner"></div>
            <p>Loading your history...</p>
          </div>
        ) : error ? (
          <div className="dashboard-error-state">
            <span className="error-icon">⚠️</span>
            <h3>Oops! Something went wrong</h3>
            <p>{error}</p>
            <button onClick={() => window.location.reload()}>Try Again</button>
          </div>
        ) : history.length === 0 ? (
          <div className="empty-state">
            <div className="empty-illustration">📭</div>
            <h2>No interviews yet</h2>
            <p>You haven't completed any interviews yet. Start your first session to see analytics and feedback.</p>
            <button className="new-interview-btn" onClick={onStartNew}>Start My First Interview</button>
          </div>
        ) : (
          <div className="history-section">
            <div className="history-grid">
              {history.map((item, idx) => {
                const report = item.report || {};
                const session_id = item.session_id;
                const score = report.final_score || 0;
                
                return (
                  <div key={session_id || idx} className="history-card" onClick={() => onViewResults(session_id)}>
                    <div className="card-header">
                      <span className="role-badge">Software Engineer</span>
                      <span className="date-label">{formatDate(item.saved_at)}</span>
                    </div>
                    <div className="card-body">
                      <div className="score-circle" style={{ borderColor: getScoreColor(score) }}>
                        <span className="score-value">{score.toFixed(1)}</span>
                        <span className="score-total">/10</span>
                      </div>
                      <div className="card-stats">
                        <div className="mini-stat">
                          <span className="stat-label">Verdict</span>
                          <span className="stat-value" style={{ color: getScoreColor(score) }}>
                            {report.verdict || "N/A"}
                          </span>
                        </div>
                        <div className="mini-stat">
                          <span className="stat-label">Questions</span>
                          <span className="stat-value">{report.questions_counted || 0}</span>
                        </div>
                      </div>
                    </div>
                    <div className="card-footer">
                      <div className="skill-tags">
                        {report.strengths?.slice(0, 3).map(s => (
                          <span key={s} className="skill-tag positive">{s}</span>
                        ))}
                      </div>
                      <span className="view-link">View Detailed Report →</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
