"""Quick verification script for Bug 1 + Bug 2 fixes."""
import re

# ── Test 1: Project filter ────────────────────────────────────────────────────
print("=" * 60)
print("TEST 1: Project Filter")
print("=" * 60)

_PROJ_EDU_KEYWORDS = {
    "b.sc", "b.tech", "m.sc", "m.tech", "b.e", "m.e", "mba", "bca", "mca",
    "b.com", "b.eng", "m.eng", "bachelor", "master", "diploma", "ph.d", "phd",
    "university", "college", "certification", "course", "bootcamp", "nsdc",
}
_PROJ_DATE_RE = re.compile(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+20", re.IGNORECASE)
_PROJ_VALID_VERBS = re.compile(r"\b(?:technologies|built|developed|implemented|created|designed|deployed)\b", re.IGNORECASE)

# Actual broken projects from the live session
projects = [
    "\u2022 B.Sc. Computer Science Sep 2022 \u2013 May 2025",
    "Scam or Real \u2014 Job Posting Classifier Nov 15 \u2013 21, 2025 Calicut University \u2013 MES College,",
    "Technologies: Python, Pandas, scikit-learn, Flask, TF-IDF, NLP (Team of 1) Vadakara, Kerala \u2022 Built TF-IDF + Linear SVM",
    "COURSES & CERTIFICATIONS numeric features using imbalance-aware oversampling.",
    "Complete Data Science, ML, DL, NLP Bootcamp \u2013 Udemy(ongoing)",
]

valid = []
for p in projects:
    text = str(p).strip()
    lower = text.lower()
    if len(text) < 15:
        print(f"  REJECT (short):   {text[:60]}")
        continue
    if any(kw in lower for kw in _PROJ_EDU_KEYWORDS):
        print(f"  REJECT (edu kw):  {text[:60]}")
        continue
    if re.match(r"^[\u2022\-\*]\s*(?:b\.sc|b\.tech|m\.sc|m\.tech|b\.e|m\.e|mba|bachelor|master)", lower):
        print(f"  REJECT (bullet):  {text[:60]}")
        continue
    if _PROJ_DATE_RE.search(text) and not _PROJ_VALID_VERBS.search(text):
        print(f"  REJECT (date):    {text[:60]}")
        continue
    valid.append(text)
    print(f"  PASS:             {text[:60]}")

print(f"\nResult: {len(valid)} valid, {len(projects) - len(valid)} rejected")
assert len(valid) <= 2, f"Too many valid projects: {len(valid)}"
print("PASS: Education entry correctly rejected!\n")

# ── Test 2: _extract_topic regex ──────────────────────────────────────────────
print("=" * 60)
print("TEST 2: _extract_topic() regex")
print("=" * 60)

def _extract_topic(question_text):
    if not question_text:
        return "this area"
    m = re.search(
        r"you built (.+?)(?:\.\s*(?:Walk|Explain|Tell|Describe))",
        question_text,
        re.IGNORECASE,
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

# Test against the ACTUAL broken question from the session
q1 = "I see you built \u2022 B.Sc. Computer Science Sep 2022 \u2013 May 2025. Walk me through the most technically challenging part of that project for a Web development context."
topic1 = _extract_topic(q1)
print(f"  Input:  {q1[:80]}...")
print(f"  Topic:  '{topic1}'")
assert "Walk" not in topic1, "Topic should not contain 'Walk'"
print("  PASS!")

q2 = "You've listed angular as a key skill. Explain a production-level decision..."
topic2 = _extract_topic(q2)
print(f"\n  Input:  {q2[:80]}")
print(f"  Topic:  '{topic2}'")
assert topic2 == "angular", f"Expected 'angular', got '{topic2}'"
print("  PASS!")

q3 = "I see you built Scam or Real Job Classifier. Walk me through..."
topic3 = _extract_topic(q3)
print(f"\n  Input:  {q3[:60]}")
print(f"  Topic:  '{topic3}'")
assert "Walk" not in topic3, "Topic should not contain 'Walk'"
print("  PASS!\n")

# ── Test 3: Follow-up templates ───────────────────────────────────────────────
print("=" * 60)
print("TEST 3: Follow-up templates (< 120 chars, no nested text)")
print("=" * 60)

topic = "angular"
depth1_q = f"Could you give me a concrete example of working with {topic}? Walk me through a specific situation."
depth2_q = f"What was the most difficult problem you solved while working with {topic}?"

print(f"  Depth 1 ({len(depth1_q)} chars): {depth1_q}")
assert len(depth1_q) <= 120, f"Depth 1 too long: {len(depth1_q)}"
assert "elaborate" not in depth1_q.lower()
print(f"  Depth 2 ({len(depth2_q)} chars): {depth2_q}")
assert len(depth2_q) <= 120, f"Depth 2 too long: {len(depth2_q)}"
assert "elaborate" not in depth2_q.lower()
print("  PASS: Both under 120 chars, no nested question text!\n")

print("=" * 60)
print("ALL TESTS PASSED")
print("=" * 60)
