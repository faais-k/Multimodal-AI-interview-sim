"""Tests for score_text route, anti-cheat detection, and calibrated scoring."""

import pytest
from backend.app.api.routes.score_text import (
    _calibrate_cosine_score,
    _check_cheating_sync,
    _load_plan,
)


def test_calibrate_cosine_score_monotonicity_and_bounds():
    """Ensure calibrated score produces expected dynamic range without collapse."""
    low_sim_score = _calibrate_cosine_score(0.10)
    mid_sim_score = _calibrate_cosine_score(0.40)
    high_sim_score = _calibrate_cosine_score(0.75)
    perfect_sim_score = _calibrate_cosine_score(0.95)

    assert 1.0 <= low_sim_score <= 3.5
    assert 3.5 <= mid_sim_score <= 7.0
    assert 8.0 <= high_sim_score <= 9.5
    assert 9.5 <= perfect_sim_score <= 10.0
    assert low_sim_score < mid_sim_score < high_sim_score <= perfect_sim_score


def test_check_cheating_sync_direct_copy():
    """Candidate echoing the exact question back must trigger anti-cheat."""
    question = "Can you explain how indexing works in PostgreSQL and its performance trade-offs?"
    answer = "Can you explain how indexing works in PostgreSQL and its performance trade-offs?"

    result = _check_cheating_sync(question, answer)
    assert result is not None
    assert result["is_cheating"] is True
    assert "Plagiarism" in result["reason"]


def test_check_cheating_sync_repetitive_spam():
    """Candidate spamming the same repetitive phrase must trigger anti-cheat."""
    question = "What is database indexing?"
    phrase = "repeat word spam test phrase "
    answer = phrase * 10

    result = _check_cheating_sync(question, answer)
    assert result is not None
    assert result["is_cheating"] is True


def test_check_cheating_sync_legitimate_answer():
    """A genuine distinct answer must not trigger anti-cheat."""
    question = "Can you explain how B-Tree indexes work in PostgreSQL?"
    answer = (
        "In PostgreSQL, a B-Tree index maintains a self-balancing tree structure. "
        "It stores keys in sorted order across leaf pages, allowing log-N lookups, "
        "range scans, and efficient sorting without performing a full sequential scan."
    )

    result = _check_cheating_sync(question, answer)
    assert result is None


def test_load_plan_missing_session():
    """_load_plan returns empty dict rather than raising NameError or FileNotFoundError."""
    plan = _load_plan("non-existent-session-id-999")
    assert plan == {}


def test_find_question_and_skill():
    """_find_question_and_skill correctly finds question and skill in state or plan."""
    from backend.app.api.routes.score_text import _find_question_and_skill

    # Found in questions_asked
    state1 = {
        "questions_asked": [{"id": "q1", "question": "What is Python?", "skill_target": "Python"}],
        "turns": []
    }
    q, s = _find_question_and_skill(state1, "q1", "sess-1")
    assert q == "What is Python?"
    assert s == "Python"

    # Found in turns
    state2 = {
        "questions_asked": [],
        "turns": [{"role": "interviewer", "id": "q2", "text": "What is Docker?", "skill_target": "DevOps"}]
    }
    q, s = _find_question_and_skill(state2, "q2", "sess-2")
    assert q == "What is Docker?"
    assert s == "DevOps"

    # Not found anywhere
    state3 = {"questions_asked": [], "turns": []}
    q, s = _find_question_and_skill(state3, "q_missing", "sess-nonexistent")
    assert q == ""
    assert s == ""

