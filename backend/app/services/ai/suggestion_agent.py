"""
SuggestionAgent

Generates 3 actionable, specific suggestions for a civic complaint.
Targeted at the ward officer who will handle the issue.
Uses existing ticket data for better contextual suggestions.
"""
from __future__ import annotations

import re
import logging
from typing import List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.services.ai.gemini_client import get_llm

logger = logging.getLogger(__name__)

SUGGESTION_SYSTEM_PROMPT = """You are a civic operations expert advising a ward officer on how to handle a citizen complaint.

Generate exactly 3 specific, actionable suggestions for addressing this issue.
Each suggestion should be:
- Concrete (what to do, not generic advice)
- Appropriate for a ward-level officer's authority
- Ordered by urgency/importance (most urgent first)
- Brief (1-2 sentences each)

Context about the ward/city: {context}

Respond ONLY as a valid JSON array of exactly 3 strings:
["suggestion 1", "suggestion 2", "suggestion 3"]"""


async def generate_suggestions(
    description: str,
    issue_category: str,
    dept_name: str,
    priority_label: str,
    location_text: Optional[str] = None,
    similar_ticket_summaries: Optional[List[str]] = None,
) -> List[str]:
    """
    Returns a list of 3 actionable suggestions.
    Falls back to generic suggestions on failure.
    """
    try:
        context_parts = [f"Department: {dept_name}", f"Priority: {priority_label}"]
        if location_text:
            context_parts.append(f"Location: {location_text}")
        if similar_ticket_summaries:
            context_parts.append(
                f"Similar past issues: {'; '.join(similar_ticket_summaries[:3])}"
            )

        llm = get_llm()
        system = SystemMessage(
            content=SUGGESTION_SYSTEM_PROMPT.format(context="; ".join(context_parts))
        )
        human = HumanMessage(
            content=(
                f"Issue category: {issue_category}\n"
                f"Citizen complaint: {description}"
            )
        )

        response = await llm.ainvoke([system, human])
        raw = re.sub(r"^```[a-z]*\n?", "", response.content.strip()).strip("`").strip()

        import json
        suggestions = json.loads(raw)
        if isinstance(suggestions, list) and len(suggestions) >= 3:
            return [str(s) for s in suggestions[:3]]
        return _fallback_suggestions(issue_category, priority_label)

    except Exception as exc:
        logger.warning("SuggestionAgent failed (%s). Using generic suggestions.", exc)
        return _fallback_suggestions(issue_category, priority_label)


def _fallback_suggestions(issue_category: str, priority_label: str) -> List[str]:
    """Rule-based fallback suggestions keyed by category."""
    generic = {
        "pothole": [
            "Dispatch road crew to inspect and patch the pothole within 24 hours.",
            "Install warning signage immediately to prevent accidents.",
            "Document with before/after photos and update the ticket accordingly.",
        ],
        "sewage_overflow": [
            "Deploy sanitation crew to clear the blocked drain immediately.",
            "Disinfect the surrounding area to prevent disease spread.",
            "File a maintenance report to schedule permanent drain repair.",
        ],
        "street_light_out": [
            "Notify electrical department to replace the faulty bulb/fixture.",
            "Install temporary lighting if area poses a safety risk.",
            "Check connected lights on the same circuit for systematic failures.",
        ],
        "garbage": [
            "Schedule an emergency pickup for the reported garbage accumulation.",
            "Identify and penalize illegal dumping if applicable.",
            "Increase collection frequency in this area if recurring.",
        ],
        "water": [
            "Dispatch a plumber to inspect and fix the reported water issue.",
            "Inform affected residents of the estimated restoration time.",
            "Check if neighboring areas are affected and escalate if widespread.",
        ],
    }
    for key, suggestions in generic.items():
        if key in issue_category.lower():
            return suggestions

    priority_action = "Treat as emergency and act within 24 hours." if priority_label in ("CRITICAL", "HIGH") else "Schedule resolution within SLA window."
    return [
        priority_action,
        "Assign a technician and update ticket status to IN_PROGRESS.",
        "Follow up with the citizen after completion for satisfaction rating.",
    ]
