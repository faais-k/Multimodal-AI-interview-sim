import { useState } from 'react';
import './Landing.css';

const Logo = () => (
  <svg width="36" height="36" viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <rect width="36" height="36" rx="10" fill="url(#logo-bg)"/>
    {/* Mountain/ascent path */}
    <path d="M8 26 L18 10 L28 26" stroke="white" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" fill="none" opacity="0.4"/>
    <path d="M8 26 L14 18 L18 22 L22 14 L28 26" stroke="white" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" fill="none"/>
    <defs>
      <linearGradient id="logo-bg" x1="0" y1="0" x2="36" y2="36">
        <stop offset="0%" stopColor="#14B8A6"/>
        <stop offset="100%" stopColor="#0D9488"/>
      </linearGradient>
    </defs>
  </svg>
);

const FEATURES = [
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <path d="M9 12h6m-3-3v6m9-6a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"/>
      </svg>
    ),
    title: "Resume-Aware Questions",
    desc: "Parses your resume to generate questions tailored to your actual skills and projects — no generic templates."
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <path d="M19 11a7 7 0 0 1-7 7m0 0a7 7 0 0 1-7-7m7 7v4m0-4a7 7 0 0 0 7-7m-7 7a7 7 0 0 1-7-7m7 7v4"/>
      </svg>
    ),
    title: "Voice Recognition",
    desc: "Speak your answers with Whisper ASR. Filler word detection and fluency scoring included."
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <path d="M2.5 12a9.5 9.5 0 1 1 19 0 9.5 9.5 0 0 1-19 0Z"/><path d="M12 6v6l4 2"/>
      </svg>
    ),
    title: "Posture Monitoring",
    desc: "Real-time webcam posture analysis keeps you interview-ready with live feedback."
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-5 0v-15A2.5 2.5 0 0 1 9.5 2Z"/><path d="M14.5 8A2.5 2.5 0 0 1 17 10.5v9a2.5 2.5 0 0 1-5 0v-9A2.5 2.5 0 0 1 14.5 8Z"/>
      </svg>
    ),
    title: "LLM Scoring",
    desc: "Qwen2.5-7B evaluates answer quality, depth and relevance — not just keyword matching."
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z"/>
      </svg>
    ),
    title: "Adaptive Follow-ups",
    desc: "AI generates contextual follow-up questions based on what was missing in your last answer."
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/>
      </svg>
    ),
    title: "Difficulty by Level",
    desc: "Fresher, intermediate, or experienced — question difficulty and depth calibrate automatically."
  },
];

const STEPS = [
  { n:"01", title:"Upload Resume", desc:"Upload your PDF or DOCX resume. We parse it to extract skills, projects, and experience." },
  { n:"02", title:"Configure Session", desc:"Set your target role, company (optional), and experience level to tailor the interview." },
  { n:"03", title:"Start Interview", desc:"Answer questions via text or voice. The AI scores each response and asks follow-ups." },
  { n:"04", title:"Review Report", desc:"Get a comprehensive scorecard: skill analysis, posture trends, fluency, and a personalised action plan." },
];

export default function Landing({ onStart }) {
  const [nav, setNav] = useState(false);

  return (
    <div className="landing">
      {/* ── Nav ── */}
      <nav className="l-nav">
        <div className="l-nav__inner">
          <a className="l-nav__brand" href="#" aria-label="Ascent home">
            <Logo />
            <span className="l-nav__wordmark">Ascent</span>
          </a>
          <div className="l-nav__links">
            <a href="#features" className="l-nav__link">Features</a>
            <a href="#how-it-works" className="l-nav__link">How it works</a>
            <a href="#stack" className="l-nav__link">Technology</a>
          </div>
          <button className="btn-primary l-nav__cta" onClick={onStart}>
            Start Free
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
          </button>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section className="l-hero">
        <div className="l-hero__inner">
          <div className="l-hero__badge">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>
            Open Source · Runs on Free Colab GPU
          </div>

          <h1 className="l-hero__title">
            Interview practice that<br/>
            <em className="l-hero__em">actually prepares you</em>
          </h1>

          <p className="l-hero__sub">
            Resume-aware questions, real-time posture feedback, voice recognition, and LLM scoring — 
            all running on a free Colab T4 GPU.
          </p>

          <div className="l-hero__actions">
            <button className="btn-primary l-hero__cta" onClick={onStart}>
              Start Mock Interview
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
            </button>
            <a className="btn-secondary" href="https://github.com/FaaizBinKasim/Multimodal-AI-interview-sim" target="_blank" rel="noopener noreferrer">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"/></svg>
              View Source
            </a>
          </div>

          <div className="l-hero__social-proof">
            <div className="l-hero__proof-item">
              <span className="l-hero__proof-num">7B</span>
              <span className="l-hero__proof-label">LLM parameters</span>
            </div>
            <div className="l-hero__proof-divider" />
            <div className="l-hero__proof-item">
              <span className="l-hero__proof-num">Free</span>
              <span className="l-hero__proof-label">Colab T4 GPU</span>
            </div>
            <div className="l-hero__proof-divider" />
            <div className="l-hero__proof-item">
              <span className="l-hero__proof-num">Real-time</span>
              <span className="l-hero__proof-label">posture analysis</span>
            </div>
          </div>
        </div>

        {/* Decorative warm gradient orbs */}
        <div className="l-hero__orb l-hero__orb--teal" aria-hidden="true"/>
        <div className="l-hero__orb l-hero__orb--amber" aria-hidden="true"/>
      </section>

      {/* ── Features ── */}
      <section className="l-section" id="features">
        <div className="l-section__inner">
          <div className="l-section__header">
            <span className="chip chip-teal">Features</span>
            <h2 className="l-section__title">Everything for a real interview experience</h2>
            <p className="l-section__sub">Not just Q&A — a complete practice environment with multimodal feedback.</p>
          </div>
          <div className="l-features-grid">
            {FEATURES.map((f, i) => (
              <div className="l-feature-card" key={i}>
                <div className="l-feature-card__icon">{f.icon}</div>
                <div className="l-feature-card__title">{f.title}</div>
                <div className="l-feature-card__desc">{f.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── How it works ── */}
      <section className="l-section l-section--alt" id="how-it-works">
        <div className="l-section__inner">
          <div className="l-section__header">
            <span className="chip chip-amber">Process</span>
            <h2 className="l-section__title">Up and running in four steps</h2>
          </div>
          <div className="l-steps">
            {STEPS.map((s, i) => (
              <div className="l-step" key={i}>
                <div className="l-step__num">{s.n}</div>
                <div>
                  <div className="l-step__title">{s.title}</div>
                  <div className="l-step__desc">{s.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Tech stack ── */}
      <section className="l-section" id="stack">
        <div className="l-section__inner">
          <div className="l-section__header">
            <span className="chip chip-stone">Stack</span>
            <h2 className="l-section__title">Built on solid foundations</h2>
          </div>
          <div className="l-tech-grid">
            {[
              {name:"Qwen2.5-7B",role:"Answer scoring & follow-up generation"},
              {name:"Whisper",role:"Speech-to-text transcription"},
              {name:"all-mpnet",role:"Semantic similarity (cosine fallback)"},
              {name:"MediaPipe",role:"Real-time posture detection"},
              {name:"FastAPI",role:"Backend API (Python)"},
              {name:"React + Vite",role:"Frontend interface"},
              {name:"Colab T4",role:"Free GPU runtime"},
              {name:"ngrok",role:"Public URL tunnel"},
            ].map((t,i) => (
              <div className="l-tech-item" key={i}>
                <div className="l-tech-item__name">{t.name}</div>
                <div className="l-tech-item__role">{t.role}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA Banner ── */}
      <section className="l-cta-banner">
        <div className="l-cta-banner__inner">
          <h2 className="l-cta-banner__title">Ready to sharpen your edge?</h2>
          <p className="l-cta-banner__sub">Upload your resume and start a tailored mock interview in 60 seconds.</p>
          <button className="btn-primary" onClick={onStart} style={{fontSize:"var(--text-md)", padding:"var(--space-4) var(--space-8)"}}>
            Start Your Interview
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
          </button>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="l-footer">
        <div className="l-footer__inner">
          <div className="l-footer__brand">
            <Logo />
            <span>Ascent</span>
          </div>
          <div className="l-footer__note">Open source · MIT License · No data stored on our servers</div>
        </div>
      </footer>
    </div>
  );
}
