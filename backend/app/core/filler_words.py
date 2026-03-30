"""
Filler word detection.

"so" and "right" removed from discourse fillers — both are normal in technical
speech ("So, I built..." / "The right approach is...") and inflate filler counts.
"""

import re
from typing import Any, Dict, List

FILLERS: Dict[str, List[str]] = {
    "hesitation": ["um", "uh", "er", "eh", "hmm", "uhh", "umm", "ahh", "ah"],
    "discourse":  [
        "like", "you know", "i mean", "basically",
        "literally", "actually", "honestly", "obviously", "clearly",
        "kind of", "sort of", "you see",
    ],
    "repetition_starters": ["i think i think", "so so", "and and", "but but"],
}

_ALL_FILLERS: set = set()
for _group in FILLERS.values():
    for _f in _group:
        _ALL_FILLERS.add(_f.lower())


def _normalise(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s']", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def analyse_fillers(transcript: str) -> Dict[str, Any]:
    if not transcript or not transcript.strip():
        return _empty_result()

    norm        = _normalise(transcript)
    words       = norm.split()
    total_words = len(words)

    if total_words == 0:
        return _empty_result()

    counts: Dict[str, int] = {}
    remaining = norm

    # Multi-word fillers first (longer first to avoid partial matches)
    multi = sorted([f for f in _ALL_FILLERS if " " in f], key=len, reverse=True)
    for mf in multi:
        c = len(re.findall(r"\b" + re.escape(mf) + r"\b", remaining))
        if c:
            counts[mf] = c
            remaining = re.sub(r"\b" + re.escape(mf) + r"\b", "", remaining)

    # Single-word fillers
    for w in remaining.split():
        if w in _ALL_FILLERS:
            counts[w] = counts.get(w, 0) + 1

    filler_count  = sum(counts.values())
    filler_ratio  = round(filler_count / total_words, 4)
    fluency_score = round(max(0.0, (1 - filler_ratio * 3)) * 10, 2)
    fluency_score = min(10.0, fluency_score)

    by_category: Dict[str, Dict[str, int]] = {}
    for cat, words_list in FILLERS.items():
        cat_counts = {w: counts[w] for w in words_list if w in counts and counts[w] > 0}
        if cat_counts:
            by_category[cat] = cat_counts

    top_fillers = sorted(
        [{"word": w, "count": c} for w, c in counts.items()],
        key=lambda x: x["count"], reverse=True
    )[:5]

    if filler_ratio < 0.05:
        label    = "EXCELLENT"
        feedback = "Very fluent speech. Minimal use of filler words."
    elif filler_ratio < 0.10:
        label    = "GOOD"
        feedback = "Good fluency. A small number of fillers detected — not distracting."
    elif filler_ratio < 0.18:
        label    = "FAIR"
        feedback = (
            f"Moderate use of filler words ({filler_count} detected). "
            "Practice pausing silently instead of using fillers when thinking."
        )
    else:
        label    = "NEEDS IMPROVEMENT"
        top_w    = top_fillers[0]["word"] if top_fillers else "filler words"
        feedback = (
            f"High use of filler words ({filler_count} in {total_words} words). "
            f"Most common: '{top_w}'. Focus on deliberate pauses and structured answers."
        )

    return {
        "total_words":   total_words,
        "filler_count":  filler_count,
        "filler_ratio":  filler_ratio,
        "fluency_score": fluency_score,
        "fluency_label": label,
        "by_category":   by_category,
        "top_fillers":   top_fillers,
        "feedback":      feedback,
    }


def aggregate_filler_report(per_answer: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not per_answer:
        return {"error": "No filler data available"}

    total_words   = sum(r.get("total_words",  0) for r in per_answer)
    total_fillers = sum(r.get("filler_count", 0) for r in per_answer)
    overall_ratio = round(total_fillers / total_words, 4) if total_words else 0.0

    merged_cats: Dict[str, Dict[str, int]] = {}
    for r in per_answer:
        for cat, words_dict in r.get("by_category", {}).items():
            if cat not in merged_cats:
                merged_cats[cat] = {}
            for w, c in words_dict.items():
                merged_cats[cat][w] = merged_cats[cat].get(w, 0) + c

    all_counts: Dict[str, int] = {}
    for cat_dict in merged_cats.values():
        for w, c in cat_dict.items():
            all_counts[w] = all_counts.get(w, 0) + c

    top_overall = sorted(
        [{"word": w, "count": c} for w, c in all_counts.items()],
        key=lambda x: x["count"], reverse=True
    )[:5]

    avg_fluency = round(
        sum(r.get("fluency_score", 10) for r in per_answer) / len(per_answer), 2
    )

    suggestions = []
    if overall_ratio >= 0.10:
        suggestions.append(
            "Practice the STAR method (Situation, Task, Action, Result) "
            "to structure answers and reduce hesitation."
        )
    if any("um" in r.get("by_category", {}).get("hesitation", {}) for r in per_answer):
        suggestions.append(
            "Replace 'um/uh' with a deliberate 1–2 second pause. "
            "Silence sounds more confident than fillers."
        )
    if any("like" in r.get("by_category", {}).get("discourse", {}) for r in per_answer):
        suggestions.append(
            "'Like' is overused. Record yourself and listen back to become aware of it."
        )

    return {
        "total_words":       total_words,
        "total_fillers":     total_fillers,
        "overall_ratio":     overall_ratio,
        "avg_fluency_score": avg_fluency,
        "by_category":       merged_cats,
        "top_fillers":       top_overall,
        "suggestions":       suggestions,
    }


def _empty_result() -> Dict[str, Any]:
    return {
        "total_words":   0,
        "filler_count":  0,
        "filler_ratio":  0.0,
        "fluency_score": 10.0,
        "fluency_label": "EXCELLENT",
        "by_category":   {},
        "top_fillers":   [],
        "feedback":      "No transcript available.",
    }
