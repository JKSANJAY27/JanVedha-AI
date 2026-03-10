"""
Commissioner API — city-level analytics, budget oversight, and system health for the highest authority.
All endpoints return aggregated, read-only data across all wards.
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional
from datetime import datetime, timedelta

from app.core.dependencies import get_current_user
from app.mongodb.models.user import UserMongo
from app.mongodb.models.ticket import TicketMongo
from app.enums import UserRole, TicketStatus, PriorityLabel

router = APIRouter()


def _require_commissioner(current_user: UserMongo = Depends(get_current_user)) -> UserMongo:
    """Allow only commissioners and super admins to access these endpoints."""
    allowed = {UserRole.COMMISSIONER, UserRole.SUPER_ADMIN}
    if current_user.role not in allowed:
        raise HTTPException(status_code=403, detail="Commissioner access required")
    return current_user


@router.get("/city-summary")
async def get_city_summary(current_user: UserMongo = Depends(_require_commissioner)):
    """High-level KPI summary for the entire city."""
    all_tickets = await TicketMongo.find_all().to_list()

    if not all_tickets:
        return {
            "total_tickets": 0,
            "open": 0,
            "closed": 0,
            "overdue": 0,
            "resolution_rate": 0,
            "avg_resolution_days": 0,
            "avg_satisfaction": None,
            "total_estimated_budget": 0,
            "total_spent_budget": 0,
        }

    now = datetime.utcnow()
    closed = [t for t in all_tickets if t.status in {TicketStatus.CLOSED}]
    open_tickets = [t for t in all_tickets if t.status not in {TicketStatus.CLOSED, TicketStatus.REJECTED}]
    overdue = [t for t in open_tickets if t.sla_deadline and t.sla_deadline < now]

    resolution_times = [
        (t.resolved_at - t.created_at).days
        for t in closed if t.resolved_at
    ]
    avg_resolution = round(sum(resolution_times) / len(resolution_times), 1) if resolution_times else 0

    sat_scores = [t.citizen_satisfaction for t in all_tickets if t.citizen_satisfaction]
    avg_sat = round(sum(sat_scores) / len(sat_scores), 1) if sat_scores else None

    total_estimated = sum(t.estimated_cost or 0 for t in all_tickets)
    total_spent = sum(t.estimated_cost or 0 for t in closed) # Using estimated cost for spent cost for now

    return {
        "total_tickets": len(all_tickets),
        "open": len(open_tickets),
        "closed": len(closed),
        "overdue": len(overdue),
        "resolution_rate": round((len(closed) / len(all_tickets)) * 100, 1),
        "avg_resolution_days": avg_resolution,
        "avg_satisfaction": avg_sat,
        "total_estimated_budget": total_estimated,
        "total_spent_budget": total_spent,
    }


@router.get("/ward-performance")
async def get_ward_performance(current_user: UserMongo = Depends(_require_commissioner)):
    """Compare performance across all wards."""
    tickets = await TicketMongo.find_all().to_list()
    now = datetime.utcnow()

    ward_map: dict = {}
    for t in tickets:
        w = t.ward_id or 0 # 0 for unassigned
        if w not in ward_map:
            ward_map[w] = {"ward_id": w, "total": 0, "open": 0, "closed": 0, "overdue": 0, "budget_spent": 0}
        
        ward_map[w]["total"] += 1
        if t.status in {TicketStatus.CLOSED}:
            ward_map[w]["closed"] += 1
            ward_map[w]["budget_spent"] += t.estimated_cost or 0
        else:
            ward_map[w]["open"] += 1
            if t.sla_deadline and t.sla_deadline < now:
                ward_map[w]["overdue"] += 1

    result = list(ward_map.values())
    # Sort by overdue count descending to highlight problem wards
    result.sort(key=lambda x: x["overdue"], reverse=True)
    return result


@router.get("/budget-burn-rate")
async def get_budget_burn_rate(
    weeks: int = Query(12, ge=4, le=52),
    current_user: UserMongo = Depends(_require_commissioner)
):
    """Weekly budget burn rate for the last N weeks."""
    now = datetime.utcnow()
    
    weekly_data = []
    for i in range(weeks - 1, -1, -1):
        week_start = now - timedelta(weeks=i + 1)
        week_end = now - timedelta(weeks=i)
        
        # Tickets resolved in this week
        tickets = await TicketMongo.find(
            TicketMongo.status == TicketStatus.CLOSED,
            TicketMongo.resolved_at >= week_start,
            TicketMongo.resolved_at < week_end,
        ).to_list()

        spent = sum(t.estimated_cost or 0 for t in tickets)
        
        weekly_data.append({
            "week_label": week_end.strftime("W%W %b"),
            "week_start": week_start,
            "budget_spent": spent,
            "resolved_tickets": len(tickets),
        })

    return weekly_data


@router.get("/critical-open-tickets")
async def get_critical_open_tickets(
    limit: int = Query(20, ge=1, le=50),
    current_user: UserMongo = Depends(_require_commissioner)
):
    """City-wide critical tickets that require commissioner attention."""
    open_statuses = [
        TicketStatus.OPEN, TicketStatus.ASSIGNED,
        TicketStatus.IN_PROGRESS, TicketStatus.AWAITING_MATERIAL,
        TicketStatus.PENDING_VERIFICATION,
    ]
    
    # Explicitly fetching tickets with priority score > 80 or label CRITICAL
    tickets = await TicketMongo.find(
        TicketMongo.status.in_(open_statuses),
        TicketMongo.priority_label == PriorityLabel.CRITICAL
    ).sort(-TicketMongo.priority_score).limit(limit).to_list()
    
    now = datetime.utcnow()
    return [
        {
            "id": str(t.id),
            "ticket_code": t.ticket_code,
            "ward_id": t.ward_id,
            "dept_id": t.dept_id,
            "issue_category": t.issue_category or "General",
            "priority_score": t.priority_score,
            "sla_deadline": t.sla_deadline,
            "days_overdue": (now - t.sla_deadline).days if t.sla_deadline and t.sla_deadline < now else 0,
            "estimated_cost": t.estimated_cost,
        }
        for t in tickets
    ]
