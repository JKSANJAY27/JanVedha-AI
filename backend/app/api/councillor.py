"""
Councillor API — ward-level analytics and insights for elected councillors.
All endpoints return aggregated, read-only data. Councillors cannot modify tickets.
"""
from fastapi import APIRouter, Depends, Query
from typing import Optional
from datetime import datetime, timedelta

from app.core.dependencies import get_current_user
from app.mongodb.models.user import UserMongo
from app.mongodb.models.ticket import TicketMongo
from app.enums import UserRole, TicketStatus, PriorityLabel

router = APIRouter()


def _require_councillor(current_user: UserMongo = Depends(get_current_user)) -> UserMongo:
    """Allow councillors, ward officers, and admins to access these endpoints."""
    allowed = {UserRole.COUNCILLOR, UserRole.WARD_OFFICER, UserRole.COMMISSIONER, UserRole.SUPER_ADMIN}
    if current_user.role not in allowed:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Councillor access required")
    return current_user


@router.get("/ward-summary")
async def get_ward_summary(
    ward_id: Optional[int] = Query(None),
    current_user: UserMongo = Depends(_require_councillor),
):
    """High-level KPI summary for a ward."""
    effective_ward = ward_id or current_user.ward_id
    
    all_tickets = await TicketMongo.find(
        TicketMongo.ward_id == effective_ward
    ).to_list()

    if not all_tickets:
        return {
            "ward_id": effective_ward,
            "total": 0,
            "open": 0,
            "closed": 0,
            "overdue": 0,
            "resolution_rate": 0,
            "avg_resolution_days": 0,
            "avg_satisfaction": None,
        }

    now = datetime.utcnow()
    closed = [t for t in all_tickets if t.status in {TicketStatus.CLOSED}]
    open_tickets = [t for t in all_tickets if t.status not in {TicketStatus.CLOSED, TicketStatus.REJECTED}]
    overdue = [t for t in open_tickets if t.sla_deadline and t.sla_deadline < now]

    # Avg resolution time (days) for closed tickets
    resolution_times = [
        (t.resolved_at - t.created_at).days
        for t in closed if t.resolved_at
    ]
    avg_resolution = round(sum(resolution_times) / len(resolution_times), 1) if resolution_times else 0

    # Satisfaction average
    sat_scores = [t.citizen_satisfaction for t in all_tickets if t.citizen_satisfaction]
    avg_sat = round(sum(sat_scores) / len(sat_scores), 1) if sat_scores else None

    return {
        "ward_id": effective_ward,
        "total": len(all_tickets),
        "open": len(open_tickets),
        "closed": len(closed),
        "overdue": len(overdue),
        "resolution_rate": round((len(closed) / len(all_tickets)) * 100, 1),
        "avg_resolution_days": avg_resolution,
        "avg_satisfaction": avg_sat,
    }


@router.get("/department-performance")
async def get_department_performance(
    ward_id: Optional[int] = Query(None),
    current_user: UserMongo = Depends(_require_councillor),
):
    """Per-department breakdown of ticket resolution in the ward."""
    effective_ward = ward_id or current_user.ward_id
    now = datetime.utcnow()

    tickets = await TicketMongo.find(
        TicketMongo.ward_id == effective_ward
    ).to_list()

    dept_map: dict = {}
    for t in tickets:
        d = t.dept_id
        if d not in dept_map:
            dept_map[d] = {"dept_id": d, "total": 0, "open": 0, "closed": 0, "overdue": 0}
        dept_map[d]["total"] += 1
        if t.status in {TicketStatus.CLOSED}:
            dept_map[d]["closed"] += 1
        else:
            dept_map[d]["open"] += 1
            if t.sla_deadline and t.sla_deadline < now:
                dept_map[d]["overdue"] += 1

    result = list(dept_map.values())
    # Sort by overdue count descending
    result.sort(key=lambda x: x["overdue"], reverse=True)
    return result


@router.get("/satisfaction-trend")
async def get_satisfaction_trend(
    ward_id: Optional[int] = Query(None),
    weeks: int = Query(8, ge=2, le=16),
    current_user: UserMongo = Depends(_require_councillor),
):
    """Weekly average citizen satisfaction for the last N weeks."""
    effective_ward = ward_id or current_user.ward_id
    now = datetime.utcnow()

    weekly_data = []
    for i in range(weeks - 1, -1, -1):
        week_start = now - timedelta(weeks=i + 1)
        week_end = now - timedelta(weeks=i)
        tickets = await TicketMongo.find(
            TicketMongo.ward_id == effective_ward,
            TicketMongo.created_at >= week_start,
            TicketMongo.created_at < week_end,
        ).to_list()

        scores = [t.citizen_satisfaction for t in tickets if t.citizen_satisfaction]
        avg = round(sum(scores) / len(scores), 1) if scores else None
        weekly_data.append({
            "week_label": week_end.strftime("W%W %b"),
            "week_start": week_start,
            "avg_satisfaction": avg,
            "ticket_count": len(tickets),
        })

    return weekly_data


@router.get("/top-issues")
async def get_top_issues(
    ward_id: Optional[int] = Query(None),
    limit: int = Query(8, ge=3, le=20),
    current_user: UserMongo = Depends(_require_councillor),
):
    """Most common issue categories in the ward."""
    effective_ward = ward_id or current_user.ward_id

    tickets = await TicketMongo.find(
        TicketMongo.ward_id == effective_ward
    ).to_list()

    category_count: dict = {}
    for t in tickets:
        cat = t.issue_category or "General"
        category_count[cat] = category_count.get(cat, 0) + 1

    sorted_cats = sorted(category_count.items(), key=lambda x: x[1], reverse=True)[:limit]
    total = len(tickets) or 1

    return [
        {
            "category": cat,
            "count": count,
            "percentage": round((count / total) * 100, 1),
        }
        for cat, count in sorted_cats
    ]


@router.get("/overdue-tickets")
async def get_overdue_tickets(
    ward_id: Optional[int] = Query(None),
    limit: int = Query(20),
    current_user: UserMongo = Depends(_require_councillor),
):
    """Tickets that have breached SLA — sorted by most overdue first."""
    effective_ward = ward_id or current_user.ward_id
    now = datetime.utcnow()

    tickets = await TicketMongo.find(
        TicketMongo.ward_id == effective_ward,
        TicketMongo.status.in_([
            TicketStatus.OPEN, TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS
        ]),
    ).to_list()

    overdue = [t for t in tickets if t.sla_deadline and t.sla_deadline < now]
    # Sort by how overdue they are (most overdue first)
    overdue.sort(key=lambda t: t.sla_deadline or now)

    return [
        {
            "id": str(t.id),
            "ticket_code": t.ticket_code,
            "dept_id": t.dept_id,
            "issue_category": t.issue_category or "General",
            "priority_label": t.priority_label,
            "sla_deadline": t.sla_deadline,
            "days_overdue": (now - t.sla_deadline).days if t.sla_deadline else 0,
            "status": t.status,
        }
        for t in overdue[:limit]
    ]


@router.get("/announcement-feed")
async def get_announcement_feed(
    ward_id: Optional[int] = Query(None),
    current_user: UserMongo = Depends(_require_councillor),
):
    """Recent activity feed for the ward (resolved tickets, newly opened critical ones)."""
    effective_ward = ward_id or current_user.ward_id
    since = datetime.utcnow() - timedelta(days=7)

    recent = await TicketMongo.find(
        TicketMongo.ward_id == effective_ward,
        TicketMongo.created_at >= since,
    ).sort(-TicketMongo.priority_score).limit(15).to_list()

    return [
        {
            "id": str(t.id),
            "ticket_code": t.ticket_code,
            "issue_category": t.issue_category or "General",
            "priority_label": t.priority_label,
            "status": t.status,
            "dept_id": t.dept_id,
            "created_at": t.created_at,
        }
        for t in recent
    ]

@router.get("/priority-insights")
async def get_priority_insights(
    ward_id: Optional[int] = Query(None),
    current_user: UserMongo = Depends(_require_councillor),
):
    """
    Ward-level priority intelligence panel for the councillor dashboard.

    Returns:
    - Count of tickets by priority label (CRITICAL / HIGH / MEDIUM / LOW)
    - Top-5 highest-priority open tickets (sorted by score)
    - Priority source breakdown (rules vs hybrid vs ml)
    - Average priority score of open tickets
    """
    effective_ward = ward_id or current_user.ward_id
    open_statuses = [
        TicketStatus.OPEN, TicketStatus.ASSIGNED,
        TicketStatus.IN_PROGRESS, TicketStatus.AWAITING_MATERIAL,
    ]

    tickets = await TicketMongo.find(
        TicketMongo.ward_id == effective_ward,
        TicketMongo.status.in_(open_statuses),
    ).to_list()

    if not tickets:
        return {
            "ward_id": effective_ward,
            "open_ticket_count": 0,
            "by_priority": {},
            "avg_priority_score": 0,
            "top_critical_tickets": [],
            "priority_source_breakdown": {},
        }

    # Count by priority label
    by_priority: dict = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    source_count: dict = {}
    scores = []

    for t in tickets:
        label = t.priority_label.value if t.priority_label else "LOW"
        by_priority[label] = by_priority.get(label, 0) + 1
        src = t.priority_source or "rules"
        source_count[src] = source_count.get(src, 0) + 1
        scores.append(t.priority_score or 0)

    avg_score = round(sum(scores) / len(scores), 1) if scores else 0

    # Top-5 by priority score (descending)
    top_tickets = sorted(tickets, key=lambda t: t.priority_score or 0, reverse=True)[:5]

    now = datetime.utcnow()
    return {
        "ward_id": effective_ward,
        "open_ticket_count": len(tickets),
        "by_priority": by_priority,
        "avg_priority_score": avg_score,
        "priority_source_breakdown": source_count,
        "top_critical_tickets": [
            {
                "id": str(t.id),
                "ticket_code": t.ticket_code,
                "priority_score": t.priority_score,
                "priority_label": t.priority_label,
                "priority_source": t.priority_source,
                "issue_category": t.issue_category or "General",
                "dept_id": t.dept_id,
                "days_open": (now - t.created_at).days,
                "sla_deadline": t.sla_deadline,
                "is_overdue": bool(t.sla_deadline and t.sla_deadline < now),
                "social_media_mentions": t.social_media_mentions,
                "report_count": t.report_count,
            }
            for t in top_tickets
        ],
    }
