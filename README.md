---
title: Ascent Interview Backend
emoji: 🤖
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
---

# 🤖 Multimodal AI Interview Simulator

A production-grade AI interview simulator for students and colleges. Practice real interviews with camera monitoring, speech recognition, semantic scoring, filler word detection, and detailed feedback.

---

## ✨ Features

| Feature | Description |
|---|---|
| 📄 Resume-aware questions | Parses your PDF resume and generates targeted questions |
| 🎤 Voice answers | Whisper large-v3-turbo transcribes your spoken answers |
| 🧠 Semantic scoring | all-mpnet-base-v2 scores answer relevance (0–10) |
| 💬 Filler word detection | Catches "um", "uh", "like", "basically" etc. |
| 🧍 Posture analysis | MediaPipe BlazePose in-browser, real-time skeleton overlay |
| ⛶ Anti-cheat proctoring | Fullscreen lock, tab-switch detection, violation logging |
| 📊 Detailed scorecard | Skill breakdown, readiness index, personalised suggestions |
| 🤖 LLM questions (optional) | Qwen2.5-7B via HuggingFace free API |
| 🆓 100% free | Runs on Google Colab T4 GPU, zero cost |

---

## 🚀 Quick Start (Local)

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 2. Install backend dependencies
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# 3. Start backend
uvicorn backend.app.main:app --reload --reload-exclude "storage/*"

# 4. Install & start frontend (new terminal)
cd frontend
npm install
npm run dev

# 5. Open http://localhost:5173
```

---

## ☁️ Deployment (Vercel + Hugging Face)

For a stable, zero-cost public demo deployment, we use **Vercel** for the frontend and a **Hugging Face Docker Space** for the backend.

See [docs/DEPLOY_VERCEL_HF_SPACE.md](docs/DEPLOY_VERCEL_HF_SPACE.md) for the full step-by-step setup.

---

## 🏗️ Architecture

```
Frontend (React + Vite)
  ├── Setup screen        — name, resume, job role, expertise level
  ├── Pre-interview       — camera check, mic check, rules
  ├── Interview screen    — questions, text/audio answers, posture monitor
  └── Results screen      — scorecard, skill analysis, charts, suggestions

Backend (FastAPI)
  ├── Resume parsing      — pdfplumber + regex + spaCy NER
  ├── Interview planner   — expertise-aware, LLM-enhanced question generation
  ├── State machine       — intro → project → technical → followup → wrapup
  ├── Scoring             — all-mpnet-base-v2 cosine similarity + TF-IDF
  ├── ASR                 — Whisper large-v3-turbo (chunked, accent-robust)
  ├── Filler detection    — transcript post-processing (no extra model)
  ├── Posture             — browser-side MediaPipe, backend receives snapshots
  ├── Anti-cheat          — violation logging endpoint
  └── Unified report      — single endpoint returns full scorecard
```

---

## 🤖 Models Used

| Component | Model | Why |
|---|---|---|
| Embeddings | `all-mpnet-base-v2` | Best MTEB scores in its size class, 110M params |
| ASR | `whisper-large-v3-turbo` | 8× faster than large-v3, near-identical accuracy, accent robust |
| Pose detection | MediaPipe BlazePose JS | Runs in browser at 30fps, no server cost, 33 keypoints |
| Question generation | `Qwen2.5-7B-Instruct` (optional) | Best free 7B instruction model in 2025 |
| Resume parsing | `pdfplumber` + regex | Fast, no OCR model needed for digital PDFs |

---

## 📁 Project Structure

```
├── backend/app/
│   ├── main.py
│   ├── core/
│   │   ├── ml_models.py          # mpnet + Whisper loaders
│   │   ├── interview_flow.py     # state machine
│   │   ├── interview_reasoning.py
│   │   ├── scoring_config.py
│   │   └── filler_words.py       # filler detection
│   └── api/routes/
│       ├── session.py / session_extra.py
│       ├── upload.py / parse_resume.py
│       ├── interview_plan.py     # LLM + expertise levels
│       ├── score_text.py         # semantic scoring
│       ├── answer_audio.py       # Whisper ASR
│       ├── aggregate_scores.py
│       ├── analytics_report.py
│       ├── final_decision.py
│       ├── posture.py
│       ├── violation.py          # anti-cheat
│       └── report.py             # unified scorecard
├── frontend/src/
│   ├── pages/
│   │   ├── Setup.jsx
│   │   ├── PreInterview.jsx
│   │   ├── Interview.jsx
│   │   └── Results.jsx
│   ├── components/
│   │   └── PostureMonitor.jsx    # MediaPipe BlazePose
│   ├── hooks/
│   │   ├── useInterview.js
│   │   ├── useAntiCheat.js
│   │   └── useAudioRecorder.js
│   └── api/client.js
└── requirements.txt
```

---

## ⚙️ Environment Variables

```env
# Frontend (.env in frontend/)
VITE_API_BASE=http://127.0.0.1:8000/api   # change for production

# Backend (optional)
HF_TOKEN=hf_...   # HuggingFace token for LLM question generation
```

---

## 🗺️ API Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Health check |
| POST | `/api/session/create` | Create session |
| POST | `/api/upload/resume` | Upload PDF resume |
| POST | `/api/parse/resume/{id}` | Parse resume |
| POST | `/api/session/job_description` | Set JD + company |
| POST | `/api/session/candidate_profile` | Set profile + expertise level |
| POST | `/api/interview/plan/{id}` | Generate question plan |
| POST | `/api/session/start_interview` | Start interview |
| POST | `/api/session/next_question` | Get next question |
| POST | `/api/score/text` | Score text answer |
| POST | `/api/answer/audio` | Transcribe + score audio |
| POST | `/api/posture/report` | Save posture snapshot |
| POST | `/api/session/violation` | Log anti-cheat violation |
| POST | `/api/aggregate/{id}` | Aggregate all scores |
| POST | `/api/analytics/{id}` | Generate analytics |
| POST | `/api/decision/{id}` | Final hiring decision |
| GET  | `/api/report/{id}` | Full unified scorecard |
