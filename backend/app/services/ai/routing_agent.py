"""
RoutingAgent

Verifies and potentially adjusts the department routing from the ClassifierAgent.
Handles multi-department issues and provides routing reasoning.
"""
from __future__ import annotations

import json
import re
import logging
from dataclasses import dataclass
from typing import Optional, List

from langchain_core.messages import HumanMessage, SystemMessage

from app.services.ai.gemini_client import get_llm
from app.services.ai.classifier_agent import DEPARTMENT_CATALOGUE, ClassificationResult

logger = logging.getLogger(__name__)

ROUTING_SYSTEM_PROMPT = """You are a senior civic administrator deciding which government department should handle a complaint.
You have been given an initial classification. Your job is to confirm it or suggest a better routing.

Available departments:
{dept_list}

Consider:
1. Which department is PRIMARILY responsible?
2. Does this need escalation (safety/health emergency)?
3. Are multiple departments involved? If so, pick the LEAD department only.

Respond ONLY with valid JSON:
{{
  "dept_id": "<confirmed or corrected department ID>",
  "dept_name": "<department name>",
  "routing_confirmed": <true if original routing was correct, false if corrected>,
  "routing_reason": "<1-2 sentence explanation for this routing decision>",
  "escalation_required": <true|false>,
  "escalation_reason": "<reason if escalation required, else null>"
}}"""


@dataclass
class RoutingResult:
    dept_id: str
    dept_name: str
    routing_confirmed: bool
    routing_reason: str
    escalation_required: bool
    escalation_reason: Optional[str] = None


async def route_complaint(
    description: str,
    classification: ClassificationResult,
) -> RoutingResult:
    """
    Verifies the dept routing. Returns a RoutingResult with the final dept_id and reasoning.
    Falls back to accepting the classifier's result on failure.
    """
    try:
        llm = get_llm()
        dept_list = "\n".join(
            f"  {did}: {info['name']}" for did, info in DEPARTMENT_CATALOGUE.items()
        )
        system = SystemMessage(content=ROUTING_SYSTEM_PROMPT.format(dept_list=dept_list))
        human = HumanMessage(
            content=(
                f"Complaint: {description}\n\n"
                f"Initial Classification:\n"
                f"  Department: {classification.dept_id} - {classification.dept_name}\n"
                f"  Category: {classification.issue_category}\n"
                f"  Summary: {classification.issue_summary}\n"
                f"  Confidence: {classification.confidence}"
            )
        )

        response = await llm.ainvoke([system, human])
        raw = re.sub(r"^```[a-z]*\n?", "", response.content.strip()).strip("`").strip()
        data = json.loads(raw)

        return RoutingResult(
            dept_id=data.get("dept_id", classification.dept_id),
            dept_name=data.get("dept_name", classification.dept_name),
            routing_confirmed=bool(data.get("routing_confirmed", True)),
            routing_reason=data.get("routing_reason", "Routing confirmed by AI."),
            escalation_required=bool(data.get("escalation_required", False)),
            escalation_reason=data.get("escalation_reason"),
        )
    except Exception as exc:
        logger.warning("RoutingAgent failed (%s). Accepting classifier result.", exc)
        return RoutingResult(
            dept_id=classification.dept_id,
            dept_name=classification.dept_name,
            routing_confirmed=True,
            routing_reason="Routing accepted from classifier (routing agent unavailable).",
            escalation_required=False,
        )
