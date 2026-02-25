"""
AI Pipeline Orchestrator

Chains all agents in sequence for a civic complaint:
  ClassifierAgent → RoutingAgent → PriorityAgent → SuggestionAgent → MemoryAgent

Returns AIPipelineResult which TicketService uses to build the TicketMongo document.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

from app.services.ai.classifier_agent import classify_complaint, ClassificationResult
from app.services.ai.routing_agent import route_complaint, RoutingResult
from app.services.ai.priority_agent import calculate_priority
from app.services.ai.suggestion_agent import generate_suggestions
from app.services.ai.memory_agent import check_and_update_memory

logger = logging.getLogger(__name__)


@dataclass
class AIPipelineResult:
    # From Classifier
    dept_id: str
    dept_name: str
    issue_category: str
    issue_summary: str
    location_extracted: str
    language_detected: str
    ai_confidence: float
    needs_clarification: bool
    clarification_question: Optional[str]
    requires_human_review: bool

    # From Router
    routing_reason: str
    escalation_required: bool
    escalation_reason: Optional[str]

    # From Priority
    priority_score: float
    priority_label: str
    priority_source: str

    # From Suggestion
    suggestions: List[str] = field(default_factory=list)

    # From Memory
    seasonal_alert: Optional[str] = None


async def run_pipeline(
    description: str,
    location_text: Optional[str] = None,
    photo_url: Optional[str] = None,
    ward_id: Optional[int] = None,
    ticket_id: Optional[str] = None,
) -> AIPipelineResult:
    """
    Run the full AI pipeline for a new complaint.

    Steps are run sequentially where each step depends on the previous output.
    Suggestion and Memory steps run concurrently for speed.
    """
    now = datetime.utcnow()

    # ── Step 1: Classify ──────────────────────────────────────────────────────
    classification: ClassificationResult = await classify_complaint(
        description=description,
        photo_url=photo_url,
    )

    # ── Step 2: Route ─────────────────────────────────────────────────────────
    routing: RoutingResult = await route_complaint(
        description=description,
        classification=classification,
    )

    # Use routing's dept_id (may override classifier's)
    final_dept_id = routing.dept_id
    final_dept_name = routing.dept_name

    # ── Step 3: Priority (hybrid rule + ML) ───────────────────────────────────
    priority_score, priority_label, priority_source = await calculate_priority(
        issue_category=classification.issue_category,
        description=description,
        dept_id=final_dept_id,
        report_count=1,
        location_type="unknown",
        days_open=0,
        hours_until_sla_breach=168.0,  # default 7-day SLA
        social_media_mentions=0,
        month=now.month,
    )

    # ── Steps 4 & 5: Suggestions + Memory (run concurrently) ─────────────────
    import asyncio
    suggestions_task = asyncio.create_task(
        generate_suggestions(
            description=description,
            issue_category=classification.issue_category,
            dept_name=final_dept_name,
            priority_label=priority_label,
            location_text=location_text,
        )
    )

    memory_task = asyncio.create_task(
        check_and_update_memory(
            ward_id=ward_id or 0,
            issue_category=classification.issue_category,
            dept_id=final_dept_id,
            priority_label=priority_label,
            priority_score=priority_score,
            description=description,
            ticket_id=ticket_id or "pending",
        )
    ) if ward_id else asyncio.create_task(asyncio.sleep(0))

    suggestions = await suggestions_task
    seasonal_alert = await memory_task if ward_id else None

    return AIPipelineResult(
        dept_id=final_dept_id,
        dept_name=final_dept_name,
        issue_category=classification.issue_category,
        issue_summary=classification.issue_summary,
        location_extracted=classification.location_extracted,
        language_detected=classification.language_detected,
        ai_confidence=classification.confidence,
        needs_clarification=classification.needs_clarification,
        clarification_question=classification.clarification_question,
        requires_human_review=classification.requires_human_review,
        routing_reason=routing.routing_reason,
        escalation_required=routing.escalation_required,
        escalation_reason=routing.escalation_reason,
        priority_score=priority_score,
        priority_label=priority_label,
        priority_source=priority_source,
        suggestions=suggestions if isinstance(suggestions, list) else [],
        seasonal_alert=seasonal_alert if isinstance(seasonal_alert, str) else None,
    )
