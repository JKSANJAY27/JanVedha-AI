"""
MemoryAgent — Seasonal & Recurring Issue Pattern Detector

Activated ONLY for CRITICAL or HIGH priority issues (or when category matches a known recurring pattern).
Saves computation by NOT checking memory for every new ticket.

Workflow:
1. Query IssueMemoryMongo for same ward + category + month (any past year)
2. If occurrence_count >= 2 → pattern detected → generate proactive alert text
3. Upsert the IssueMemory record for this ticket
4. Return alert text (None if no pattern detected)
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Optional, List

from langchain_core.messages import HumanMessage, SystemMessage

from app.services.ai.gemini_client import get_llm

logger = logging.getLogger(__name__)

MEMORY_ALERT_PROMPT = """You are a civic planning advisor. Based on historical issue data, generate a CONCISE proactive alert.

Historical pattern:
- Ward: {ward_id}
- Issue category: {issue_category}
- Month: {month_name}
- Times reported in past years: {count}
- Average severity score: {avg_severity:.1f}

Generate a 2-3 sentence alert message that:
1. Mentions this is a recurring seasonal issue
2. Gives 1-2 specific preventive actions the ward officer should take NOW (before the issue worsens)
3. References the historical context briefly

Respond in plain text ONLY (no JSON, no markdown)."""

MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]


def _should_check_memory(priority_label: str, issue_category: str) -> bool:
    """
    Gate: only check memory for critical/high issues or known recurring categories.
    Avoids unnecessary DB + LLM calls for low-priority routine complaints.
    """
    if priority_label in ("CRITICAL", "HIGH"):
        return True
    recurring_categories = {
        "flood", "flooding", "pothole", "sewage_overflow", "dirty_water",
        "mosquito_breeding", "garbage", "drain_blocked", "road_collapse",
    }
    return any(cat in issue_category.lower() for cat in recurring_categories)


async def check_and_update_memory(
    ward_id: int,
    issue_category: str,
    dept_id: str,
    priority_label: str,
    priority_score: float,
    description: str,
    ticket_id: str,
) -> Optional[str]:
    """
    Main entry point for the MemoryAgent.
    Returns a proactive alert string if a seasonal pattern is detected, else None.
    """
    if ward_id is None or not _should_check_memory(priority_label, issue_category):
        return None

    try:
        from app.mongodb.models.issue_memory import IssueMemoryMongo

        now = datetime.utcnow()
        current_month = now.month
        current_year = now.year

        # Look for past-year records for same ward + category + month
        past_memories: List[IssueMemoryMongo] = await IssueMemoryMongo.find(
            IssueMemoryMongo.ward_id == ward_id,
            IssueMemoryMongo.issue_category == issue_category,
            IssueMemoryMongo.month == current_month,
            IssueMemoryMongo.year < current_year,
        ).to_list()

        alert_text: Optional[str] = None

        if len(past_memories) >= 1:
            total_occurrences = sum(m.occurrence_count for m in past_memories)
            if total_occurrences >= 2:
                avg_severity = sum(m.avg_severity_score for m in past_memories) / len(past_memories)
                alert_text = await _generate_alert_text(
                    ward_id=ward_id,
                    issue_category=issue_category,
                    month=current_month,
                    count=total_occurrences,
                    avg_severity=avg_severity,
                )

        # Upsert current year's memory record
        existing = await IssueMemoryMongo.find_one(
            IssueMemoryMongo.ward_id == ward_id,
            IssueMemoryMongo.issue_category == issue_category,
            IssueMemoryMongo.month == current_month,
            IssueMemoryMongo.year == current_year,
        )
        if existing:
            existing.occurrence_count += 1
            # Rolling average severity
            prev_total = existing.avg_severity_score * (existing.occurrence_count - 1)
            existing.avg_severity_score = (prev_total + priority_score) / existing.occurrence_count
            if ticket_id not in existing.sample_ticket_ids:
                existing.sample_ticket_ids = (existing.sample_ticket_ids + [ticket_id])[-5:]
            existing.last_seen_description = description[:300]
            existing.updated_at = now
            await existing.save()
        else:
            # Extract keywords (simple split of top words)
            keywords = list({
                w.lower() for w in description.split()
                if len(w) > 4 and w.isalpha()
            })[:10]
            new_memory = IssueMemoryMongo(
                ward_id=ward_id,
                issue_category=issue_category,
                dept_id=dept_id,
                month=current_month,
                year=current_year,
                occurrence_count=1,
                avg_severity_score=priority_score,
                keywords=keywords,
                sample_ticket_ids=[ticket_id],
                last_seen_description=description[:300],
            )
            await new_memory.insert()

        return alert_text

    except Exception as exc:
        logger.warning("MemoryAgent failed: %s", exc)
        return None


async def _generate_alert_text(
    ward_id: int, issue_category: str, month: int, count: int, avg_severity: float
) -> str:
    """Uses Gemini to generate a human-readable seasonal alert."""
    try:
        llm = get_llm()
        prompt = MEMORY_ALERT_PROMPT.format(
            ward_id=ward_id,
            issue_category=issue_category.replace("_", " "),
            month_name=MONTH_NAMES[month],
            count=count,
            avg_severity=avg_severity,
        )
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        return response.content.strip()
    except Exception as exc:
        logger.warning("Memory alert LLM failed: %s. Using template.", exc)
        return (
            f"⚠️ Seasonal Alert: Ward {ward_id} has historically reported "
            f"{issue_category.replace('_', ' ')} issues in {MONTH_NAMES[month]} "
            f"({count} times in past records). "
            f"Preventive inspection and maintenance is recommended."
        )


async def get_seasonal_alerts_for_ward(ward_id: int, month: int) -> List[dict]:
    """
    Returns predicted recurring issues for a ward in a given month.
    Used by the /api/public/seasonal-alerts endpoint.
    """
    try:
        from app.mongodb.models.issue_memory import IssueMemoryMongo

        memories = await IssueMemoryMongo.find(
            IssueMemoryMongo.ward_id == ward_id,
            IssueMemoryMongo.month == month,
        ).sort(-IssueMemoryMongo.occurrence_count).limit(10).to_list()

        alerts = []
        for m in memories:
            if m.occurrence_count >= 2:
                alerts.append({
                    "issue_category": m.issue_category,
                    "dept_id": m.dept_id,
                    "occurrence_count": m.occurrence_count,
                    "avg_severity_score": round(m.avg_severity_score, 1),
                    "last_seen_year": m.year,
                    "recommendation": (
                        f"Schedule preventive maintenance for {m.issue_category.replace('_', ' ')} "
                        f"— reported {m.occurrence_count} times in {MONTH_NAMES[month]} historically."
                    ),
                })
        return alerts
    except Exception as exc:
        logger.error("get_seasonal_alerts_for_ward failed: %s", exc)
        return []
