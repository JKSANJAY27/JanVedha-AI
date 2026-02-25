"""
ClassifierAgent

Classifies a civic complaint into a department, extracts metadata, and determines language.
Uses LangChain structured output with Gemini to ensure reliable JSON responses.
Falls back gracefully on API failure.
"""
from __future__ import annotations

import json
import re
import logging
from dataclasses import dataclass, field
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.exceptions import OutputParserException

from app.services.ai.gemini_client import get_llm

logger = logging.getLogger(__name__)

# Department catalogue — extend as needed
DEPARTMENT_CATALOGUE = {
    "D01": {"name": "Roads & Bridges", "keywords": ["pothole", "road", "bridge", "footpath", "pavement", "crack", "speed breaker"]},
    "D02": {"name": "Buildings & Planning", "keywords": ["construction", "illegal", "encroachment", "building", "permit"]},
    "D03": {"name": "Water Supply", "keywords": ["water", "supply", "pipe", "leak", "low pressure", "no water", "dirty water"]},
    "D04": {"name": "Sewage & Drainage", "keywords": ["sewage", "drain", "blocked", "overflow", "manhole", "stench"]},
    "D05": {"name": "Solid Waste Management", "keywords": ["garbage", "waste", "bin", "collection", "dumping", "litter", "trash"]},
    "D06": {"name": "Street Lighting", "keywords": ["light", "lamp", "dark", "street light", "electricity", "bulb"]},
    "D07": {"name": "Parks & Greenery", "keywords": ["park", "tree", "garden", "grass", "playground", "fallen tree"]},
    "D08": {"name": "Health & Sanitation", "keywords": ["mosquito", "dengue", "fever", "epidemic", "stray", "dog", "bite", "dead animal"]},
    "D09": {"name": "Fire & Emergency", "keywords": ["fire", "accident", "emergency", "explosion", "hazard", "collapse"]},
    "D10": {"name": "Traffic & Transport", "keywords": ["traffic", "signal", "bus", "road block", "parking", "vehicle"]},
    "D11": {"name": "Revenue & Property", "keywords": ["tax", "property", "document", "certificate"]},
    "D12": {"name": "Social Welfare", "keywords": ["pension", "welfare", "disability", "ration", "subsidy"]},
    "D13": {"name": "Education", "keywords": ["school", "teacher", "education", "college", "student"]},
    "D14": {"name": "Disaster Management", "keywords": ["flood", "cyclone", "landslide", "tsunami", "disaster", "relief"]},
}

SYSTEM_PROMPT = """You are an expert civic complaint classifier for a smart city AI system in India.
Your task is to analyze a citizen's complaint and extract structured information.

Available departments and their IDs:
{dept_list}

Respond ONLY with valid JSON matching this exact schema (no markdown, no explanation):
{{
  "dept_id": "<department ID from the list above>",
  "dept_name": "<department name>",
  "issue_category": "<short snake_case category, e.g. pothole, sewage_overflow, street_light_out>",
  "issue_summary": "<1-2 sentence neutral summary of the complaint>",
  "location_extracted": "<extracted location text or 'Unknown'>",
  "language_detected": "<ISO 639-1 code, e.g. en, ta, hi, te>",
  "confidence": <float 0.0-1.0>,
  "needs_clarification": <true|false>,
  "clarification_question": "<question to ask if needs_clarification is true, else null>",
  "requires_human_review": <true if confidence < 0.7>
}}"""

def _build_dept_list() -> str:
    return "\n".join(
        f"  {did}: {info['name']} (handles: {', '.join(info['keywords'][:4])})"
        for did, info in DEPARTMENT_CATALOGUE.items()
    )


@dataclass
class ClassificationResult:
    dept_id: str
    dept_name: str
    issue_category: str
    issue_summary: str
    location_extracted: str
    language_detected: str
    confidence: float
    needs_clarification: bool
    clarification_question: Optional[str] = None
    requires_human_review: bool = False


def _keyword_fallback(text: str) -> ClassificationResult:
    """Simple keyword match fallback when LLM is unavailable."""
    text_lower = text.lower()
    best_dept = "D05"
    best_score = 0
    for dept_id, info in DEPARTMENT_CATALOGUE.items():
        score = sum(1 for kw in info["keywords"] if kw in text_lower)
        if score > best_score:
            best_score = score
            best_dept = dept_id
    dept_info = DEPARTMENT_CATALOGUE[best_dept]
    return ClassificationResult(
        dept_id=best_dept,
        dept_name=dept_info["name"],
        issue_category="general_complaint",
        issue_summary=text[:200],
        location_extracted="Unknown",
        language_detected="en",
        confidence=0.6 if best_score > 0 else 0.4,
        needs_clarification=best_score == 0,
        clarification_question="Could you describe the issue in more detail?" if best_score == 0 else None,
        requires_human_review=True,
    )


async def classify_complaint(description: str, photo_url: Optional[str] = None) -> ClassificationResult:
    """
    Main entry point. Classifies a complaint using Gemini LLM.
    Falls back to keyword matching if LLM call fails.
    """
    try:
        llm = get_llm()
        system = SystemMessage(content=SYSTEM_PROMPT.format(dept_list=_build_dept_list()))
        user_content = f"Complaint: {description}"
        if photo_url:
            user_content += f"\n[Photo attached: {photo_url}]"
        human = HumanMessage(content=user_content)

        response = await llm.ainvoke([system, human])
        raw = response.content.strip()

        # Strip markdown code fences if present
        raw = re.sub(r"^```[a-z]*\n?", "", raw).strip("`").strip()

        data = json.loads(raw)
        return ClassificationResult(
            dept_id=data.get("dept_id", "D05"),
            dept_name=data.get("dept_name", "Solid Waste Management"),
            issue_category=data.get("issue_category", "general_complaint"),
            issue_summary=data.get("issue_summary", description[:200]),
            location_extracted=data.get("location_extracted", "Unknown"),
            language_detected=data.get("language_detected", "en"),
            confidence=float(data.get("confidence", 0.75)),
            needs_clarification=bool(data.get("needs_clarification", False)),
            clarification_question=data.get("clarification_question"),
            requires_human_review=bool(data.get("requires_human_review", False)),
        )
    except Exception as exc:
        logger.warning("ClassifierAgent LLM call failed (%s). Using keyword fallback.", exc)
        return _keyword_fallback(description)
