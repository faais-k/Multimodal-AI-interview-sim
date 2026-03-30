Perfect. Below is the **full, clean, editor-ready** version of **`docs/project_log.md`**.
You can **copy–paste as-is**. No filler, no inconsistencies, aligned with your actual backend state.

---

## 📄 `docs/project_log.md`

```md
# PROJECT LOG — Multimodal AI Interview Simulator

## Project Title
Multimodal AI Interview Simulator  
(Backend-first system with scoring, analytics, decision engine, and future frontend)

---

## Project Summary

The Multimodal AI Interview Simulator is a full-stack interview evaluation system designed to:

- Parse ATS-friendly resumes
- Accept job role, job description, experience, and education
- Dynamically generate interview questions
- Conduct a **stateful, multi-stage interview**
- Score answers using **Sentence Transformers + TF-IDF explainability**
- Insert **follow-up questions automatically** when answers lack depth
- Aggregate scores into a final report
- Generate analytics and a readiness index
- Produce a final hiring decision (PASS / BORDERLINE / HOLD)
- Persist **all artifacts** for audit and review

The backend is deterministic, explainable, and LLM-free by design (LLMs planned later).

---

## Architecture Overview

### Backend Stack
- **Framework**: FastAPI
- **ML**: sentence-transformers, scikit-learn
- **ASR**: Whisper (via transformers)
- **Storage**: filesystem (`storage/<session_id>/`)
- **State management**: JSON-based interview state machine
- **Scoring**: cosine similarity + heuristics
- **Analytics**: post-interview signal analysis
- **Decision engine**: rule-based, conservative by default

---

## Key Directories & Files

```

backend/
└── app/
├── main.py
├── api/
│   └── routes/
│       ├── health.py
│       ├── session.py
│       ├── upload.py
│       ├── parse_resume.py
│       ├── interview_plan.py
│       ├── generate_question.py
│       ├── score_text.py
│       ├── answer_audio.py
│       ├── aggregate_scores.py      # Phase 6.1
│       ├── analytics_report.py      # Phase 6.2
│       └── decision.py              # Phase 6.3
├── core/
│   ├── interview_flow.py
│   ├── interview_state.py
│   ├── interview_reasoning.py
│   ├── scoring_config.py
│   └── ml_models.py
docs/
├── api_contracts.md
├── project_log.md
storage/
└── <session_id>/

```

---

## Interview Flow (Authoritative)

```

intro
→ project
→ technical (resume + JD driven)
→ follow-ups (conditional, dynamic)
→ HR / behavioral
→ critical thinking
→ warmup
→ wrapup
→ candidate questions (loop until none)
→ end

````

Rules:
- Intro and project are fixed stages
- Follow-ups can occur **anywhere except between intro → project**
- Interview never ends abruptly after wrap-up
- Candidate questions are handled before final termination

---

## Chronological Development Log

### Phase 0 — Foundation
- Repository initialized
- FastAPI skeleton created
- Health check endpoint added
- Session creation with isolated storage implemented

---

### Phase 1 — Resume Handling
- Resume upload (`/api/upload/resume`)
- PDF/DOCX text extraction
- Resume parsing (`/api/parse/resume/{session_id}`)
- Extracted: name, email, skills
- Parsing hardened against encoding errors

---

### Phase 2 — Interview Planning
- Interview plan generation using:
  - Resume
  - Job role
  - Job description
  - Candidate profile
- Deterministic question generation (no LLM)
- Output stored as `interview_plan.json`

---

### Phase 3 — Interview State Machine
- Implemented persistent interview state
- Added:
  - `start_interview`
  - `next_question`
- State transitions tracked in `interview_state.json`
- Prevents repeated questions
- Supports dynamic follow-ups

---

### Phase 4 — Answer Scoring
- Text answer scoring (`/api/score/text`)
- SentenceTransformer embeddings
- Cosine similarity normalized to score [0–10]
- TF-IDF token extraction for explainability
- Human-review flags when:
  - Score below threshold
  - Answer too short
  - Depth insufficient

---

### Phase 5 — Audio Answers (ASR)
- Audio upload endpoint
- Whisper ASR integration
- Transcript auto-scored using same pipeline
- Audio persisted for audit

---

### Phase 6.1 — Score Aggregation
- Aggregates all question scores
- Weighted scoring by question type
- Coverage validation against interview plan
- Generates `final_report.json`
- Updates interview state with final metadata

---

### Phase 6.2 — Analytics
- Skill-wise performance analysis
- Follow-up pressure metrics
- Answer consistency signals
- Risk classification (LOW / MEDIUM / HIGH)
- Readiness index generation
- Output: `analytics_report.json`

Cleanup iteration performed:
- Removed stop-word noise
- Reduced token pollution
- Limited skills to meaningful technical signals

---

### Phase 6.3 — Decision Engine
- Final hiring decision endpoint
- Inputs:
  - Final score
  - Analytics signals
  - Human-review flags
- Conservative rules:
  - Human review → BORDERLINE or HOLD
- Output: `decision.json`

---

## Known Issues & Resolutions

### Docs UI freezing
- Cause: heavy ML loads during startup
- Fix: lazy model loading

### Resume parsing crashes
- Cause: malformed PDFs
- Fix: error-tolerant text extraction

### Model reload issues (uvicorn)
- Cause: reload + model load race
- Fix: centralized model loader with fallback

---

## Current Status (Confirmed)

✅ Backend complete  
✅ Interview lifecycle stable  
✅ Scoring, aggregation, analytics, decision working  
✅ API contract finalized  
⏳ LLM enhancement deferred  
⏳ Security hardening pending  
⏳ Frontend not started

---

## Deferred / Future Enhancements

- LLM-based question generation
- LLM-assisted answer evaluation
- Skill taxonomy + ontology
- JWT authentication & RBAC
- Performance optimizations
- Vector DB for answer history
- Admin dashboard

---

## How to Run (Local)

```bash
python -m venv intrv-sim
source intrv-sim/bin/activate
pip install -r requirements.txt
uvicorn backend.app.main:app --reload --reload-exclude storage/*
````

---

## Recommended Next Steps

1. Freeze backend (tag release)
2. Finalize API contract (done)
3. Build frontend (React/Vite)
4. Add admin dashboard
5. Harden security

---

## Changelog

* **2026-02-02**

  * Phase 6.1, 6.2, 6.3 completed
  * Backend feature-complete (non-LLM)

