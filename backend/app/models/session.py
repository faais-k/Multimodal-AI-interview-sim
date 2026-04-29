from enum import Enum


class SessionStatus(str, Enum):
    CREATED = "created"  # Session record created, initial data gathered
    PREFLIGHT_COMPLETE = "preflight_complete"  # Camera/mic checks passed
    QUESTION_ACTIVE = "question_active"  # A question is currently presented to candidate
    ANSWER_PENDING = "answer_pending"  # Candidate is answering (recording/submitting)
    SCORING_PENDING = "scoring_pending"  # Answer being processed (ASR + LLM scoring)
    FOLLOWUP_PENDING = "followup_pending"  # System is preparing follow-up question
    INTERVIEW_COMPLETE = "interview_complete"  # All planned questions answered
    REPORT_GENERATED = "report_generated"  # Final report compiled and stored
