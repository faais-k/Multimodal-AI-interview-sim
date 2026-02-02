## 📄 `docs/api_contracts.md`

# API Contract — Multimodal AI Interview Simulator
**Backend v0.1.0**

This document is the **single source of truth** for frontend integration, testing, demos, and future maintenance.



## Global Notes

- Base URL (local): `http://127.0.0.1:8000`
- All endpoints return JSON unless stated otherwise
- Every session-scoped operation **must** include `session_id`
- Backend controls interview flow and state
- Frontend must treat all returned file paths as **opaque**
- Interview lifecycle:


create session
→ upload resume
→ parse resume
→ (optional) job description + candidate profile
→ generate plan
→ start interview
→ next_question ↔ answer + score (loop)
→ aggregate
→ analytics
→ decision





## API Versioning

- Current version: `0.1.0`
- Optional request header:


X-API-Version: 0.1.0


- Breaking changes require major version bump



## 1. Health Check

### GET `/api/health`

**Purpose**
- Verify backend availability
- Used by frontend and CI

**Response 200**
json
{
"status": "ok",
"service": "backend",
"stage": "development"
}




## 2. Session Management

### Create Session

### POST `/api/session/create`

**Purpose**

* Creates a new interview session
* Allocates `storage/<session_id>/`

**Request**

* No body

**Response 200**

json
{
  "session_id": "699d7239-f89b-4d58-b6a3-64a5c5110bce",
  "storage_path": "storage/699d7239-f89b-4d58-b6a3-64a5c5110bce"
}


**Curl**

bash
curl -X POST http://127.0.0.1:8000/api/session/create




## 3. Resume Upload

### POST `/api/upload/resume`

**Purpose**

* Upload candidate resume (PDF/DOCX)

**Request**
`multipart/form-data`

| Field      | Type   | Required |
| ---------- | ------ | -------- |
| session_id | string | yes      |
| file       | file   | yes      |

**Response 200**

json
{
  "status": "ok",
  "filename": "resume.pdf",
  "saved_path": "storage/<session_id>/resumes/resume.pdf",
  "session_id": "<session_id>"
}


**Curl**

bash
curl -F "session_id=<SESSION_ID>" \
     -F "file=@resume.pdf" \
     http://127.0.0.1:8000/api/upload/resume




## 4. Resume Parsing

### POST `/api/parse/resume/{session_id}`

**Purpose**

* Extract name, email, skills from resume

**Response 200**

json
{
  "status": "ok",
  "parsed_path": "storage/<session_id>/parsed_resume.json",
  "skills": ["python", "docker", "machine learning"],
  "email": "candidate@email.com",
  "name": "Candidate Name"
}


**Curl**

bash
curl -X POST http://127.0.0.1:8000/api/parse/resume/<SESSION_ID>




## 5. Job Description (Optional)

### POST `/api/session/job_description`

**Request**

json
{
  "session_id": "<SESSION_ID>",
  "job_role": "Machine Learning Engineer",
  "job_description": "Build ML pipelines, deploy models, integrate with backend APIs"
}


**Response**

json
{
  "status": "ok",
  "path": "storage/<session_id>/job_description.json"
}




## 6. Candidate Profile (Optional)

### POST `/api/session/candidate_profile`

**Request**

json
{
  "session_id": "<SESSION_ID>",
  "experience": "Internships in ML and backend development",
  "education": "BSc Computer Science"
}


**Response**

json
{
  "status": "ok",
  "path": "storage/<session_id>/candidate_profile.json"
}




## 7. Interview Plan Generation

### POST `/api/interview/plan/{session_id}`

**Purpose**

* Generate structured interview plan

**Response**

json
{
  "status": "ok",
  "session_id": "<session_id>",
  "candidate": "Candidate Name",
  "summary": "Machine Learning Engineer",
  "total_questions": 15,
  "plan_path": "storage/<session_id>/interview_plan.json"
}




## 8. Interview Control (State Machine)

### Start Interview

### POST `/api/session/start_interview?session_id=<SESSION_ID>`

**Response**

json
{
  "status": "ok",
  "message": "interview started"
}




### Next Question

### POST `/api/session/next_question?session_id=<SESSION_ID>`

**Response — question**

json
{
  "status": "ok",
  "question": {
    "id": "project_1",
    "type": "project",
    "question": "Explain one of your main projects.",
    "meta": {}
  }
}


**Response — completed**

json
{
  "status": "ok",
  "question": {
    "status": "completed",
    "message": "Interview has ended. Thank you."
  }
}




## 9. Text Answer Scoring

### POST `/api/score/text`

**Request**

json
{
  "session_id": "<SESSION_ID>",
  "question_id": "<QUESTION_ID>",
  "answer_text": "I built ML pipelines using PyTorch and Docker."
}


**Response**

json
{
  "status": "ok",
  "question_id": "<QUESTION_ID>",
  "question_type": "technical",
  "raw_score": 7.1,
  "weighted_score": 2.13,
  "weight": 0.3,
  "min_score": 6.5,
  "needs_human_review": false,
  "similarity": 0.42,
  "top_matches": [
    { "token": "pytorch", "ref_tfidf": 0.26 }
  ],
  "score_path": "storage/<session_id>/scores/<question_id>.json"
}




## 10. Audio Answer Scoring

### POST `/api/answer/audio`

**Request**
`multipart/form-data`

| Field       | Required |
| ----------- | -------- |
| session_id  | yes      |
| question_id | yes      |
| file        | yes      |

**Response**

json
{
  "status": "ok",
  "transcript": "I built models using PyTorch",
  "score": 8.2,
  "similarity": 0.69,
  "needs_human_review": false,
  "audio_path": "storage/<session_id>/answers/<uuid>.wav"
}




## 11. Score Aggregation (Phase 6.1)

### POST `/api/aggregate/{session_id}`

**Response**

json
{
  "status": "ok",
  "final_score": 6.74,
  "needs_human_review": true,
  "report_path": "storage/<session_id>/final_report.json"
}




## 12. Analytics Report (Phase 6.2)

### POST `/api/analytics/{session_id}`

**Response**

json
{
  "status": "ok",
  "analytics_path": "storage/<session_id>/analytics_report.json",
  "readiness_level": "JUNIOR-MID"
}




## 13. Decision Engine (Phase 6.3)

### POST `/api/decision/{session_id}`

**Response**

json
{
  "status": "ok",
  "decision": "BORDERLINE",
  "confidence": 0.67,
  "final_score": 6.74,
  "readiness_level": "JUNIOR-MID",
  "needs_human_review": true,
  "reasons": [
    "Inconsistent answer depth",
    "High-risk skills identified"
  ]
}




## 14. Storage Structure


storage/
└── <session_id>/
    ├── resumes/
    ├── parsed_resume.json
    ├── job_description.json
    ├── candidate_profile.json
    ├── interview_plan.json
    ├── interview_state.json
    ├── answers/
    ├── scores/
    ├── final_report.json
    ├── analytics_report.json
    └── decision.json




## 15. Error Handling

| Code | Meaning                   |
| ---- | ------------------------- |
| 400  | Invalid request           |
| 404  | Session or file not found |
| 500  | Internal server error     |

json
{
  "detail": "Human readable error message"
}




## 16. Frontend Best Practices

1. Never generate questions client-side
2. Always call `next_question` after scoring
3. Treat `needs_human_review` as a blocker flag
4. Never infer decision client-side
5. Backend is authoritative



## 17. Change Log

* **v0.1.0**

  * Session, resume, interview flow
  * Scoring, aggregation, analytics, decision engine


