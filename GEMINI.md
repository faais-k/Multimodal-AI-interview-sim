# Gemini AI Context - Ascent AI Interview Simulator

This project is a multimodal AI-powered technical interview simulator featuring resume parsing, anti-cheat monitoring, and intelligent scoring. It uses a hybrid AI scoring mechanism (Cosine similarity + LLM evaluation).

## Project Structure

### 1. Backend (`/backend`)
- **Framework:** FastAPI, Python 3.10+
- **Key Tech:** PyTorch, Transformers, Sentence-Transformers.
- **Core Engine:** `app/core/interview_flow.py` (handles the interview state machine and per-session `asyncio.Lock`).
- **Storage:** Dual storage setup using Flat-file for speed (active) + MongoDB for reports (optional).
- **Setup & Execution:** 
  - Uses `requirements.txt`.
  - Start the backend via: `uvicorn app.main:app --reload --port 8000`.
- **Guidelines:** Follow the split-lock pattern in `interview_flow.py` (`read → ML (unlocked) → write`). Ensure operations are idempotent where possible (like `next_question`).

### 2. Frontend (`/frontend`)
- **Framework:** React 19, Vite.
- **Key Tech:** Tailwind CSS, Framer Motion, Firebase Auth, MediaPipe Tasks Vision, WebRTC.
- **State Recovery:** `sessionStorage` is used heavily for page refresh safe state recovery alongside `/api/session/status` backend sync.
- **Setup & Execution:**
  - Install dependencies via `npm install`.
  - Start the frontend via: `npm run dev` (runs on `http://localhost:5173`).
- **Guidelines:** Use class-based CSS architecture combined with Tailwind. Ensure high-performance animations and cross-device responsiveness.

### 3. Knowledge Graph (`/graphify-out`)
This directory contains a generated knowledge graph representing the codebase abstractions, communities, and dependencies.
- **`GRAPH_REPORT.md`**: Textual analysis of the codebase, highlighting critical "God Nodes" (e.g., `SessionStatus`, `validate_session_id()`, `get_storage_dir()`, `score_text_answer()`) and code community clusters. Refer to this to understand the relationships and dependencies between different backend modules.
- **`graph.json` & `graph.html`**: Data and visualization of the codebase knowledge graph.

## Development Rules
- **Aesthetics First:** Frontend changes should feel premium, dynamic, and state-of-the-art.
- **Resilience:** The backend must handle LLM fallbacks gracefully. The frontend must handle disconnects and tab switches cleanly.
- **Security:** Do not bypass Firebase Auth verification or anti-cheat triggers (posture monitoring, tab-switch detection, face-presence validation) without explicit instructions.
