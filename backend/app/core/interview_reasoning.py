"""
Topic detection via semantic similarity.

Imports are lazy to avoid blocking FastAPI startup before models are loaded.
"""

from typing import List, Optional

SIMILARITY_THRESHOLD = 0.45


def detect_topic(
    last_answer: str,
    skills: List[str],
    projects: List[str],
) -> Optional[str]:
    """
    Return the skill or project text most semantically similar to the answer,
    or None if similarity is below threshold.
    """
    if not last_answer.strip():
        return None

    # Lazy imports — models may not be ready at module load time
    from sentence_transformers import util
    from backend.app.core.ml_models import encode_sentence

    candidates = []
    for skill in skills:
        candidates.append(("skill", skill))
    for project in projects:
        if isinstance(project, dict):
            text = project.get("details", project.get("name", ""))
            candidates.append(("project", text[:120]))
        else:
            candidates.append(("project", str(project)[:120]))

    if not candidates:
        return None

    answer_emb = encode_sentence(last_answer)
    candidate_texts = [text for _, text in candidates]
    candidate_embs = encode_sentence(candidate_texts)
    similarities = util.cos_sim(answer_emb, candidate_embs)[0]

    best_idx = int(similarities.argmax().item())
    best_score = float(similarities[best_idx].item())
    best_topic = candidate_texts[best_idx]

    return best_topic if best_score >= SIMILARITY_THRESHOLD else None
