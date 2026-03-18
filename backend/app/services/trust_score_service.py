"""
Ward Trust Score computation — Feature 4.

Computes a monthly trust score from ticket data + social sentiment.
Formula:
  trust_score = (on_time_rate * 0.35) + (verified_completion_rate * 0.30)
              + (citizen_satisfaction * 0.20) + ((1 - reopen_rate) * 0.15)
  multiplied by 100 → score out of 100
"""
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from app.core.config import settings

logger = logging.getLogger(__name__)

SLA_HOURS = 72  # Default SLA window in hours


async def compute_trust_score(ward_id: int, month: str) -> Dict[str, Any]:
    """
    Compute the Public Trust Score for a ward in a given month (YYYY-MM).
    Stores a snapshot in trust_score_history.
    Returns the full breakdown dict.
    """
    from app.mongodb.models.ticket import TicketMongo
    from app.mongodb.models.social_post import SocialPostMongo
    from app.mongodb.models.trust_score import TrustScoreMongo

    # Parse month
    year_int, month_int = int(month[:4]), int(month[5:7])
    from calendar import monthrange
    _, last_day = monthrange(year_int, month_int)
    month_start = datetime(year_int, month_int, 1)
    month_end = datetime(year_int, month_int, last_day, 23, 59, 59)

    # ── Fetch tickets resolved in this month ──────────────────────────────────
    resolved_tickets = await TicketMongo.find(
        TicketMongo.ward_id == ward_id,
        TicketMongo.status.in_(["CLOSED", "RESOLVED"]),
        TicketMongo.resolved_at >= month_start,
        TicketMongo.resolved_at <= month_end,
    ).to_list()

    total_resolved = len(resolved_tickets)

    # on_time_rate: resolved within SLA (72h default)
    resolved_within_sla = 0
    resolution_hours_list = []
    for t in resolved_tickets:
        if t.resolved_at and t.created_at:
            elapsed_h = (t.resolved_at - t.created_at).total_seconds() / 3600
            resolution_hours_list.append(elapsed_h)
            sla_limit = SLA_HOURS
            if t.sla_deadline:
                sla_limit = (t.sla_deadline - t.created_at).total_seconds() / 3600
            if elapsed_h <= sla_limit:
                resolved_within_sla += 1

    on_time_rate = (resolved_within_sla / total_resolved) if total_resolved > 0 else 0.0
    avg_resolution_hours = (
        sum(resolution_hours_list) / len(resolution_hours_list)
        if resolution_hours_list else 0.0
    )

    # verified_completion_rate: AI-verified resolutions
    verified_resolutions = sum(1 for t in resolved_tickets if t.work_verified is True)
    verified_completion_rate = (verified_resolutions / total_resolved) if total_resolved > 0 else 0.0

    # reopen_rate: tickets reopened (proxy for quality)
    all_ward_tickets_month = await TicketMongo.find(
        TicketMongo.ward_id == ward_id,
        TicketMongo.created_at >= month_start,
        TicketMongo.created_at <= month_end,
    ).to_list()
    reopened_tickets = sum(1 for t in all_ward_tickets_month if t.status == "REOPENED")
    reopen_rate = (reopened_tickets / total_resolved) if total_resolved > 0 else 0.0

    # citizen_satisfaction: positive social sentiment
    social_posts = await SocialPostMongo.find(
        SocialPostMongo.ward_id == ward_id,
        SocialPostMongo.timestamp >= month_start,
        SocialPostMongo.timestamp <= month_end,
    ).to_list()
    total_sentiment_posts = len(social_posts)
    positive_sentiment_posts = sum(
        1 for p in social_posts
        if hasattr(p, "sentiment_score") and p.sentiment_score is not None and p.sentiment_score > 0
    )
    citizen_satisfaction = (
        positive_sentiment_posts / total_sentiment_posts
        if total_sentiment_posts > 0 else 0.0
    )

    # ── Weighted trust score ──────────────────────────────────────────────────
    trust_score = round((
        on_time_rate * 0.35
        + verified_completion_rate * 0.30
        + citizen_satisfaction * 0.20
        + (1 - min(reopen_rate, 1.0)) * 0.15
    ) * 100, 1)

    # ── Persist snapshot ──────────────────────────────────────────────────────
    # Upsert: remove old snapshot for same ward+month, then insert new one
    await TrustScoreMongo.find(
        TrustScoreMongo.ward_id == ward_id,
        TrustScoreMongo.month == month,
    ).delete()

    snapshot = TrustScoreMongo(
        ward_id=ward_id,
        month=month,
        trust_score=trust_score,
        on_time_rate=round(on_time_rate, 4),
        avg_resolution_hours=round(avg_resolution_hours, 1),
        verified_completion_rate=round(verified_completion_rate, 4),
        citizen_satisfaction=round(citizen_satisfaction, 4),
        reopen_rate=round(reopen_rate, 4),
        total_resolved=total_resolved,
        resolved_within_sla=resolved_within_sla,
        verified_resolutions=verified_resolutions,
        total_sentiment_posts=total_sentiment_posts,
        positive_sentiment_posts=positive_sentiment_posts,
        reopened_tickets=reopened_tickets,
    )
    await snapshot.insert()

    return _build_response(snapshot)


def _build_response(s) -> Dict[str, Any]:
    return {
        "ward_id": s.ward_id,
        "month": s.month,
        "trust_score": s.trust_score,
        "grade": _grade(s.trust_score),
        "components": {
            "on_time_rate": {
                "value": round(s.on_time_rate * 100, 1),
                "label": "Issues resolved on time",
                "weight": 0.35,
                "raw": {"resolved_within_sla": s.resolved_within_sla, "total_resolved": s.total_resolved},
            },
            "verified_completion_rate": {
                "value": round(s.verified_completion_rate * 100, 1),
                "label": "Work independently verified",
                "weight": 0.30,
                "raw": {"verified_resolutions": s.verified_resolutions, "total_resolved": s.total_resolved},
            },
            "citizen_satisfaction": {
                "value": round(s.citizen_satisfaction * 100, 1),
                "label": "Citizen sentiment positive",
                "weight": 0.20,
                "raw": {"positive": s.positive_sentiment_posts, "total": s.total_sentiment_posts},
            },
            "quality_score": {
                "value": round((1 - min(s.reopen_rate, 1.0)) * 100, 1),
                "label": "Quality (no re-reports)",
                "weight": 0.15,
                "raw": {"reopened": s.reopened_tickets, "total_resolved": s.total_resolved},
            },
        },
        "avg_resolution_hours": s.avg_resolution_hours,
        "computed_at": s.computed_at.isoformat() if s.computed_at else None,
    }


def _grade(score: float) -> str:
    if score >= 75:
        return "green"
    elif score >= 50:
        return "amber"
    return "red"


async def get_trust_score_history(ward_id: int, months: int = 6) -> List[Dict[str, Any]]:
    """Return last N months of trust score snapshots for sparkline data."""
    from app.mongodb.models.trust_score import TrustScoreMongo

    snapshots = await TrustScoreMongo.find(
        TrustScoreMongo.ward_id == ward_id
    ).sort(-TrustScoreMongo.month).limit(months).to_list()

    return [
        {"month": s.month, "trust_score": s.trust_score, "grade": _grade(s.trust_score)}
        for s in reversed(snapshots)
    ]


async def generate_trust_score_insights(ward_id: int, score_data: Dict) -> str:
    """Use Gemini to generate a plain-language insight about the trust score."""
    if not settings.GEMINI_API_KEY:
        return _fallback_insight(score_data)

    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")

        components = score_data.get("components", {})
        prompt = f"""You are a civic performance analyst. Below is the Public Trust Score breakdown for Ward {ward_id}:

Trust Score: {score_data.get('trust_score', 0)}/100 ({score_data.get('grade', 'N/A')})
- On-time resolution rate: {components.get('on_time_rate', {}).get('value', 0)}%
- Work independently verified: {components.get('verified_completion_rate', {}).get('value', 0)}%
- Positive citizen sentiment: {components.get('citizen_satisfaction', {}).get('value', 0)}%
- Quality (no re-reports): {components.get('quality_score', {}).get('value', 0)}%
- Avg resolution time: {score_data.get('avg_resolution_hours', 0)} hours

Write a 2-3 sentence specific, actionable insight for the councillor.
Focus on the WEAKEST metric and suggest a concrete action.
Be direct and professional."""

        response = await model.generate_content_async(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Trust score insight generation failed: {e}")
        return _fallback_insight(score_data)


def _fallback_insight(score_data: Dict) -> str:
    score = score_data.get("trust_score", 0)
    if score >= 75:
        return "Your ward's trust score is strong. Maintain current resolution rates and continue proactive citizen communication."
    elif score >= 50:
        return "Trust score is moderate. Focus on improving verified completion rates and reducing resolution times to boost public confidence."
    return "Trust score needs improvement. Prioritize clearing overdue tickets and ensuring work is photo-verified to rebuild public trust."

