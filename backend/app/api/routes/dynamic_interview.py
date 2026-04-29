"""
Dynamic Interview Generation — LLM-powered company research and question generation.

This endpoint generates interview questions dynamically using:
1. Company research (via LLM knowledge/simulated Glassdoor-style data)
2. Job role and job description analysis
3. Candidate's resume (skills, projects, education)
4. Difficulty level calibration

Unlike template-based questions, these are unique to each session.
"""

import asyncio
import json
import random
import re
from pathlib import Path
from typing import Dict, List

from fastapi import APIRouter, HTTPException
from backend.app.core.validation import validate_session_id

router = APIRouter()


def _storage_dir() -> Path:
    from backend.app.core.storage import get_storage_dir
    return get_storage_dir()


def _read_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(p: Path, data: dict):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")


async def _research_company(company_name: str, job_role: str) -> Dict:
    """
    Research company using LLM to get interview insights.
    Returns dict with company_focus, common_questions, tech_stack, culture.
    """
    from backend.app.core.ml_models import llm_generate
    
    if not company_name:
        return {
            "company_focus": "general technical skills",
            "common_questions": [],
            "tech_stack_hints": [],
            "interview_style": "standard"
        }
    
    prompt = f"""You are a technical interview researcher. Research {company_name} as an interview candidate for the role of {job_role}.

Provide insights in this exact JSON format (no markdown, no code blocks):
{{
  "company_focus": "2-3 sentences about what this company values in technical interviews for {job_role}",
  "common_questions": ["question 1", "question 2", "question 3"],
  "tech_stack_hints": ["likely tech 1", "likely tech 2"],
  "interview_style": "brief description of their interview style"
}}

Be specific to {company_name} and {job_role}. If unsure about specific questions, provide general but relevant patterns for this type of company and role."""
    
    try:
        raw = await asyncio.to_thread(llm_generate, prompt, max_new_tokens=400, temperature=0.3)
        
        # Extract JSON
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            result = json.loads(match.group(0))
            return {
                "company_focus": result.get("company_focus", ""),
                "common_questions": result.get("common_questions", [])[:3],
                "tech_stack_hints": result.get("tech_stack_hints", []),
                "interview_style": result.get("interview_style", "standard")
            }
    except Exception:
        pass
    
    return {
        "company_focus": f"Technical skills for {job_role}",
        "common_questions": [],
        "tech_stack_hints": [],
        "interview_style": "standard"
    }


def _get_difficulty_guidance(level: str) -> Dict:
    """Get difficulty-specific guidance for question generation."""
    guidance = {
        "fresher": {
            "depth": "fundamental concepts",
            "complexity": "basic to intermediate",
            "focus": "learning approach, projects, fundamentals",
            "avoid": "system design, architecture trade-offs, production scaling"
        },
        "intermediate": {
            "depth": "practical application",
            "complexity": "intermediate to advanced",
            "focus": "real-world problems, debugging, optimization",
            "avoid": "very basic definitions, executive-level strategy"
        },
        "experienced": {
            "depth": "architectural decisions",
            "complexity": "advanced to expert",
            "focus": "system design, trade-offs, scalability, mentoring",
            "avoid": "basic syntax questions, toy problems"
        }
    }
    return guidance.get(level, guidance["fresher"])


async def _generate_dynamic_question(
    q_type: str,
    context: Dict,
    difficulty: str,
    company_research: Dict
) -> Dict:
    """
    Generate a single dynamic question using LLM.
    
    Args:
        q_type: "intro", "project", "technical", "behavioral", "critical", "wrapup"
        context: dict with candidate info, skills, projects, etc.
        difficulty: fresher/intermediate/experienced
        company_research: dict with company insights
    
    Returns dict with question, skill_target, rationale.
    """
    from backend.app.core.ml_models import llm_generate
    
    diff_guide = _get_difficulty_guidance(difficulty)
    
    # Build context prompt
    candidate_info = f"""
Candidate Profile:
- Role applying for: {context.get('job_role', 'Software Engineer')}
- Experience: {context.get('experience_years', 0)} years
- Skills: {', '.join(context.get('skills', [])[:6])}
- Projects: {', '.join([p.get('name', '') for p in context.get('projects', [])[:2]])}
- Education: {context.get('education_summary', '')}
"""
    
    company_info = f"""
Company Context ({context.get('company', 'General')}):
- Focus: {company_research.get('company_focus', '')}
- Style: {company_research.get('interview_style', 'standard')}
- Common patterns: {', '.join(company_research.get('common_questions', [])[:2])}
"""
    
    prompts = {
        "intro": f"""Generate ONE unique, conversational self-introduction question for a {difficulty}-level candidate.

{candidate_info}
{company_info}

Requirements:
- Ask about their background AND motivation for this specific role/company
- Be warm but professional
- Reference their specific background if possible
- Difficulty: {diff_guide['depth']}
- Return ONLY the question, no preamble.""",

        "project": f"""Generate ONE unique technical question about a candidate's project work.

Project context: {context.get('current_project', 'their recent work')}
Tech stack mentioned: {', '.join(context.get('project_tech', []))}
{candidate_info}

Requirements:
- Ask about a SPECIFIC challenge or decision in their project
- Difficulty level: {diff_guide['complexity']}
- Focus: {diff_guide['focus']}
- Avoid: {diff_guide['avoid']}
- Return ONLY the question.""",

        "technical": f"""Generate ONE unique technical question about: {context.get('target_skill', 'their skills')}

{candidate_info}
{company_info}

Requirements:
- Make it a practical, scenario-based question
- NOT a definition question
- Difficulty: {diff_guide['complexity']}
- Focus: {diff_guide['focus']}
- Avoid: {diff_guide['avoid']}
- Return ONLY the question.""",

        "behavioral": f"""Generate ONE unique behavioral/situational question for a {difficulty}-level candidate.

{candidate_info}
{company_info}

Requirements:
- Focus on collaboration, problem-solving, or adaptability
- Make it relevant to their experience level
- Ask for specific examples
- Difficulty: {diff_guide['complexity']}
- Return ONLY the question.""",

        "critical": f"""Generate ONE critical thinking/debugging scenario question.

Context: {context.get('target_skill', 'technical system')}
{candidate_info}
{company_info}

Requirements:
- Present a realistic problem scenario
- Ask them to walk through their approach
- Difficulty: {diff_guide['complexity']}
- Make it a {difficulty}-level appropriate challenge
- Return ONLY the question.""",

        "wrapup": f"""Generate ONE closing question for a candidate interviewing at {context.get('company', 'the company')}.

{candidate_info}

Requirements:
- Give them a chance to showcase something not yet discussed
- Or ask about their questions for the team
- Be genuine, not templated
- Return ONLY the question."""
    }
    
    prompt = prompts.get(q_type, prompts["technical"])
    
    # Template fallbacks when LLM is unavailable or fails
    template_fallbacks = {
        "intro": f"Tell me about yourself and what motivated you to apply for this {context.get('job_role', 'Software Engineer')} role.",
        "project": f"Describe a challenging project you worked on using {context.get('target_skill', 'your tech stack')}. What was your specific contribution?",
        "technical": f"Explain how you would approach a technical problem involving {context.get('target_skill', 'your core skills')}. Walk me through your thought process.",
        "behavioral": "Tell me about a time when you had to work with a difficult team member. How did you handle the situation?",
        "critical": f"You're debugging a production issue in {context.get('target_skill', 'a critical system')}. What steps would you take to identify and fix the problem?",
        "wrapup": "What questions do you have for me about the team or the company?"
    }
    
    try:
        question = await asyncio.to_thread(llm_generate, prompt, max_new_tokens=200, temperature=0.7)
        question = question.strip().strip('"').strip("'")
        
        # Clean up common issues
        if question.startswith("Question:"):
            question = question[9:].strip()
        
        # Validate question is not empty and is meaningful
        if not question or len(question) < 20 or question.lower().startswith("tell me about") and len(question) < 30:
            # Use template fallback if LLM returned something too short or empty
            question = template_fallbacks.get(q_type, template_fallbacks["technical"])
            return {
                "question": question,
                "generated": True,
                "used_fallback": True
            }
        
        return {
            "question": question,
            "generated": True
        }
    except Exception as e:
        # Return template fallback on any error
        question = template_fallbacks.get(q_type, f"Tell me about your experience with {context.get('target_skill', 'technology')}.")
        return {
            "question": question,
            "generated": False,
            "error": str(e),
            "used_fallback": True
        }


@router.post("/interview/generate-dynamic/{session_id}")
async def generate_dynamic_interview(session_id: str):
    """
    Generate a complete dynamic interview plan using LLM.
    
    This is called during the permissions page (background generation)
    while the user is setting up camera/mic permissions.
    """
    try:
        validate_session_id(session_id)
        sdir = _storage_dir() / session_id
        
        if not sdir.exists():
            raise HTTPException(status_code=404, detail="Session not found.")
        
        # Load parsed data
        parsed_p = sdir / "parsed_resume.json"
        if not parsed_p.exists():
            raise HTTPException(status_code=404, detail="Resume not parsed. Upload resume first.")
        
        parsed = _read_json(parsed_p)
        
        # Load profile data
        prof = _read_json(sdir / "candidate_profile.json") if (sdir / "candidate_profile.json").exists() else {}
        jd = _read_json(sdir / "job_description.json") if (sdir / "job_description.json").exists() else {}
        
        # Extract context
        company = (jd.get("company") or prof.get("company") or "").strip()
        job_role = (prof.get("job_role") or jd.get("job_role") or "Software Engineer").strip()
        expertise = (prof.get("expertise_level") or "fresher").lower()
        
        # Get candidate info
        skills = parsed.get("skills", [])
        projects = parsed.get("projects", [])
        name = parsed.get("name") or prof.get("name") or "Candidate"
        
        # Research company
        company_research = await _research_company(company, job_role)
        
        # Build generation context
        def _get_proj_field(p, field, limit=200):
            if isinstance(p, dict):
                return str(p.get(field, ""))[:limit]
            return str(p)[:limit]

        context = {
            "name": name,
            "job_role": job_role,
            "company": company,
            "experience_years": parsed.get("experience_years", 0),
            "skills": skills,
            "projects": [{"name": _get_proj_field(p, "name", 50), "description": _get_proj_field(p, "details", 200)} for p in projects[:3]],
            "education_summary": parsed.get("education_summary", ""),
        }
        
        questions = []
        
        # Prepare all question generation tasks to run in parallel
        tasks = []
        
        # 1. Self Introduction
        tasks.append(("intro", context, "intro_1", "self_intro", "self_intro"))
        
        # 2. Project Questions (up to 2)
        for i, proj in enumerate(projects[:2]):
            proj_text = _get_proj_field(proj, "details", 500) if isinstance(proj, dict) else str(proj)
            proj_name = _get_proj_field(proj, "name", 100) if isinstance(proj, dict) else f"Project {i+1}"
            
            proj_context = {
                **context,
                "current_project": proj_text[:300],
                "project_tech": re.findall(r"\b(Python|JavaScript|React|Node|MongoDB|SQL|AWS|Docker|Kubernetes)\b", proj_text, re.I)
            }
            tasks.append(("project", proj_context, f"project_{i+1}", "project", proj_name))
        
        # 3. Technical Questions (2-3 based on skills and job)
        tech_skills = skills[:3] if skills else ["programming"]
        for i, skill in enumerate(tech_skills):
            tech_context = {
                **context,
                "target_skill": skill
            }
            tasks.append(("technical", tech_context, f"technical_{i+1}", "technical", skill))
        
        # 4. Behavioral Question
        tasks.append(("behavioral", context, "behavioral_1", "behavioral", "collaboration"))
        
        # 5. Critical Thinking
        critical_skill = tech_skills[0] if tech_skills else "system"
        critical_context = {
            **context,
            "target_skill": critical_skill
        }
        tasks.append(("critical", critical_context, "critical_1", "critical", critical_skill))
        
        # 6. Wrap-up
        tasks.append(("wrapup", context, "wrapup_1", "wrapup", "wrapup"))
        
        # Execute all LLM calls in parallel
        results = await asyncio.gather(*[
            _generate_dynamic_question(q_type, q_context, expertise, company_research)
            for q_type, q_context, _, _, _ in tasks
        ])
        
        # Build questions from results
        for (q_type, _, q_id, q_type_display, skill_target), result in zip(tasks, results):
            questions.append({
                "id": q_id,
                "type": q_type_display,
                "question": result["question"],
                "skill_target": skill_target,
                "source": "llm_dynamic"
            })
        
        # Save the plan
        plan = {
            "session_id": session_id,
            "candidate": name,
            "job_role": job_role,
            "company": company,
            "expertise_level": expertise,
            "total_questions": len(questions),
            "used_llm": True,
            "llm_generated": True,
            "company_research": company_research,
            "questions": questions,
            "max_followups": {"fresher": 3, "intermediate": 5, "experienced": 7}.get(expertise, 5),
            "followup_cache": {},  # populated post-generation if needed
            "generated_at": str(asyncio.get_running_loop().time())
        }
        
        _write_json(sdir / "interview_plan.json", plan)
        
        # Build preview and check for fallbacks
        questions_preview = []
        any_fallback = any(r.get("used_fallback", False) for r in results)
        
        from backend.app.core.ml_models import is_hf_circuit_open
        hf_open = is_hf_circuit_open()

        return {
            "status": "ok",
            "session_id": session_id,
            "total_questions": len(questions),
            "expertise_level": expertise,
            "company_researched": bool(company),
            "llm_fallback": any_fallback or hf_open,
            "questions_preview": [{"id": q["id"], "type": q["type"]} for q in questions]
        }
    except Exception as e:
        import logging
        logging.exception(f"Error in dynamic generation for session {session_id}: {e}")
        # Preserve HTTP 500 so frontend knows it failed and can fallback
        raise HTTPException(status_code=500, detail=f"Dynamic interview generation failed: {str(e)}")
