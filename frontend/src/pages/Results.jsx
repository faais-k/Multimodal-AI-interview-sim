import { RadialBarChart, RadialBar, PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import { useState } from "react";

/* ── helpers ── */
const fmtPct = v => v != null ? `${Math.round(v * 100)}%` : "—";
const fmtScore = v => v != null ? v.toFixed(1) : "—";
const riskColor = r => r === "LOW" ? "#48bb78" : r === "MEDIUM" ? "#ed8936" : "#fc8181";
const verdictStyle = v => ({
  PASS:       { bg:"#48bb7822", border:"#48bb78", color:"#48bb78", emoji:"🎉" },
  BORDERLINE: { bg:"#ed893622", border:"#ed8936", color:"#ed8936", emoji:"⚠️" },
  FAIL:       { bg:"#fc818122", border:"#fc8181", color:"#fc8181", emoji:"❌" },
}[v] || { bg:"#2a2d3e", border:"#667eea", color:"#667eea", emoji:"📊" });

const FILLER_COLORS = ["#667eea","#764ba2","#9f7aea","#4299e1","#48bb78","#ed8936"];

export default function Results({ report, onRestart }) {
  if (!report) return null;

  const verdict   = report.decision || report.verdict || "BORDERLINE";
  const vs        = verdictStyle(verdict);
  const score     = report.final_score ?? 0;
  const skills    = Object.entries(report.skills_analysis || {});
  const fillers   = report.filler_word_summary || {};
  const posture   = report.posture_summary || {};
  const quality   = report.answer_quality  || {};
  const readiness = report.readiness_index || {};
  const reviewer  = report.reviewer_summary|| {};
  const candidate = report.candidate       || {};
  const viols     = report.violations_summary || {};
  const postureLabelText = {
    GOOD: "✅ Good posture maintained",
    HEAD_FORWARD: "⚠️ Head frequently forward — try sitting back",
    SLOUCHING: "⚠️ Slouching detected — straighten your back",
    LOOKING_AWAY: "⚠️ Camera angle issues detected",
  };

  const [expandedQA, setExpandedQA] = useState(() => new Set());
  const toggleQA = (key) => {
    setExpandedQA(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const truncate120 = (s) => {
    const t = String(s || "");
    return t.length > 120 ? t.slice(0, 120) + "..." : t;
  };

  // Pie data for filler words
  const fillerPieData = (fillers.top_fillers || []).map((f, i) => ({
    name: `"${f.word}"`, value: f.count, fill: FILLER_COLORS[i % FILLER_COLORS.length],
  }));

  // Radial gauge data
  const gaugeData = [{ value: score, fill: score >= 7.5 ? "#48bb78" : score >= 6 ? "#ed8936" : "#fc8181" }];

  return (
    <div style={S.page}>
      <div style={S.container}>

        {/* ── HEADER ── */}
        <div style={S.header}>
          <div style={S.headerLeft}>
            <div style={S.headerName}>{candidate.name || "Candidate"}</div>
            <div style={S.headerMeta}>
              {candidate.job_role && <span style={S.metaChip}>💼 {candidate.job_role}</span>}
              {candidate.company  && <span style={S.metaChip}>🏢 {candidate.company}</span>}
              {candidate.expertise_level && <span style={{...S.metaChip, textTransform:"capitalize"}}>📊 {candidate.expertise_level}</span>}
            </div>
          </div>
          <button style={S.restartBtn} onClick={onRestart}>🔄 New Interview</button>
        </div>

        {/* ── VERDICT + SCORE GAUGE ── */}
        <div style={S.topRow}>
          <div style={{ ...S.verdictCard, background: vs.bg, border: `1px solid ${vs.border}` }}>
            <div style={S.verdictEmoji}>{vs.emoji}</div>
            <div style={{ ...S.verdictLabel, color: vs.color }}>{verdict}</div>
            <div style={S.verdictSub}>{readiness.level || ""}</div>
            <div style={S.verdictConfidence}>Confidence: {fmtPct(report.confidence)}</div>
          </div>

          <div style={S.gaugeCard}>
            <div style={S.gaugeTitle}>Overall Score</div>
            <div style={S.gaugeWrap}>
              <ResponsiveContainer width="100%" height={180}>
                <RadialBarChart cx="50%" cy="100%" innerRadius="60%" outerRadius="100%"
                  startAngle={180} endAngle={0} data={[{ value: 10, fill: "#2a2d3e" }, ...gaugeData]}>
                  <RadialBar dataKey="value" cornerRadius={8} />
                </RadialBarChart>
              </ResponsiveContainer>
              <div style={S.gaugeScore}>{fmtScore(score)}<span style={S.gaugeMax}>/10</span></div>
            </div>
            <div style={S.gaugeSub}>Pass threshold: {report.pass_threshold ?? 6.0}</div>
          </div>

          <div style={S.quickStats}>
            {[
              { label:"Questions", value: report.questions_counted ?? "—" },
              { label:"Coverage",  value: fmtPct(report.coverage_pct) },
              { label:"Avg Similarity", value: quality.avg_similarity != null ? quality.avg_similarity.toFixed(2) : "—" },
              { label:"Consistency", value: quality.consistency || "—" },
              { label:"Posture Good", value: posture.good_posture_pct != null ? `${posture.good_posture_pct}%` : "—" },
              { label:"Violations", value: viols.total ?? 0 },
            ].map(s => (
              <div key={s.label} style={S.statBox}>
                <div style={S.statVal}>{s.value}</div>
                <div style={S.statLabel}>{s.label}</div>
              </div>
            ))}
          </div>
        </div>

        {/* ── DECISION REASONS ── */}
        {(report.decision_reasons || []).length > 0 && (
          <div style={S.section}>
            <h3 style={S.sectionTitle}>📋 Decision Summary</h3>
            <div style={S.reasonsList}>
              {(report.decision_reasons || []).map((r, i) => (
                <div key={i} style={S.reasonItem}>
                  <span style={S.reasonBullet}>›</span>{r}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── PERFORMANCE SUMMARY ── */}
        {(report.strengths || []).length + (report.weak_areas || []).length + (report.not_assessed || []).length > 0 && (
          <div style={S.section}>
            <h3 style={S.sectionTitle}>📈 Performance Summary</h3>
            <div style={S.performanceGroups}>
              {(report.strengths || []).length > 0 && (
                <div style={S.performanceGroup}>
                  <div style={S.performanceGroupTitle}>✅ Strengths</div>
                  <div style={S.pillsRow}>
                    {(report.strengths || []).map((sk, i) => (
                      <span key={i} style={S.pillGreen}>{sk}</span>
                    ))}
                  </div>
                </div>
              )}
              {(report.weak_areas || []).length > 0 && (
                <div style={S.performanceGroup}>
                  <div style={S.performanceGroupTitle}>⚠️ Needs Work</div>
                  <div style={S.pillsRow}>
                    {(report.weak_areas || []).map((sk, i) => (
                      <span key={i} style={S.pillOrange}>{sk}</span>
                    ))}
                  </div>
                </div>
              )}
              {(report.not_assessed || []).length > 0 && (
                <div style={S.performanceGroup}>
                  <div style={S.performanceGroupTitle}>📋 Not Assessed</div>
                  <div style={S.pillsRow}>
                    {(report.not_assessed || []).map((sk, i) => (
                      <span key={i} style={S.pillGray}>{sk}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── STRENGTHS + CONCERNS ── */}
        <div style={S.twoCol}>
          <div style={S.section}>
            <h3 style={S.sectionTitle}>✅ Strengths</h3>
            {(reviewer.strengths || []).map((s, i) => (
              <div key={i} style={S.strengthItem}><span style={S.greenDot} />{s}</div>
            ))}
          </div>
          <div style={S.section}>
            <h3 style={S.sectionTitle}>⚠️ Areas to Improve</h3>
            {(reviewer.concerns || []).map((c, i) => (
              <div key={i} style={S.concernItem}><span style={S.orangeDot} />{c}</div>
            ))}
          </div>
        </div>

        {/* ── SKILL BREAKDOWN ── */}
        <div style={S.section}>
          <h3 style={S.sectionTitle}>🧠 Skill-by-Skill Analysis</h3>
          {skills.length === 0 && (
            <div style={S.noData}>No skill-level data available. This may happen if the answer scoring did not identify specific skill tokens.</div>
          )}
          {skills.length > 0 && (
            <div style={S.skillTable}>
              <div style={S.skillHeader}>
                <span>Skill</span><span>Avg Score</span><span>Questions</span><span>Follow-ups</span><span>Risk</span>
              </div>
              {skills.sort((a,b) => (b[1].avg_score||0)-(a[1].avg_score||0)).map(([skill, data]) => (
                <div key={skill} style={S.skillRow}>
                  <span style={S.skillName}>{skill}</span>
                  <span style={{ ...S.skillScore, color: riskColor(data.risk) }}>
                    {fmtScore(data.avg_score)}
                  </span>
                  <span style={S.skillCell}>{data.questions}</span>
                  <span style={S.skillCell}>{data.followups}</span>
                  <span style={{ ...S.riskBadge, background: riskColor(data.risk) + "22", color: riskColor(data.risk) }}>
                    {data.risk}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ── SCORE BREAKDOWN BY TYPE ── */}
        {Object.keys(report.per_type_summary || {}).length > 0 && (
          <div style={S.section}>
            <h3 style={S.sectionTitle}>📊 Score Breakdown by Question Type</h3>
            <div style={S.typeGrid}>
              {Object.entries(report.per_type_summary).map(([type, data]) => (
                <div key={type} style={S.typeCard}>
                  <div style={S.typeLabel}>{type.replace("_"," ").toUpperCase()}</div>
                  <div style={S.typeScore}>{fmtScore(data.avg_raw)}</div>
                  <div style={S.typeMeta}>{data.count} question{data.count !== 1 ? "s" : ""}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── SKILL COVERAGE ── */}
        {(report.skill_coverage && Object.keys(report.skill_coverage).length > 0) && (
          <div style={S.section}>
            <h3 style={S.sectionTitle}>🧩 Skill Coverage</h3>
            <div style={S.coverageList}>
              {(() => {
                const entries = Object.entries(report.skill_coverage || {});
                const tested = entries
                  .filter(([_, v]) => v && v.tested)
                  .sort((a, b) => (b[1].avg_score ?? -1) - (a[1].avg_score ?? -1));
                const notAssessed = entries
                  .filter(([_, v]) => !v || !v.tested)
                  .sort((a, b) => a[0].localeCompare(b[0]));
                return [...tested, ...notAssessed].map(([skill, data]) => {
                  const avg = data?.avg_score;
                  const questions = data?.questions ?? 0;
                  const isTested = !!data?.tested;
                  const scoreColor = avg == null
                    ? "#667eea"
                    : avg >= 7.5 ? "#48bb78" : avg >= 6.5 ? "#ed8936" : "#fc8181";
                  return (
                    <div key={skill} style={S.coverageRow}>
                      <div style={S.coverageSkill}>
                        <span style={{ ...S.coverageDot, background: isTested ? scoreColor : "#4a5568" }} />
                        <span>{skill}</span>
                        {!isTested && (
                          <span style={S.badgeGray}>Not assessed</span>
                        )}
                      </div>
                      <div style={S.coverageCell}>
                        {isTested ? (avg == null ? "—" : fmtScore(avg)) : "—"}
                      </div>
                      <div style={S.coverageCell}>{isTested ? questions : 0}</div>
                      <div style={S.coverageCell}>
                        {isTested ? (
                          <span style={{ ...S.badgeScore, borderColor: scoreColor, color: scoreColor }}>
                            {avg >= 7.5 ? "Strong" : avg >= 6.5 ? "Medium" : "Low"}
                          </span>
                        ) : null}
                      </div>
                    </div>
                  );
                });
              })()}
            </div>
          </div>
        )}

        {/* ── INTERVIEW Q&A BREAKDOWN ── */}
        {(report.question_breakdown && report.question_breakdown.length > 0) && (
          <div style={S.section}>
            <h3 style={S.sectionTitle}>📝 Interview Q&A Breakdown</h3>
            <div style={S.qaList}>
              {report.question_breakdown.map((item, idx) => {
                const q = item?.question || "";
                const key = `${idx}-${item?.skill_target || ""}-${item?.type || ""}`;
                const open = expandedQA.has(key);
                const score = item?.score;
                const scoreColor = score == null
                  ? "#667eea"
                  : score >= 7.5 ? "#48bb78" : score >= 6.5 ? "#ed8936" : "#fc8181";
                return (
                  <div key={key} style={S.qaRow}>
                    <div
                      role="button"
                      tabIndex={0}
                      onClick={() => toggleQA(key)}
                      style={S.qaRowMain}
                    >
                      <div style={S.qaTopLine}>
                        <span style={{ ...S.qaBadge, borderColor: scoreColor, color: scoreColor }}>
                          {score == null ? "—" : fmtScore(score)}
                        </span>
                        <span style={S.qaTypeTag}>{item?.type || "technical"}</span>
                        {item?.skill_target && <span style={S.qaSkillTag}>{item.skill_target}</span>}
                      </div>
                      <div style={S.qaQuestionText}>
                        {open ? q : truncate120(q)}
                      </div>
                      <div style={S.qaAnswerPreview}>{item?.answer_preview || ""}</div>
                    </div>
                    {open && <div style={S.qaRowDetails} />}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ── FILLER WORDS ── */}
        <div style={S.twoCol}>
          <div style={S.section}>
            <h3 style={S.sectionTitle}>💬 Filler Word Analysis</h3>
            <div style={S.fillerSummary}>
              <div style={S.fillerStat}>
                <span style={S.fillerNum}>{fillers.total_fillers ?? 0}</span>
                <span style={S.fillerStatLabel}>Total fillers</span>
              </div>
              <div style={S.fillerStat}>
                <span style={S.fillerNum}>{fillers.affected_answers ?? 0}</span>
                <span style={S.fillerStatLabel}>Affected answers</span>
              </div>
              <div style={S.fillerStat}>
                <span style={S.fillerNum}>{(fillers.top_fillers || []).length}</span>
                <span style={S.fillerStatLabel}>Top fillers tracked</span>
              </div>
            </div>
            {fillerPieData.length > 0 && (
              <ResponsiveContainer width="100%" height={180}>
                <PieChart>
                  <Pie data={fillerPieData} cx="50%" cy="50%" outerRadius={70} dataKey="value" label={({name,value}) => `${name}:${value}`} labelLine={false} fontSize={11}>
                    {fillerPieData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
                  </Pie>
                  <Tooltip formatter={(v, n) => [v, n]} contentStyle={{ background:"#1a1d2e", border:"1px solid #2a2d3e", borderRadius:"8px", color:"#e2e8f0" }} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* ── POSTURE ── */}
          <div style={S.section}>
            <h3 style={S.sectionTitle}>🧍 Posture Summary</h3>
            {posture.total_snapshots > 0 ? (
              <>
                <div style={S.postureGauge}>
                  <div style={{ ...S.postureBar, width: `${Math.min(posture.good_posture_pct || 0, 100)}%`, background: posture.good_posture_pct >= 70 ? "#48bb78" : "#ed8936" }} />
                </div>
                <div style={S.posturePct}>{posture.good_posture_pct ?? 0}% good posture</div>
                <div style={S.postureFlag}>
                  • {postureLabelText[posture.most_common_label] || posture.most_common_label || "No dominant posture label"}
                </div>
                <div style={S.postureFlag}>
                  • Average posture score: {Math.round((posture.avg_score || 0) * 100)}%
                </div>
              </>
            ) : (
              <div style={S.noData}>No posture data recorded.</div>
            )}

            {/* Anti-cheat */}
            {viols.total > 0 && (
              <div style={S.violBox}>
                <div style={S.violTitle}>🚨 Proctoring Flags</div>
                {Object.entries(viols.by_type || {}).map(([t, c]) => (
                  <div key={t} style={S.violItem}>{t.replace("_"," ")}: {c}×</div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* ── SUGGESTIONS ── */}
        {(report.suggestions || []).length > 0 && (
          <div style={S.section}>
            <h3 style={S.sectionTitle}>💡 Personalised Suggestions</h3>
            <div style={S.suggGrid}>
              {(report.suggestions || []).map((s, i) => (
                <div key={i} style={S.suggCard}>
                  <span style={S.suggNum}>{i + 1}</span>
                  <span style={S.suggText}>{s}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        <div style={S.footer}>
          <button style={S.restartBtnLg} onClick={onRestart}>🔄 Start Another Interview</button>
          <p style={S.footerNote}>AI Interview Simulator — Results are for practice purposes only.</p>
        </div>
      </div>
    </div>
  );
}

const S = {
  page:           { minHeight:"100vh", background:"#0f1117", fontFamily:"'Segoe UI',system-ui,sans-serif", padding:"24px" },
  container:      { maxWidth:"1100px", margin:"0 auto", display:"flex", flexDirection:"column", gap:"20px" },
  header:         { background:"#1a1d2e", border:"1px solid #2a2d3e", borderRadius:"14px", padding:"20px 28px", display:"flex", alignItems:"center", justifyContent:"space-between" },
  headerLeft:     { display:"flex", flexDirection:"column", gap:"8px" },
  headerName:     { color:"#e2e8f0", fontSize:"22px", fontWeight:700 },
  headerMeta:     { display:"flex", gap:"10px", flexWrap:"wrap" },
  metaChip:       { background:"#2a2d3e", borderRadius:"20px", padding:"4px 12px", color:"#a0a3b1", fontSize:"13px" },
  restartBtn:     { padding:"10px 20px", background:"transparent", border:"1px solid #2a2d3e", borderRadius:"8px", color:"#a0a3b1", cursor:"pointer", fontSize:"14px", fontWeight:600 },
  topRow:         { display:"grid", gridTemplateColumns:"180px 1fr 1fr", gap:"20px" },
  verdictCard:    { borderRadius:"14px", padding:"24px", display:"flex", flexDirection:"column", alignItems:"center", gap:"8px", justifyContent:"center" },
  verdictEmoji:   { fontSize:"36px" },
  verdictLabel:   { fontSize:"20px", fontWeight:800, letterSpacing:"1px" },
  verdictSub:     { color:"#a0a3b1", fontSize:"13px", fontWeight:600 },
  verdictConfidence:{ color:"#4a5568", fontSize:"12px" },
  gaugeCard:      { background:"#1a1d2e", border:"1px solid #2a2d3e", borderRadius:"14px", padding:"20px", display:"flex", flexDirection:"column", alignItems:"center" },
  gaugeTitle:     { color:"#a0a3b1", fontSize:"13px", fontWeight:700, marginBottom:"4px" },
  gaugeWrap:      { position:"relative", width:"100%", height:"180px" },
  gaugeScore:     { position:"absolute", bottom:"20px", left:"50%", transform:"translateX(-50%)", color:"#e2e8f0", fontSize:"36px", fontWeight:800 },
  gaugeMax:       { fontSize:"16px", color:"#4a5568", fontWeight:400 },
  gaugeSub:       { color:"#4a5568", fontSize:"12px", marginTop:"4px" },
  quickStats:     { background:"#1a1d2e", border:"1px solid #2a2d3e", borderRadius:"14px", padding:"20px", display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:"16px" },
  statBox:        { display:"flex", flexDirection:"column", alignItems:"center", gap:"4px" },
  statVal:        { color:"#e2e8f0", fontSize:"20px", fontWeight:700 },
  statLabel:      { color:"#4a5568", fontSize:"11px", textAlign:"center" },
  section:        { background:"#1a1d2e", border:"1px solid #2a2d3e", borderRadius:"14px", padding:"24px 28px" },
  sectionTitle:   { color:"#e2e8f0", fontSize:"16px", fontWeight:700, margin:"0 0 16px" },
  reasonsList:    { display:"flex", flexDirection:"column", gap:"8px" },
  reasonItem:     { display:"flex", gap:"10px", color:"#a0a3b1", fontSize:"14px", lineHeight:1.5 },
  reasonBullet:   { color:"#667eea", fontWeight:700, flexShrink:0 },
  twoCol:         { display:"grid", gridTemplateColumns:"1fr 1fr", gap:"20px" },
  strengthItem:   { display:"flex", alignItems:"flex-start", gap:"10px", color:"#a0a3b1", fontSize:"14px", marginBottom:"8px", lineHeight:1.5 },
  greenDot:       { width:"8px", height:"8px", borderRadius:"50%", background:"#48bb78", flexShrink:0, marginTop:"5px" },
  concernItem:    { display:"flex", alignItems:"flex-start", gap:"10px", color:"#a0a3b1", fontSize:"14px", marginBottom:"8px", lineHeight:1.5 },
  orangeDot:      { width:"8px", height:"8px", borderRadius:"50%", background:"#ed8936", flexShrink:0, marginTop:"5px" },
  skillTable:     { display:"flex", flexDirection:"column", gap:"0" },
  skillHeader:    { display:"grid", gridTemplateColumns:"2fr 1fr 1fr 1fr 1fr", padding:"10px 16px", color:"#4a5568", fontSize:"12px", fontWeight:700, letterSpacing:"0.5px", borderBottom:"1px solid #2a2d3e" },
  skillRow:       { display:"grid", gridTemplateColumns:"2fr 1fr 1fr 1fr 1fr", padding:"12px 16px", borderBottom:"1px solid #1a1d2e", alignItems:"center" },
  skillName:      { color:"#e2e8f0", fontSize:"14px", fontWeight:500, textTransform:"capitalize" },
  skillScore:     { fontSize:"15px", fontWeight:700 },
  skillCell:      { color:"#a0a3b1", fontSize:"14px" },
  riskBadge:      { borderRadius:"20px", padding:"3px 10px", fontSize:"12px", fontWeight:700, width:"fit-content" },
  typeGrid:       { display:"grid", gridTemplateColumns:"repeat(auto-fill,minmax(130px,1fr))", gap:"12px" },
  typeCard:       { background:"#0f1117", border:"1px solid #2a2d3e", borderRadius:"10px", padding:"16px", textAlign:"center" },
  typeLabel:      { color:"#4a5568", fontSize:"10px", fontWeight:700, letterSpacing:"0.5px", marginBottom:"6px" },
  typeScore:      { color:"#e2e8f0", fontSize:"22px", fontWeight:800, marginBottom:"4px" },
  typeMeta:       { color:"#4a5568", fontSize:"11px" },
  fillerSummary:  { display:"flex", gap:"16px", marginBottom:"16px" },
  fillerStat:     { flex:1, background:"#0f1117", borderRadius:"10px", padding:"14px", textAlign:"center" },
  fillerNum:      { display:"block", color:"#667eea", fontSize:"22px", fontWeight:800, marginBottom:"4px" },
  fillerStatLabel:{ color:"#4a5568", fontSize:"11px" },
  performanceGroups: { display:"flex", gap:"14px", flexWrap:"wrap" },
  performanceGroup: { minWidth:"240px" },
  performanceGroupTitle:{ color:"#e2e8f0", fontSize:"13px", fontWeight:800, marginBottom:"10px" },
  pillsRow: { display:"flex", gap:"8px", flexWrap:"wrap" },
  pillGreen: { background:"#48bb7822", border:"1px solid #48bb78", color:"#48bb78", borderRadius:"999px", padding:"6px 10px", fontSize:"12px", fontWeight:700 },
  pillOrange:{ background:"#ed893622", border:"1px solid #ed8936", color:"#ed8936", borderRadius:"999px", padding:"6px 10px", fontSize:"12px", fontWeight:700 },
  pillGray:  { background:"#2a2d3e", border:"1px solid #4a5568", color:"#a0a3b1", borderRadius:"999px", padding:"6px 10px", fontSize:"12px", fontWeight:700 },
  coverageList: { display:"flex", flexDirection:"column", gap:"8px" },
  coverageRow: { background:"#0f1117", border:"1px solid #2a2d3e", borderRadius:"12px", padding:"12px 14px", display:"grid", gridTemplateColumns:"2.3fr 0.9fr 0.7fr 1fr", gap:"10px", alignItems:"center" },
  coverageSkill:{ display:"flex", alignItems:"center", gap:"10px", color:"#e2e8f0", fontSize:"14px", fontWeight:600 },
  coverageDot: { width:"10px", height:"10px", borderRadius:"50%", flexShrink:0, display:"inline-block" },
  coverageCell:{ color:"#a0a3b1", fontSize:"13px" },
  badgeGray:{ background:"#2a2d3e", border:"1px solid #4a5568", color:"#a0a3b1", borderRadius:"999px", padding:"4px 10px", fontSize:"12px", fontWeight:700, marginLeft:"10px" },
  badgeScore:{ background:"#1a1d2e22", border:"1px solid", borderRadius:"999px", padding:"4px 10px", fontSize:"12px", fontWeight:800, width:"fit-content" },
  qaList: { display:"flex", flexDirection:"column", gap:"12px" },
  qaRow: { background:"#0f1117", border:"1px solid #2a2d3e", borderRadius:"12px", overflow:"hidden" },
  qaRowMain:{ padding:"14px 16px", cursor:"pointer" },
  qaTopLine:{ display:"flex", gap:"10px", alignItems:"center", flexWrap:"wrap", marginBottom:"8px" },
  qaBadge:{ border:"1px solid", background:"#1a1d2e", borderRadius:"999px", padding:"6px 10px", fontSize:"12px", fontWeight:800 },
  qaTypeTag:{ background:"#1a1d2e", border:"1px solid #2a2d3e", color:"#a0a3b1", borderRadius:"999px", padding:"6px 10px", fontSize:"12px", fontWeight:700 },
  qaSkillTag:{ background:"#1a1d2e", border:"1px solid #2a2d3e", color:"#667eea", borderRadius:"999px", padding:"6px 10px", fontSize:"12px", fontWeight:800 },
  qaQuestionText:{ color:"#e2e8f0", fontSize:"14px", fontWeight:700, lineHeight:1.4 },
  qaRowDetails:{ padding:"0 16px 14px 16px" },
  qaAnswerPreview:{ color:"#a0a3b1", fontSize:"13px", lineHeight:1.5, whiteSpace:"pre-wrap" },
  postureGauge:   { background:"#0f1117", borderRadius:"50px", height:"12px", overflow:"hidden", marginBottom:"8px" },
  postureBar:     { height:"100%", borderRadius:"50px", transition:"width .5s" },
  posturePct:     { color:"#e2e8f0", fontSize:"16px", fontWeight:700, marginBottom:"12px" },
  postureFlag:    { color:"#a0a3b1", fontSize:"13px", marginBottom:"6px" },
  noData:         { color:"#4a5568", fontSize:"14px", fontStyle:"italic" },
  violBox:        { background:"#fc818111", border:"1px solid #fc818133", borderRadius:"10px", padding:"14px", marginTop:"16px" },
  violTitle:      { color:"#fc8181", fontSize:"13px", fontWeight:700, marginBottom:"8px" },
  violItem:       { color:"#fc8181", fontSize:"13px", opacity:0.8, marginBottom:"4px" },
  suggGrid:       { display:"flex", flexDirection:"column", gap:"10px" },
  suggCard:       { background:"#0f1117", border:"1px solid #2a2d3e", borderRadius:"10px", padding:"14px 18px", display:"flex", gap:"14px", alignItems:"flex-start" },
  suggNum:        { background:"#667eea22", color:"#667eea", borderRadius:"50%", width:"24px", height:"24px", display:"flex", alignItems:"center", justifyContent:"center", fontSize:"12px", fontWeight:800, flexShrink:0 },
  suggText:       { color:"#a0a3b1", fontSize:"14px", lineHeight:1.6 },
  footer:         { textAlign:"center", padding:"20px 0" },
  restartBtnLg:   { padding:"14px 40px", background:"linear-gradient(135deg,#667eea,#764ba2)", border:"none", borderRadius:"10px", color:"#fff", fontSize:"16px", fontWeight:700, cursor:"pointer", marginBottom:"12px" },
  footerNote:     { color:"#2a2d3e", fontSize:"12px", margin:0 },
};
