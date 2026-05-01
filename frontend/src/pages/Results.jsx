import { useState } from "react";
import "./Results.css";

/* ── helpers ── */
const fmt  = v => v != null ? v.toFixed(1) : "—";
const fmtP = v => v != null ? `${Math.round(v * 100)}%` : "—";

const scoreColor = s =>
  s == null ? "var(--primary)"
  : s >= 7.5 ? "var(--success)"
  : s >= 6.0 ? "var(--warning)"
  : "var(--danger)";

const scoreChipClass = s =>
  s == null ? "chip-stone"
  : s >= 7.5 ? "chip-blue"
  : s >= 6.0 ? "chip-warning"
  : "chip-red";

const Logo = () => (
  <img src="/src/assets/logo.jpg" alt="Ascent Logo" className="w-7 h-7 rounded-sm object-cover" />
);

const VerdictIcon = ({ verdict, size = 28 }) => {
  const p = { viewBox:"0 0 24 24", fill:"none", stroke:"currentColor", strokeWidth:"2", strokeLinecap:"round", strokeLinejoin:"round", width:size, height:size };
  if (verdict === "PASS")       return <svg {...p}><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>;
  if (verdict === "FAIL")       return <svg {...p}><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>;
  if (verdict === "BORDERLINE") return <svg {...p}><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>;
  return <svg {...p}><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>;
};

const ChevronIcon = ({ open }) => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
    style={{ transform: open ? "rotate(180deg)" : "rotate(0)", transition: "transform 0.2s ease" }}>
    <polyline points="6 9 12 15 18 9"/>
  </svg>
);

function Accordion({ title, defaultOpen = false, children, badge, priority }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className={`results-accordion${open?" open":""}`}>
      <button className="results-accordion__header" onClick={() => setOpen(o => !o)} aria-expanded={open}>
        <span className="results-accordion__title">{title}</span>
        <div className="results-accordion__meta">
          {badge && <span className={`chip chip-${priority==="high"?"red":priority==="medium"?"warning":"stone"}`}>{badge}</span>}
          <ChevronIcon open={open} />
        </div>
      </button>
      {open && <div className="results-accordion__body animate-in">{children}</div>}
    </div>
  );
}

function ScoreBar({ value, max = 10, color }) {
  const pct = Math.min(100, ((value ?? 0) / max) * 100);
  return (
    <div className="score-bar">
      <div className="score-bar__track">
        <div className="score-bar__fill" style={{ width: `${pct}%`, background: color || "var(--ascent-blue)" }} />
      </div>
    </div>
  );
}

export default function Results({ report, caps, onRestart }) {
  if (!report) {
    return (
      <div className="min-h-screen bg-surface-base flex items-center justify-center p-6">
        <div className="text-center max-w-sm">
          <h2 className="text-xl font-semibold mb-2 text-text-primary">No Report Available</h2>
          <p className="text-sm text-text-secondary mb-6">
            Interview results could not be loaded. This can happen if you refreshed the page or navigated here directly.
          </p>
          <button className="btn-primary px-6 py-2" onClick={onRestart}>
            Start New Interview
          </button>
        </div>
      </div>
    );
  }

  const verdict   = report.decision || report.verdict || "BORDERLINE";
  const score     = report.final_score ?? 0;
  const candidate = report.candidate || {};
  const skills    = Object.entries(report.skills_analysis || {});
  const fillers   = report.filler_word_summary || {};
  const posture   = report.posture_summary || {};
  const quality   = report.answer_quality || {};
  const readiness = report.readiness_index || {};
  const reviewer  = report.reviewer_summary || {};
  const viols     = report.violations_summary || {};
  const questions = report.question_breakdown || [];
  const strengths = report.strengths || [];
  const weakAreas = report.weak_areas || [];
  const notAssessed = report.not_assessed || [];
  const actionPlan  = reviewer.recommendation || report.suggestions || [];

  // Sort questions by score ascending (weakest first)
  const sortedQs = [...questions].sort((a, b) => {
    if (a.skipped && !b.skipped) return -1;
    if (!a.skipped && b.skipped) return 1;
    return (a.score ?? 10) - (b.score ?? 10);
  });

  const verdictColors = {
    PASS:       { bg:"var(--success-glow)", border:"var(--success)", text:"var(--success-dark)" },
    FAIL:       { bg:"var(--danger-glow)",  border:"var(--danger)",  text:"var(--danger-dark)"  },
    BORDERLINE: { bg:"var(--warning-glow)", border:"var(--warning)", text:"var(--warning-dark)" },
  };
  const vc = verdictColors[verdict] || verdictColors.BORDERLINE;

  return (
    <div className="results-shell">
      {/* Header bar */}
      <header className="results-bar">
        <div className="results-bar__brand">
          <Logo />
          <span>Ascent</span>
        </div>
        <div className="results-bar__meta">
          {candidate.name && <span className="results-bar__name">{candidate.name}</span>}
          {candidate.job_role && <span className="chip chip-stone">{candidate.job_role}</span>}
          {candidate.company  && <span className="chip chip-stone">{candidate.company}</span>}
          {candidate.expertise_level && <span className="chip chip-blue" style={{textTransform:"capitalize"}}>{candidate.expertise_level}</span>}
        </div>
        <button className="btn-secondary results-bar__restart" onClick={onRestart}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="1 4 1 10 7 10"/><polyline points="23 20 23 14 17 14"/><path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15"/></svg>
          New Interview
        </button>
      </header>

      <div className="results-body">
        {/* ── Hero score row ── */}
        <div className="results-hero">
          {/* Verdict */}
          <div className="verdict-card" style={{background: vc.bg, borderColor: vc.border}}>
            <div style={{color: vc.text}}><VerdictIcon verdict={verdict} size={32}/></div>
            <div className="verdict-card__label" style={{color: vc.text}}>{verdict}</div>
            <div className="verdict-card__sub">{readiness.level || report.readiness_level || ""}</div>
            <div className="verdict-card__conf">Confidence: {fmtP(report.confidence)}</div>
          </div>

          {/* Score */}
          <div className="score-card">
            <div className="score-card__label">Overall Score</div>
            <div className="score-card__value" style={{color: scoreColor(score)}}>{fmt(score)}<span className="score-card__max">/10</span></div>
            <ScoreBar value={score} color={scoreColor(score)} />
            <div className="score-card__threshold">Pass threshold: {report.pass_threshold ?? 6.0}</div>
          </div>

          {/* Quick stats */}
          <div className="stats-grid">
            {[
              {l:"Questions",    v: report.questions_counted ?? "—"},
              {l:"Coverage",     v: fmtP(report.coverage_pct)},
              {l:"Avg Similarity",v: quality.avg_similarity != null ? quality.avg_similarity.toFixed(2) : "—"},
              {l:"Consistency",  v: quality.consistency || "—"},
              {l:"Posture Good", v: posture.good_posture_pct != null ? `${posture.good_posture_pct}%` : "—"},
              {l:"Violations",   v: viols.total ?? 0},
            ].map(s => (
              <div className="stat-box" key={s.l}>
                <div className="stat-box__val">{s.v}</div>
                <div className="stat-box__label">{s.l}</div>
              </div>
            ))}
          </div>
        </div>

        {/* ── Accordion sections ── */}
        <div className="results-sections">

          {/* ── Inference Telemetry ── */}
          <div className="telemetry-card card">
            <h3 className="telemetry-card__title">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><rect x="4" y="4" width="16" height="16" rx="2" ry="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/><line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/><line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/></svg>
              Evaluation Telemetry
            </h3>
            <div className="telemetry-grid">
              <div className="telemetry-item">
                <span className="telemetry-label">Compute Engine</span>
                <span className="telemetry-value" style={{textTransform:"uppercase"}}>{caps.mode || "CPU (Serverless)"}</span>
              </div>
              <div className="telemetry-item">
                <span className="telemetry-label">LLM Evaluator</span>
                <span className="telemetry-value">{caps.llmMode === "local" ? "Local GPU Inference" : caps.llmMode === "api" ? "Serverless API (Qwen)" : "Cosine Fallback"}</span>
              </div>
              <div className="telemetry-item">
                <span className="telemetry-label">Speech Recognition</span>
                <span className="telemetry-value">{caps.audioEnabled ? "Active (Whisper)" : "Disabled"}</span>
              </div>
            </div>
          </div>

          {/* Decision reasons */}
          {(report.decision_reasons || []).length > 0 && (
            <div className="card">
              <div className="perf-col__title" style={{marginBottom: "0.75rem"}}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
                Key Factors for Decision
              </div>
              <ul className="reason-list" style={{paddingTop: 0}}>
                {(report.decision_reasons || []).map((r, i) => (
                  <li key={i} className="reason-list__item">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
                    {r}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Strengths & weak areas */}
          {(strengths.length + weakAreas.length) > 0 && (
            <Accordion title="Skill Performance" defaultOpen={true}>
              {strengths.length > 0 && (
                <div style={{marginBottom: "1.5rem"}}>
                  <div className="perf-col__title" style={{marginBottom: "0.75rem"}}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                    Strengths
                  </div>
                  <div style={{display: "flex", flexWrap: "wrap", gap: "0.5rem"}}>
                    {strengths.map((s, i) => <span key={i} className="chip chip-success" style={{display: "inline-block"}}>{s}</span>)}
                  </div>
                </div>
              )}
              {weakAreas.length > 0 && (
                <div style={{marginBottom: "1.5rem"}}>
                  <div className="perf-col__title" style={{marginBottom: "0.75rem"}}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
                    Areas to Improve
                  </div>
                  <div style={{display: "flex", flexWrap: "wrap", gap: "0.5rem"}}>
                    {weakAreas.map((s, i) => <span key={i} className="chip chip-warn" style={{display: "inline-block"}}>{s}</span>)}
                  </div>
                </div>
              )}
              {notAssessed.length > 0 && (
                <details style={{marginTop: "0", paddingTop: "0", borderTop: "1px solid var(--color-border)"}}>
                  <summary style={{cursor: "pointer", fontWeight: "500", color: "var(--color-text-secondary)"}}>
                    Not Assessed on Resume ({notAssessed.length})
                  </summary>
                  <div style={{display: "flex", flexWrap: "wrap", gap: "0.5rem", marginTop: "0.75rem"}}>
                    {notAssessed.map((s, i) => <span key={i} className="chip" style={{display: "inline-block"}}>{s}</span>)}
                  </div>
                </details>
              )}
            </Accordion>
          )}

          {/* Skills breakdown */}
          {skills.length > 0 && (
            <Accordion title="Skills Analysis">
              <div className="skills-table">
                {skills.map(([sk, data]) => (
                  <div className="skills-row" key={sk}>
                    <div className="skills-row__name">{sk}</div>
                    <div className="skills-row__bar">
                      <ScoreBar value={data.avg_score} color={scoreColor(data.avg_score)} />
                    </div>
                    <span className={`chip ${scoreChipClass(data.avg_score)}`}>{fmt(data.avg_score)}/10</span>
                    <span className={`chip chip-stone`}>{data.risk || "—"}</span>
                  </div>
                ))}
              </div>
            </Accordion>
          )}

          {/* Q&A breakdown (sorted weakest first) */}
          {sortedQs.length > 0 && (
            <Accordion title="Question Breakdown" badge="Weakest first">
              <div className="qa-list">
                {sortedQs.map((item, i) => {
                  const s = item.score;
                  // Determine scoring method label and style
                  const method = item.scoring_method || item.scorer || "cosine";
                  const methodLabels = {
                    "skipped": { label: "Skipped", chipClass: "chip-stone" },
                    "llm_qwen": { label: "LLM (Qwen)", chipClass: "chip-blue" },
                    "cosine_similarity": { label: "Cosine", chipClass: "chip-stone" },
                    "whisper_asr": { label: "Whisper ASR", chipClass: "chip-amber" },
                    "llm": { label: "LLM", chipClass: "chip-blue" },
                    "cosine": { label: "Cosine", chipClass: "chip-stone" },
                  };
                  const methodInfo = methodLabels[method] || { label: method, chipClass: "chip-stone" };
                  
                  return (
                    <div className="qa-item" key={i}>
                      <div className="qa-item__header">
                        <div className="qa-item__left">
                          <span className={`chip ${scoreChipClass(s)}`}>{fmt(s)}/10</span>
                          {item.skipped && <span className="chip chip-stone">Skipped</span>}
                          <span className={`chip ${methodInfo.chipClass} qa-item__method`} title="Scoring method used">
                            {methodInfo.label}
                          </span>
                          {item.skill_target && <span className="chip chip-stone qa-item__skill">{item.skill_target}</span>}
                          {(item.question_type || item.type) && <span className="chip chip-stone qa-item__type">{item.question_type || item.type}</span>}
                        </div>
                      </div>
                      <div className="qa-item__question">Q: {item.question}</div>
                      {(item.answer || item.answer_preview) && <div className="qa-item__answer">A: {item.answer || item.answer_preview}</div>}
                      {item.llm_evaluation?.what_was_missing && (
                        <div className="qa-item__missing">
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4m0-4h.01"/></svg>
                          Missing: {item.llm_evaluation.what_was_missing}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </Accordion>
          )}

          {/* Filler words */}
          {(fillers.total_words ?? 0) > 0 && (
            <Accordion title="Fluency Analysis">
              <div className="filler-summary">
                <div className="filler-summary__stats">
                  <div className="stat-box">
                    <div className="stat-box__val">{fillers.total_fillers ?? 0}</div>
                    <div className="stat-box__label">Total Fillers</div>
                  </div>
                  <div className="stat-box">
                    <div className="stat-box__val">{fillers.avg_fluency_score != null ? fillers.avg_fluency_score.toFixed(1) : "—"}/10</div>
                    <div className="stat-box__label">Fluency Score</div>
                  </div>
                  <div className="stat-box">
                    <div className="stat-box__val">{fillers.total_words ?? 0}</div>
                    <div className="stat-box__label">Total Words</div>
                  </div>
                </div>
                {(fillers.top_fillers || []).length > 0 && (
                  <div className="filler-bars">
                    <div className="filler-bars__title">Most Used Fillers</div>
                    {fillers.top_fillers.slice(0, 5).map((f, i) => {
                      const maxCount = Math.max(...fillers.top_fillers.map(x => x.count), 1);
                      return (
                        <div className="filler-bar-row" key={i}>
                          <span className="filler-bar-row__word">"{f.word}"</span>
                          <div className="filler-bar-row__track">
                            <div className="filler-bar-row__fill" style={{width:`${(f.count/maxCount)*100}%`}}/>
                          </div>
                          <span className="filler-bar-row__count">×{f.count}</span>
                        </div>
                      );
                    })}
                  </div>
                )}
                {(fillers.suggestions || []).map((s, i) => (
                  <div className="filler-tip" key={i}>{s}</div>
                ))}
              </div>
            </Accordion>
          )}

          {/* Posture */}
          {posture.total_snapshots > 0 && (
            <Accordion title="Posture Summary">
              <div className="posture-summary">
                <div className="stat-box">
                  <div className="stat-box__val">{posture.good_posture_pct != null ? `${posture.good_posture_pct}%` : "—"}</div>
                  <div className="stat-box__label">Good Posture</div>
                </div>
                <div className="stat-box">
                  <div className="stat-box__val">{posture.most_common_label || "—"}</div>
                  <div className="stat-box__label">Most Common</div>
                </div>
                <div className="stat-box">
                  <div className="stat-box__val">{posture.total_snapshots}</div>
                  <div className="stat-box__label">Snapshots</div>
                </div>
              </div>
            </Accordion>
          )}

          {/* Action plan */}
          {actionPlan.length > 0 && (
            <Accordion title="Personalised Action Plan" defaultOpen={true} badge="Recommended" priority="high">
              <ol className="action-plan">
                {actionPlan.map((item, i) => (
                  <li key={i} className="action-plan__item">
                    <span className="action-plan__num">{String(i + 1).padStart(2, "0")}</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ol>
            </Accordion>
          )}

        </div>
      </div>
    </div>
  );
}
