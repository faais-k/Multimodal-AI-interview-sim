import "./Processing.css";
export default function Processing({ error, onRetry }) {
  return (
    <div className="proc-shell">
      <div className="proc-card animate-in">
        {error ? (
          <>
            <div className="proc-icon proc-icon--error">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
            </div>
            <h2 className="proc-title">Something went wrong</h2>
            <p className="proc-sub">{error}</p>
            {onRetry && <button className="btn-primary" onClick={onRetry}>Try Again</button>}
          </>
        ) : (
          <>
            <div className="proc-icon">
              <span className="spinner" style={{width:40,height:40,borderWidth:3}}/>
            </div>
            <h2 className="proc-title">Analysing your interview…</h2>
            <p className="proc-sub">Generating your personalised scorecard and action plan.</p>
            <div className="proc-steps">
              {["Scoring all answers","Detecting filler words","Analysing posture","Building action plan"].map((s,i)=>(
                <div className="proc-step" key={i} style={{animationDelay:`${i*0.3}s`}}>
                  <span className="spinner" style={{width:12,height:12,borderWidth:2}}/>{s}
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
