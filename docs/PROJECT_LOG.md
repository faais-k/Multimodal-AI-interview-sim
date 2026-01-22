# PROJECT LOG � Multimodal AI Interview Simulator

## Project title
Multimodal AI Interview Simulator (backend + frontend + posture detection + scoring + resume parsing)

## Project summary
An interview simulation platform that:
- Parses candidate resumes
- Generates an interview plan
- Conducts interactive AI-driven interviews (text/audio)
- Scores answers with sentence-transformer embeddings + TF-IDF explainability
- Provides posture detection and live suggestions
- Persists step-by-step logs and scores for review

---

## Chronological log (high-level)
### 2026-01-XX � Project start & initial setup
- Created repo, initial FastAPI skeleton.
- Implemented session creation, resume upload endpoints.

### Implemented features (dates approximate)
- Resume parsing (`parse_resume.py`)
- Interview plan generation (`interview_plan.py`)
- Answer endpoints (`/api/answer/audio`, `/api/answer/text`)
- Scoring: sentence-transformers, TF-IDF explainability (`score_text.py`)
- Centralized model loading (`ml_models.py`)
- Posture endpoint skeleton (`posture.py`) to receive client metrics
- Frontend skeleton created with Vite (React) � Node version noted

---

## Errors encountered & solutions
- **ImportError: PipelineException from transformers**  
  _Cause:_ wrong import name; transformers API changed.  
  _Fix:_ import pipeline only and handle exceptions generically or use correct exception types.

- **UTF-8 decode error when reading resume**  
  _Cause:_ resume text had weird bytes.  
  _Fix:_ used `read_text(..., errors="ignore")` while parsing.

- **SentenceTransformer not loaded at request time (uvicorn --reload)**  
  _Cause:_ model loading expected during startup; reload process timing caused requests before model load.  
  _Fix:_ made `ml_models` lazy-load and thread-safe (fall-back loads in endpoints).

- **Docs UI stuck/hanging in dev**  
  _Cause:_ startup/lifespan issues or long blocking model loads.  
  _Fix:_ moved heavy model loads to be lazy or in lifespan but with safe behavior and debug prints.

- **ASR (Whisper) issues**  
  _Cause:_ transformers pipeline downloads and ffmpeg missing or model size.  
  _Fix:_ added safe imports, user-friendly error messages and saved uploaded file before ASR.

---

## Current status (today)
- Backend endpoints for health, session, upload, parse resume, interview plan, answer audio, scoring, posture are implemented and tested via `curl`.
- Frontend scaffold created; Vite warns node version (upgrade recommended).
- Logging and persistent storage in `storage/<session_id>/` is present for parsed resumes, plans, scores, posture logs.

---

## Next planned steps
1. Implement backend interview flow state machine (done).
2. Integrate `start_interview` and `next_question` endpoints (done).
3. Implement client-side posture detection using MediaPipe & reporting endpoint (pending).
4. Build frontend UI that orchestrates session -> upload -> parse -> interview -> posture -> show score.

---

## How to update this document programmatically
A helper script `tools/update_log.py` adds timestamped entries to the bottom.


### 2026-01-22T07:14:00.298792Z � Test entry

