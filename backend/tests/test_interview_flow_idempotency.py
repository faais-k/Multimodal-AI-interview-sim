import json
from pathlib import Path

from backend.app.core import interview_flow


def _write_state(tmp_path: Path, session_id: str, state: dict) -> None:
    session_dir = tmp_path / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "interview_state.json").write_text(json.dumps(state), encoding="utf-8")


def test_next_write_returns_existing_active_question_for_concurrent_followup(tmp_path):
    session_id = "session-a"
    active_followup = {
        "id": "followup_python_4",
        "question": "Could you give me a concrete example of working with Python?",
        "skill_target": "Python",
    }
    state = {
        "session_id": session_id,
        "completed": False,
        "cursor": {"stage": "technical", "last_question_id": "technical_1"},
        "questions_asked": [active_followup],
        "answers": {},
        "turns": [
            {
                "role": "interviewer",
                "id": active_followup["id"],
                "text": active_followup["question"],
                "skill_target": "Python",
            }
        ],
    }
    _write_state(tmp_path, session_id, state)

    stale_decision = {
        "action": "followup",
        "original_q": {"id": "technical_1", "question": "Explain Python.", "skill_target": "Python"},
        "original_q_id": "technical_1",
        "depth": 1,
    }

    result = interview_flow._decide_next_write(
        tmp_path,
        session_id,
        {"questions": []},
        stale_decision,
        active_followup["question"],
    )

    assert result["id"] == active_followup["id"]
    assert result["question"] == active_followup["question"]


def test_duplicate_followup_text_uses_alternate_not_completed(tmp_path):
    session_id = "session-b"
    duplicate_text = "Could you give me a concrete example of working with Python?"
    state = {
        "session_id": session_id,
        "completed": False,
        "followup_count": 1,
        "cursor": {"stage": "technical", "last_question_id": "technical_1"},
        "questions_asked": [
            {"id": "technical_1", "question": "Explain Python.", "skill_target": "Python"},
            {"id": "followup_python_2", "question": duplicate_text, "skill_target": "Python"},
        ],
        "answers": {
            "technical_1": {"answer": "Python answer", "score": 5},
            "followup_python_2": {"answer": "Follow-up answer", "score": 5},
        },
        "turns": [
            {"role": "interviewer", "id": "technical_1", "text": "Explain Python."},
            {"role": "candidate", "id": "technical_1", "text": "Python answer", "score": 5},
            {"role": "interviewer", "id": "followup_python_2", "text": duplicate_text},
            {"role": "candidate", "id": "followup_python_2", "text": "Follow-up answer", "score": 5},
        ],
    }
    _write_state(tmp_path, session_id, state)

    decision = {
        "action": "followup",
        "original_q": {"id": "technical_1", "question": "Explain Python.", "skill_target": "Python"},
        "original_q_id": "technical_1",
        "depth": 2,
    }
    plan = {
        "questions": [
            {"id": "technical_1", "type": "technical", "question": "Explain Python."},
            {"id": "technical_2", "type": "technical", "question": "Explain APIs."},
        ]
    }

    result = interview_flow._decide_next_write(
        tmp_path,
        session_id,
        plan,
        decision,
        duplicate_text,
    )

    assert result["id"].startswith("followup_python_")
    assert result["question"] != duplicate_text
    assert "completed" not in result
