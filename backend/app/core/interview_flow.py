"""
Interview State Machine.

All state lives in storage/<session_id>/interview_state.json.
Every mutating function reads → modifies → writes atomically within a single request.

P4-B: Per-session asyncio.Lock guards all read_state / write_state pairs.
      Route handlers MUST acquire get_state_lock(session_id) before calling
      read_state() or write_state().

P2-A: _llm_generate_followup() generates specific follow-ups using what_was_missing
      from the last LLM evaluation. Falls back to templates if LLM unavailable.

P3-C: followup_cache in interview_plan.json is checked before LLM runtime call.
"""

import asyncio
import json
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

STATE_FILE            = "interview_state.json"
DEFAULT_MAX_FOLLOWUPS = 5

# ── P4-B: Per-session state file lock ─────────────────────────────────────────

_state_locks:       dict = {}
_state_locks_mutex = threading.Lock()
_MAX_LOCKS = 10000  # Prevent unbounded growth


def _cleanup_old_locks():
    """Remove locks for sessions that no longer exist on disk."""
    global _state_locks
    with _state_locks_mutex:
        if len(_state_locks) > _MAX_LOCKS:
            # Simple LRU: clear oldest half when exceeding limit
            keys_to_remove = list(_state_locks.keys())[:_MAX_LOCKS // 2]
            for key in keys_to_remove:
                del _state_locks[key]


def _get_state_lock(session_id: str) -> asyncio.Lock:
    _cleanup_old_locks()
    with _state_locks_mutex:
        if session_id not in _state_locks:
            _state_locks[session_id] = asyncio.Lock()
        return _state_locks[session_id]


def get_state_lock(session_id: str) -> asyncio.Lock:
    """Return the per-session asyncio.Lock for interview_state.json.

    Route handlers (score_text, session) MUST wrap their read_state → write_state
    sequences with:
        async with interview_flow.get_state_lock(session_id):
            state = interview_flow.read_state(...)
            ...
            interview_flow.write_state(...) / interview_flow.record_answer(...)
    """
    return _get_state_lock(session_id)


# ── Path helpers ───────────────────────────────────────────────────────────────

def _session_dir(storage_dir: Path, session_id: str) -> Path:
    return storage_dir / session_id

def _state_path(storage_dir: Path, session_id: str) -> Path:
    return _session_dir(storage_dir, session_id) / STATE_FILE

def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"

def _safe_id(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", text.strip().lower())[:40]


# ── State I/O ──────────────────────────────────────────────────────────────────
import os
import tempfile

def read_state(storage_dir: Path, session_id: str) -> Dict[str, Any]:
    path = _state_path(storage_dir, session_id)
    if not path.exists():
        raise FileNotFoundError(
            "interview_state.json not found. Call /api/session/start_interview first."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def write_state(storage_dir: Path, session_id: str, state: Dict[str, Any]) -> None:
    """
    Atomically write state to disk using temp file + rename.
    
    This ensures that even if the process crashes during write,
    the existing state file remains intact (or the temp file is cleaned up).
    """
    target_path = _state_path(storage_dir, session_id)
    session_dir = _session_dir(storage_dir, session_id)
    
    # Ensure session directory exists
    session_dir.mkdir(parents=True, exist_ok=True)
    
    # Create temp file in same directory for atomic rename
    fd, temp_path = tempfile.mkstemp(
        dir=session_dir,
        prefix=f".interview_state_{session_id}_",
        suffix=".tmp"
    )
    try:
        # Write to temp file
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        
        # Atomic rename (POSIX guarantees atomicity for rename within same filesystem)
        os.replace(temp_path, target_path)
    except Exception:
        # Clean up temp file on error
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def _last_candidate_turn(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for turn in reversed(state.get("turns", [])):
        if turn.get("role") == "candidate":
            return turn
    return None


def _store_question(state: Dict[str, Any], q: Dict[str, Any]) -> None:
    state["questions_asked"].append({
        "id":           q["id"],
        "question":     q["question"],
        "skill_target": q.get("skill_target", ""),
        "is_final":     bool(q.get("is_final", False)),
        "time":         _now(),
    })
    state["turns"].append({
        "role":         "interviewer",
        "id":           q["id"],
        "text":         q["question"],
        "skill_target": q.get("skill_target", ""),
        "is_final":     bool(q.get("is_final", False)),
        "time":         _now(),
    })


# ── Initialise ─────────────────────────────────────────────────────────────────

def init_interview_state(
    storage_dir: Path,
    session_id: str,
    parsed_resume: dict,
    job_role: Optional[str] = None,
) -> dict:
    _session_dir(storage_dir, session_id).mkdir(parents=True, exist_ok=True)

    plan_path     = _session_dir(storage_dir, session_id) / "interview_plan.json"
    max_followups = DEFAULT_MAX_FOLLOWUPS
    if plan_path.exists():
        try:
            plan          = json.loads(plan_path.read_text(encoding="utf-8"))
            max_followups = plan.get("max_followups", DEFAULT_MAX_FOLLOWUPS)
        except Exception:
            pass

    # P1-D: Read expertise_level from candidate_profile.json if available
    profile_path    = _session_dir(storage_dir, session_id) / "candidate_profile.json"
    expertise_level = "intermediate"
    if profile_path.exists():
        try:
            prof            = json.loads(profile_path.read_text(encoding="utf-8"))
            expertise_level = prof.get("expertise_level", "intermediate")
        except Exception:
            pass

    state: Dict[str, Any] = {
        "session_id":     session_id,
        "job_role":       job_role,
        "completed":      False,
        "wrapup_asked":   False,
        "followup_count": 0,
        "max_followups":  max_followups,
        "followup_depth": {},
        "candidate": {
            "name":            parsed_resume.get("name"),
            "email":           parsed_resume.get("email"),
            "skills":          parsed_resume.get("skills", []),
            "projects":        parsed_resume.get("projects", []),
            "summary":         parsed_resume.get("summary", ""),
            "expertise_level": expertise_level,   # P1-D
        },
        "cursor": {
            "stage":            "intro",
            "last_question_id": None,
            "current_topic":    None,
        },
        "questions_asked": [],
        "answers":         {},
        "turns":           [],
    }
    write_state(storage_dir, session_id, state)
    return state


# ── Record answer ──────────────────────────────────────────────────────────────

def record_answer(
    storage_dir: Path,
    session_id: str,
    question_id: str,
    question_text: str,
    answer_text: str,
    score: Optional[float] = None,
    detected_topic: str | None = None,
) -> bool:
    """Record answer and update interview stage.
    
    Returns True if interview is now COMPLETED, False otherwise.
    """
    state = read_state(storage_dir, session_id)

    state["answers"][question_id] = {
        "question": question_text,
        "answer":   answer_text,
        "score":    score,
        "time":     _now(),
    }
    state["turns"].append({
        "role":  "candidate",
        "id":    question_id,
        "text":  answer_text,
        "score": score,
        "time":  _now(),
    })

    if detected_topic:
        state["cursor"]["current_topic"] = detected_topic

    # Advanced Stage Logic
    # 1. If it's a follow-up, don't advance the main stage
    if not question_id.startswith("followup"):
        current_stage = state["cursor"].get("stage", "intro")
        
        # Robust stage progression
        if current_stage == "intro":
            state["cursor"]["stage"] = "project"
        elif current_stage == "project":
            state["cursor"]["stage"] = "technical"
        elif current_stage == "technical" and question_id.startswith("wrapup"):
            # If we were in technical and just answered wrapup, we stay in technical
            # (or move to a hypothetical 'end' stage), but 'completed' is what matters.
            pass

    state["cursor"]["last_question_id"] = question_id

    # Check is_final from interviewer turns OR questions_asked
    asked_question = None
    for turn in reversed(state.get("turns", [])):
        if turn.get("role") == "interviewer" and turn.get("id") == question_id:
            asked_question = turn
            break
    if asked_question is None:
        for q in reversed(state.get("questions_asked", [])):
            if q.get("id") == question_id:
                asked_question = q
                break

    # Completion check
    # Only complete if: (1) the answered question is marked is_final, or (2) it's a wrapup question
    # AND we should verify that we've actually gone through the interview flow
    questions_asked_count = len(state.get("questions_asked", []))
    minimum_questions_before_completion = 5  # intro + project + at least 3 more
    
    if ((asked_question and asked_question.get("is_final") is True) or question_id.startswith("wrapup")) and questions_asked_count >= minimum_questions_before_completion:
        state["completed"] = True

    write_state(storage_dir, session_id, state)
    return state["completed"]


# ── Follow-up helpers ──────────────────────────────────────────────────────────

def _extract_topic(question_text: str) -> str:
    """Extract a short topic phrase from a full question string."""
    if not question_text:
        return "this area"
    m = re.search(
        r"you built (.+?)(?:\.\s*(?:Walk|Explain|Tell|Describe))",
        question_text, re.IGNORECASE,
    )
    if m:
        topic = m.group(1).strip().lstrip("\u2022 ").lstrip("- ")
        return topic[:100] if topic else "this area"
    m = re.search(r"you(?:'ve)?\s+listed\s+(.+?)\s+as\b", question_text, re.IGNORECASE)
    if m:
        topic = m.group(1).strip().lstrip("\u2022 ").lstrip("- ")
        return topic[:100] if topic else "this area"
    words = question_text.split()[:6]
    return " ".join(words) + ("..." if len(question_text.split()) > 6 else "")


def _find_original_question(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Walk questions_asked backwards to find the last non-followup question.

    Ensures follow-up questions always reference the ORIGINAL question's topic,
    not a previous follow-up's expanded text.
    """
    for q in reversed(state.get("questions_asked", [])):
        if not str(q.get("id", "")).startswith("followup"):
            return q
    return None


def _llm_generate_followup(
    original_question: str,
    candidate_answer: str,
    what_was_missing: str,
    topic: str,
    depth: int,
) -> Optional[str]:
    """Generate a specific, contextual follow-up question using the LLM.

    Returns the question string, or None if LLM unavailable or validation fails.
    Never exceeds 150 characters. Falls back to templates on failure.
    """
    try:
        from backend.app.core.ml_models import get_llm_model, llm_generate

        model, _ = get_llm_model()
        if model is None:
            return None

        depth_instruction = (
            "Ask for a concrete real-world example from their experience."
            if depth <= 1 else
            "Ask about the hardest technical challenge they faced with this topic."
        )

        missing_context = (
            f"The evaluator noted this was missing: {what_was_missing}"
            if what_was_missing and what_was_missing.lower() not in ("none", "")
            else "The answer lacked technical depth."
        )

        prompt = f"""You are a technical interviewer generating ONE follow-up question.

ORIGINAL QUESTION: {original_question}
TOPIC/SKILL: {topic}
{missing_context}
CANDIDATE ANSWER SUMMARY: {candidate_answer[:200]}

Generate exactly ONE specific follow-up question that:
- Addresses what was missing
- Is under 120 characters
- Starts directly with the question (no preamble like "Great, now tell me...")
- {depth_instruction}
- Does NOT repeat the original question
- Does NOT embed the original question text inside it

Respond with ONLY the question, nothing else."""

        q = llm_generate(prompt, max_new_tokens=80, temperature=0.0).strip()

        # Validate output
        if not q or len(q) > 150:
            return None
        q = q.strip("\"'")
        if not q.endswith("?"):
            q = q + "?"
        # Reject if it accidentally quotes the original question
        if original_question[:40].lower() in q.lower():
            return None
        return q

    except Exception:
        return None


def should_ask_followup(state: Dict[str, Any]) -> bool:
    if state.get("followup_count", 0) >= state.get("max_followups", DEFAULT_MAX_FOLLOWUPS):
        return False
    last_turn = _last_candidate_turn(state)
    if not last_turn:
        return False
    if last_turn.get("skipped") is True or str(last_turn.get("text", "")).strip().lower() == "skipped":
        return False
    # Do not follow up on wrapup or self_intro questions — they mark end-of-interview
    # or opening greetings. Following up on these prevents finalization.
    last_qid_check = state.get("cursor", {}).get("last_question_id", "")
    if last_qid_check.startswith("wrapup") or last_qid_check.startswith("intro"):
        return False
    score = last_turn.get("score")
    text  = last_turn.get("text", "")
    if score is not None and score < 6.5:
        return True
    if len(text.split()) < 30:
        return True
    return False


def generate_followup_question(
    state:           Dict[str, Any],
    original_q:      Optional[Dict[str, Any]],
    depth:           int,
    storage_dir:     Path,
    session_id:      str,
    what_was_missing: str = "",
) -> Optional[Dict[str, Any]]:
    """Generate a follow-up question, trying three sources in order:

    1. followup_cache in interview_plan.json (pre-generated at setup time)  — fastest
    2. LLM runtime generation using what_was_missing                         — best quality
    3. Template strings (depth 1 / depth 2)                                  — always available

    Never embeds previous question text. Never exceeds 120 characters.
    """
    if original_q is None:
        return None

    topic = (
        original_q.get("skill_target")
        or _extract_topic(original_q.get("question", ""))
    )
    if not topic or topic in ("self_intro", "project_experience", "wrapup", "collaboration"):
        topic = _extract_topic(original_q.get("question", ""))
    topic = topic.lstrip("\u2022 ").lstrip("- ").strip()
    if not topic:
        topic = "this area"

    asked      = {t["text"].lower() for t in state["turns"] if t["role"] == "interviewer"}
    safe_topic = _safe_id(topic)
    original_q_id = original_q.get("id", "")

    q_text: Optional[str] = None

    # ── P3-C: Check pre-generated cache first ────────────────────────────────
    plan_path = storage_dir / session_id / "interview_plan.json"
    if plan_path.exists() and depth <= 1:
        try:
            plan_data = json.loads(plan_path.read_text(encoding="utf-8"))
            cache = plan_data.get("followup_cache", {})
            if original_q_id in cache:
                cached_q = cache[original_q_id]
                # Return question key for caller to handle cache deletion
                q_text = cached_q
                cache_key = original_q_id
                # We'll handle cache deletion in the caller under proper lock
                return {
                    "question": q_text,
                    "type": "followup",
                    "id": f"followup_{int(time.time())}",
                    "cache_key": cache_key
                }
        except Exception:
            pass

    # ── P2-A: LLM runtime generation (if cache miss) ─────────────────────────
    if q_text is None:
        last_turn   = _last_candidate_turn(state)
        last_answer = (last_turn or {}).get("text", "")
        q_text = _llm_generate_followup(
            original_question=original_q.get("question", ""),
            candidate_answer=last_answer,
            what_was_missing=what_was_missing,
            topic=topic,
            depth=depth,
        )

    # ── Template fallback ─────────────────────────────────────────────────────
    if q_text is None:
        if depth <= 1:
            q_text = (
                f"Could you give me a concrete example of working with {topic}? "
                f"Walk me through a specific situation."
            )
        else:
            q_text = f"What was the most difficult problem you solved while working with {topic}?"

    # Trim to 120 chars max
    if len(q_text) > 120:
        q_text = q_text[:117] + "..."

    if q_text.lower() in asked:
        return None

    state["followup_count"] = state.get("followup_count", 0) + 1
    return {
        "id":           f"followup_{safe_topic}_{len(state['turns'])}",
        "type":         "followup",
        "question":     q_text,
        "skill_target": topic,
        "meta":         {"topic": topic, "depth": depth},
    }



# ── Split-lock next_question helpers (Bug 2 fix) ───────────────────────────────
# These two functions replace decide_next_question in the next_question route.
# _decide_next_read:  reads state, returns a decision dict — NO writes, NO LLM.
# _decide_next_write: accepts decision + resolved text, writes to state — one write_state call.
# decide_next_question (below) is preserved unchanged for the session restore path.

def _decide_next_read(storage_dir: Path, session_id: str, plan: dict) -> dict:
    """Read state and return a decision dict. No writes. No LLM calls.

    Returns one of:
      {"action": "completed",       "payload": {...}}
      {"action": "awaiting_wrapup", "payload": {...}}
      {"action": "followup",        "original_q": {...}, "depth": int,
                                    "what_was_missing": str, "last_answer": str,
                                    "cached_q_text": str|None, "original_q_id": str}
      {"action": "serve_question",  "question": {...}}
    """
    state = read_state(storage_dir, session_id)
    stage = state["cursor"]["stage"]

    if state.get("completed"):
        return {"action": "completed",
                "payload": {"status": "completed",
                             "message": "Interview complete. Thank you for your time!"}}

    last_qid = state["cursor"].get("last_question_id") or ""
    # Determine last-asked question type to skip followups on wrapup/intro
    last_q_type = ""
    for t in reversed(state.get("turns", [])):
        if t.get("role") == "interviewer" and t.get("id") == last_qid:
            last_q_type = t.get("skill_target", "") or ""
            break
    skip_followup = (
        (stage == "project" and last_qid.startswith("intro"))
        or last_qid.startswith("wrapup")
        or last_q_type in ("wrapup", "self_intro")
        or state.get("completed", False)
    )

    if not skip_followup and should_ask_followup(state):
        original_q    = _find_original_question(state)
        original_q_id = (original_q or {}).get("id", "unknown")
        state.setdefault("followup_depth", {})
        current_depth = state["followup_depth"].get(original_q_id, 0)

        if current_depth < 2 and original_q:
            # Read what_was_missing from last score file — no write
            what_was_missing = ""
            safe_last = re.sub(r"[^a-zA-Z0-9_\-]", "_", last_qid)[:80]
            last_score_path = storage_dir / session_id / "scores" / f"{safe_last}.json"
            if last_score_path.exists():
                try:
                    ls = json.loads(last_score_path.read_text(encoding="utf-8"))
                    what_was_missing = (ls.get("llm_evaluation") or {}).get("what_was_missing", "") or ""
                except Exception:
                    pass

            # Check cache — READ ONLY, do NOT consume/delete here
            cached_q_text = None
            plan_path = storage_dir / session_id / "interview_plan.json"
            if plan_path.exists() and current_depth == 0:
                try:
                    plan_data = json.loads(plan_path.read_text(encoding="utf-8"))
                    cached_q_text = plan_data.get("followup_cache", {}).get(original_q_id)
                except Exception:
                    pass

            last_turn   = _last_candidate_turn(state)
            last_answer = (last_turn or {}).get("text", "")

            return {
                "action":           "followup",
                "original_q":       original_q,
                "original_q_id":    original_q_id,
                "depth":            current_depth + 1,
                "what_was_missing": what_was_missing,
                "last_answer":      last_answer,
                "cached_q_text":    cached_q_text,
            }

    plan_questions    = plan.get("questions", [])
    intro_from_plan   = next((q for q in plan_questions if q.get("id") == "intro_1"), None)
    project_from_plan = next((q for q in plan_questions if q.get("id") == "project_1"), None)

    if stage == "intro":
        q = dict(intro_from_plan) if intro_from_plan else _make_question(
            "intro_1", "self_intro",
            f"Hi {state['candidate'].get('name') or 'there'}! Please introduce yourself — "
            "your background, key skills, and what draws you to this role.",
            skill_target="self_intro",
        )
        return {"action": "serve_question", "question": q}

    if stage == "project":
        q = dict(project_from_plan) if project_from_plan else _make_question(
            "project_1", "project",
            "Walk me through your most significant project — your role, the problem, "
            "the tech stack, and a specific challenge you overcame.",
            skill_target="project_experience",
        )
        return {"action": "serve_question", "question": q}

    asked_ids = {q["id"] for q in state["questions_asked"]}
    for q in plan_questions:
        if q.get("id") not in asked_ids:
            next_q = dict(q)
            if next_q.get("type") == "wrapup" or str(next_q.get("id", "")).startswith("wrapup"):
                next_q["is_final"] = True
            return {"action": "serve_question", "question": next_q}

    if not state.get("wrapup_asked"):
        company = plan.get("company", "")
        co_ctx  = f" for this role at {company}" if company else ""
        q = _make_question(
            f"wrapup_{len(state['questions_asked'])}",
            "wrapup",
            f"Before we wrap up — is there anything else you'd like to share{co_ctx}?",
            skill_target="wrapup",
        )
        q["is_final"] = True
        return {"action": "serve_question", "question": q}

    return {"action": "awaiting_wrapup",
            "payload": {"status": "awaiting_wrapup_answer",
                        "message": "Please submit your answer to complete the interview."}}


def _decide_next_write(
    storage_dir: Path,
    session_id: str,
    plan: dict,
    decision: dict,
    resolved_q_text: str = None,
) -> dict:
    """Write the decided question to state and return it.

    This is the ONLY function that calls write_state() in the next_question flow.
    For followup actions: consumes/deletes the cache entry if it was pre-generated.
    """
    state  = read_state(storage_dir, session_id)
    action = decision["action"]

    if action in ("completed", "awaiting_wrapup"):
        return decision["payload"]

    if action == "followup":
        original_q    = decision["original_q"]
        original_q_id = decision["original_q_id"]
        depth         = decision["depth"]

        topic = (
            original_q.get("skill_target")
            or _extract_topic(original_q.get("question", ""))
        )
        topic = topic.lstrip("\u2022 ").lstrip("- ").strip() or "this area"
        safe_topic = _safe_id(topic)

        asked = {t["text"].lower() for t in state["turns"] if t["role"] == "interviewer"}
        if resolved_q_text and resolved_q_text.lower() in asked:
            # Already asked — skip this follow-up silently
            return {"status": "completed", "message": "No new follow-up available."}

        q = {
            "id":           f"followup_{safe_topic}_{len(state['turns'])}",
            "type":         "followup",
            "question":     resolved_q_text,
            "skill_target": topic,
            "meta":         {"topic": topic, "depth": depth},
        }

        # Consume cache entry if the cached text was the one used
        if decision.get("cached_q_text") and resolved_q_text == decision["cached_q_text"]:
            plan_path = storage_dir / session_id / "interview_plan.json"
            try:
                plan_data = json.loads(plan_path.read_text(encoding="utf-8"))
                cache = plan_data.get("followup_cache", {})
                cache.pop(original_q_id, None)
                plan_data["followup_cache"] = cache
                plan_path.write_text(json.dumps(plan_data, indent=2), encoding="utf-8")
            except Exception:
                pass

        state.setdefault("followup_depth", {})
        state["followup_depth"][original_q_id] = depth
        state["followup_count"] = state.get("followup_count", 0) + 1
        _store_question(state, q)
        write_state(storage_dir, session_id, state)
        return q

    if action == "serve_question":
        q = decision["question"]
        if q.get("type") == "wrapup" or str(q.get("id", "")).startswith("wrapup"):
            q["is_final"] = True
            state["wrapup_asked"] = True
        _store_question(state, q)
        write_state(storage_dir, session_id, state)
        return q

    return {"status": "error", "message": f"Unknown action: {action}"}

# ── Question factory ───────────────────────────────────────────────────────────

def _make_question(
    qid: str, qtype: str, question: str,
    skill_target: str = "",
    meta: Optional[dict] = None,
) -> Dict[str, Any]:
    return {
        "id":           qid,
        "type":         qtype,
        "question":     question,
        "skill_target": skill_target,
        "meta":         meta or {},
    }


# ── Main decision engine ───────────────────────────────────────────────────────

def decide_next_question(
    storage_dir: Path, session_id: str, plan: dict
) -> Dict[str, Any]:
    state = read_state(storage_dir, session_id)
    stage = state["cursor"]["stage"]

    if state.get("completed"):
        return {"status": "completed", "message": "Interview complete. Thank you for your time!"}

    name     = state["candidate"].get("name") or "there"
    projects = state["candidate"].get("projects", [])

    # ── Follow-up gate ────────────────────────────────────────────────────────
    last_qid = state["cursor"].get("last_question_id") or ""
    last_q_type_old = ""
    for t in reversed(state.get("turns", [])):
        if t.get("role") == "interviewer" and t.get("id") == last_qid:
            last_q_type_old = t.get("skill_target", "") or ""
            break
    skip_followup_now = (
        (stage == "project" and last_qid.startswith("intro"))
        or last_qid.startswith("wrapup")
        or last_q_type_old in ("wrapup", "self_intro")
        or state.get("completed", False)
    )

    if not skip_followup_now and should_ask_followup(state):
        original_q    = _find_original_question(state)
        original_q_id = (original_q or {}).get("id", "unknown")

        state.setdefault("followup_depth", {})
        current_depth = state["followup_depth"].get(original_q_id, 0)

        if current_depth < 2 and original_q:
            # P2-A: Read what_was_missing from the last score file
            what_was_missing = ""
            safe_last = re.sub(r"[^a-zA-Z0-9_\-]", "_", last_qid)[:80]
            last_score_path  = storage_dir / session_id / "scores" / f"{safe_last}.json"
            if last_score_path.exists():
                try:
                    last_score       = json.loads(last_score_path.read_text(encoding="utf-8"))
                    llm_eval         = last_score.get("llm_evaluation") or {}
                    what_was_missing = llm_eval.get("what_was_missing", "") or ""
                except Exception:
                    pass

            q = generate_followup_question(
                state=state,
                original_q=original_q,
                depth=current_depth + 1,
                storage_dir=storage_dir,
                session_id=session_id,
                what_was_missing=what_was_missing,
            )
            if q:
                state["followup_depth"][original_q_id] = current_depth + 1
                _store_question(state, q)
                
                # Handle cache deletion under same lock
                if "cache_key" in q:
                    plan_path = storage_dir / session_id / "interview_plan.json"
                    try:
                        plan_data = json.loads(plan_path.read_text(encoding="utf-8"))
                        cache = plan_data.get("followup_cache", {})
                        if q["cache_key"] in cache:
                            del cache[q["cache_key"]]
                            plan_data["followup_cache"] = cache
                            plan_path.write_text(json.dumps(plan_data, indent=2), encoding="utf-8")
                    except Exception:
                        pass  # Cache deletion failed but question was already stored
                
                write_state(storage_dir, session_id, state)
                return q

    plan_questions     = plan.get("questions", [])
    intro_from_plan    = next((q for q in plan_questions if q.get("id") == "intro_1"), None)
    project_from_plan  = next((q for q in plan_questions if q.get("id") == "project_1"), None)

    # ── Intro (once) ──────────────────────────────────────────────────────────
    if stage == "intro":
        if intro_from_plan:
            q = dict(intro_from_plan)
        else:
            job_role = plan.get("job_role", "")
            company  = plan.get("company", "")
            co_ctx   = f" at {company}" if company else ""
            role_ctx = f" {job_role}" if job_role else " role"
            q = _make_question(
                "intro_1", "self_intro",
                f"Hi {name}! Please introduce yourself — your education, key skills, "
                f"and why you're interested in this{role_ctx}{co_ctx}.",
                skill_target="self_intro",
            )
        _store_question(state, q)
        write_state(storage_dir, session_id, state)
        return q

    # ── Project (once) ────────────────────────────────────────────────────────
    if stage == "project":
        if project_from_plan:
            q = dict(project_from_plan)
        else:
            job_role = plan.get("job_role", "")
            text = (
                f"Walk me through one of your most significant projects relevant to "
                f"{job_role or 'this role'}. "
                "Cover your role, the problem you were solving, the tech stack, "
                "and a specific challenge you overcame."
                if projects else
                "I don't see major projects listed. Can you describe any internship, "
                "academic project, or self-learning project you've worked on — "
                "what you built and what you learned?"
            )
            q = _make_question("project_1", "project", text, skill_target="project_experience")
        _store_question(state, q)
        write_state(storage_dir, session_id, state)
        return q

    # ── Plan questions (technical stage) ─────────────────────────────────────
    asked_ids = {q["id"] for q in state["questions_asked"]}
    for q in plan.get("questions", []):
        if q.get("id") not in asked_ids:
            next_q = dict(q)
            if next_q.get("type") == "wrapup" or str(next_q.get("id", "")).startswith("wrapup"):
                next_q["is_final"] = True
            _store_question(state, next_q)
            write_state(storage_dir, session_id, state)
            return next_q

    # ── Wrapup (once) ─────────────────────────────────────────────────────────
    if not state.get("wrapup_asked"):
        company = plan.get("company", "")
        co_ctx  = f" for this role at {company}" if company else ""
        q = _make_question(
            f"wrapup_{len(state['questions_asked'])}",
            "wrapup",
            f"Before we wrap up — is there anything else you'd like to share "
            f"about your experience or skills{co_ctx}?",
            skill_target="wrapup",
        )
        q["is_final"] = True
        state["wrapup_asked"] = True
        _store_question(state, q)
        write_state(storage_dir, session_id, state)
        return q

    return {
        "status":  "awaiting_wrapup_answer",
        "message": "Please submit your answer to complete the interview.",
    }
