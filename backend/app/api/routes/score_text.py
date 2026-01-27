from fastapi import APIRouter, HTTPException
from pathlib import Path
import json, traceback
from typing import List, Dict, Any

from sentence_transformers import util
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np

from backend.app.core.ml_models import encode_sentence
from backend.app.core.interview_flow import record_answer
from backend.app.core.scoring_config import QUESTION_TYPE_WEIGHTS

router = APIRouter()

# --------------------------------------------------
# Helpers
# --------------------------------------------------

def load_parsed_resume(storage_dir: Path, session_id: str) -> dict:
    p = storage_dir / session_id / "parsed_resume.json"
    if not p.exists():
        raise FileNotFoundError("parsed_resume.json not found")
    return json.loads(p.read_text(encoding="utf-8", errors="ignore"))


def load_interview_state(storage_dir: Path, session_id: str) -> dict:
    p = storage_dir / session_id / "interview_state.json"
    if not p.exists():
        raise FileNotFoundError("interview_state.json not found")
    return json.loads(p.read_text(encoding="utf-8", errors="ignore"))


def find_question_from_state(state: dict, question_id: str) -> dict:
    for t in state.get("turns", []):
        if t["role"] == "interviewer" and t["id"] == question_id:
            return t
    raise FileNotFoundError(f"Question {question_id} not found in interview_state")


def infer_question_type(question_id: str, question_text: str) -> str:
    qid = question_id.lower()

    if qid.startswith("intro"):
        return "self_intro"
    if qid.startswith("project"):
        return "project"
    if qid.startswith("followup"):
        return "followup"
    if qid.startswith("wrapup"):
        return "wrapup"

    # fallback heuristic
    tech_keywords = ["explain", "how", "design", "architecture", "implement"]
    if any(k in question_text.lower() for k in tech_keywords):
        return "technical"

    return "followup"


def build_dynamic_reference_text(
    question_text: str,
    parsed_resume: dict,
    state: dict
) -> str:
    resume_summary = parsed_resume.get("summary", "")
    skills = ", ".join(parsed_resume.get("skills", []))
    projects = " ".join(parsed_resume.get("projects", [])[:2])

    recent_turns = []
    for t in state.get("turns", [])[-6:]:
        recent_turns.append(f"{t['role']}: {t['text']}")

    return f"""
Interview question:
{question_text}

Resume summary:
{resume_summary}

Skills:
{skills}

Projects:
{projects}

Recent interview context:
{' | '.join(recent_turns)}

A strong answer should be clear, relevant, structured, and specific.
"""


def compute_top_matches(reference: str, answer: str, top_k: int = 6):
    try:
        vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        X = vec.fit_transform([reference, answer])
        names = np.array(vec.get_feature_names_out())

        ref_vec = X[0].toarray().ravel()
        ans_vec = X[1].toarray().ravel()

        mask = (ref_vec > 0) & (ans_vec > 0)
        if not np.any(mask):
            return []

        scores = ref_vec * mask
        idx = np.argsort(scores)[::-1][:top_k]

        return [{"token": names[i], "ref_tfidf": round(float(ref_vec[i]), 6)} for i in idx if mask[i]]
    except Exception:
        return []


# --------------------------------------------------
# Endpoint
# --------------------------------------------------

@router.post("/score/text")
async def score_text_answer(payload: dict):
    try:
        session_id = payload.get("session_id")
        question_id = payload.get("question_id")
        answer_text = (payload.get("answer_text") or "").strip()

        if not session_id or not question_id:
            raise HTTPException(400, "session_id and question_id required")
        if not answer_text:
            raise HTTPException(400, "answer_text is empty")

        BASE_DIR = Path(__file__).resolve().parents[4]
        STORAGE_DIR = BASE_DIR / "storage"

        parsed_resume = load_parsed_resume(STORAGE_DIR, session_id)
        state = load_interview_state(STORAGE_DIR, session_id)

        q_turn = find_question_from_state(state, question_id)
        question_text = q_turn["text"]

        # 🔹 infer question type
        qtype = infer_question_type(question_id, question_text)
        config = QUESTION_TYPE_WEIGHTS.get(qtype, {})

        min_score = config.get("min_score", 5.0)
        weight = config.get("weight", 0.2)

        # 🔹 dynamic reference
        ref_text = build_dynamic_reference_text(question_text, parsed_resume, state)

        # embeddings
        sim = util.cos_sim(
            encode_sentence(ref_text),
            encode_sentence(answer_text)
        ).item()

        sim = max(min(sim, 1.0), -1.0)
        raw_score = round(((sim + 1) / 2) * 10, 2)
        weighted_score = round(raw_score * weight, 2)

        needs_review = raw_score < min_score
        top_matches = compute_top_matches(ref_text, answer_text)

        # persist answer
        record_answer(
            STORAGE_DIR,
            session_id,
            question_id,
            question_text,
            answer_text,
            raw_score
        )

        score_obj = {
            "session_id": session_id,
            "question_id": question_id,
            "question_type": qtype,
            "raw_score": raw_score,
            "weighted_score": weighted_score,
            "weight": weight,
            "min_score": min_score,
            "needs_human_review": needs_review,
            "similarity": sim,
            "top_matches": top_matches
        }

        out_dir = STORAGE_DIR / session_id / "scores"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{question_id}.json").write_text(
            json.dumps(score_obj, indent=2),
            encoding="utf-8"
        )

        return {"status": "ok", **score_obj}

    except HTTPException:
        raise
    except Exception:
        print(traceback.format_exc())
        raise HTTPException(500, "Internal error scoring answer")
