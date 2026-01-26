# backend/app/core/interview_reasoning.py

from typing import List, Optional
from sentence_transformers import util
from backend.app.core.ml_models import encode_sentence


SIMILARITY_THRESHOLD = 0.45  # conservative, avoids false positives


def detect_topic(
    last_answer: str,
    skills: List[str],
    projects: List[str]
) -> Optional[str]:
    """
    Detect what topic the candidate is talking about based on semantic similarity.

    Returns:
        topic (str) or None
    """

    if not last_answer.strip():
        return None

    candidates = []

    for skill in skills:
        candidates.append(("skill", skill))

    for project in projects:
        # keep project text short and meaningful
        candidates.append(("project", project[:120]))

    if not candidates:
        return None

    answer_emb = encode_sentence(last_answer)

    best_topic = None
    best_score = 0.0

    for topic_type, text in candidates:
        text_emb = encode_sentence(text)
        score = util.cos_sim(answer_emb, text_emb).item()

        if score > best_score:
            best_score = score
            best_topic = text

    if best_score >= SIMILARITY_THRESHOLD:
        return best_topic

    return None
