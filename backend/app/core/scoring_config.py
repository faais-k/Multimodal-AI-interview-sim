"""
Question type weights and minimum score thresholds.
Used by score_text.py and aggregate_scores.py.
"""

QUESTION_TYPE_WEIGHTS = {
    "self_intro": {"weight": 0.10, "min_score": 5.0},
    "project":    {"weight": 0.20, "min_score": 6.0},
    "technical":  {"weight": 0.30, "min_score": 6.5},
    "followup":   {"weight": 0.15, "min_score": 6.0},
    "hr":         {"weight": 0.10, "min_score": 5.5},
    "behavioral": {"weight": 0.10, "min_score": 5.5},
    "critical":   {"weight": 0.10, "min_score": 6.0},
    "warmup":     {"weight": 0.05, "min_score": 4.0},
    "wrapup":     {"weight": 0.05, "min_score": 4.0},
}
