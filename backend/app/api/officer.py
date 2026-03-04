"""
Officer API — authenticated endpoints for ward/dept officers.
Fully rewritten to use MongoDB (Beanie).
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.core.dependencies import get_current_user, require_ward_officer
from app.mongodb.models.user import UserMongo
from app.mongodb.models.ticket import TicketMongo
from app.services.ticket_service import TicketService
from app.enums import UserRole, PriorityLabel

router = APIRouter()


# ─── Ticket Listing ──────────────────────────────────────────────────────────

@router.get("/tickets")
async def get_tickets(
    current_user: UserMongo = Depends(get_current_user),
    limit: int = 50,
):
    """
    Returns tickets scoped to the officer's role:
    - WARD_OFFICER / COUNCILLOR → filtered by ward_id
    - ZONAL_OFFICER → filtered by zone_id
    - DEPT_HEAD → filtered by dept_id
    - TECHNICIAN → tickets assigned specifically to them
    - COMMISSIONER / SUPER_ADMIN → all tickets
    """
    if current_user.role in {UserRole.WARD_OFFICER, UserRole.COUNCILLOR}:
        tickets = await TicketMongo.find(
            TicketMongo.ward_id == current_user.ward_id
        ).sort(-TicketMongo.priority_score).limit(limit).to_list()

    elif current_user.role == UserRole.ZONAL_OFFICER:
        tickets = await TicketMongo.find(
            TicketMongo.zone_id == current_user.zone_id
        ).sort(-TicketMongo.priority_score).limit(limit).to_list()

    elif current_user.role == UserRole.DEPT_HEAD:
        tickets = await TicketMongo.find(
            TicketMongo.dept_id == current_user.dept_id,
            TicketMongo.ward_id == current_user.ward_id,
        ).sort(-TicketMongo.priority_score).limit(limit).to_list()

    elif current_user.role == UserRole.TECHNICIAN:
        tickets = await TicketMongo.find(
            TicketMongo.technician_id == str(current_user.id)
        ).sort(-TicketMongo.priority_score).limit(limit).to_list()

    else:
        # Commissioner / Super Admin
        tickets = await TicketMongo.find_all().sort(
            -TicketMongo.priority_score
        ).limit(limit).to_list()

    return [_ticket_list_item(t) for t in tickets]


@router.get("/tickets/assigned-to-me")
async def get_my_tickets(
    current_user: UserMongo = Depends(get_current_user),
):
    """Returns tickets directly assigned to the current officer/technician."""
    if current_user.role == UserRole.TECHNICIAN:
        tickets = await TicketMongo.find(
            TicketMongo.technician_id == str(current_user.id)
        ).sort(-TicketMongo.priority_score).to_list()
    else:
        tickets = await TicketMongo.find(
            TicketMongo.assigned_officer_id == str(current_user.id)
        ).sort(-TicketMongo.priority_score).to_list()

    return [_ticket_list_item(t) for t in tickets]


@router.get("/dashboard/summary")
async def get_dashboard_summary(
    current_user: UserMongo = Depends(get_current_user),
):
    """
    Supervisory overview for Ward PGO — per-department ticket breakdown,
    SLA breach counts, and satisfacton average.
    """
    from datetime import datetime

    if current_user.role in {UserRole.WARD_OFFICER, UserRole.COUNCILLOR}:
        all_tickets = await TicketMongo.find(
            TicketMongo.ward_id == current_user.ward_id
        ).to_list()
    elif current_user.role == UserRole.DEPT_HEAD:
        all_tickets = await TicketMongo.find(
            TicketMongo.dept_id == current_user.dept_id,
            TicketMongo.ward_id == current_user.ward_id,
        ).to_list()
    else:
        all_tickets = await TicketMongo.find_all().to_list()

    now = datetime.utcnow()
    open_statuses = {"OPEN", "ASSIGNED", "IN_PROGRESS", "AWAITING_MATERIAL", "PENDING_VERIFICATION"}

    dept_stats: dict = {}
    total_open = 0
    total_overdue = 0
    total_critical = 0

    for t in all_tickets:
        d = t.dept_id
        if d not in dept_stats:
            dept_stats[d] = {"dept_id": d, "open": 0, "closed": 0, "overdue": 0, "critical": 0}

        if t.status in open_statuses:
            dept_stats[d]["open"] += 1
            total_open += 1
            if t.sla_deadline and t.sla_deadline < now:
                dept_stats[d]["overdue"] += 1
                total_overdue += 1
        else:
            dept_stats[d]["closed"] += 1

        if t.priority_label == "CRITICAL":
            dept_stats[d]["critical"] += 1
            total_critical += 1

    sat_scores = [t.citizen_satisfaction for t in all_tickets if t.citizen_satisfaction]
    avg_sat = round(sum(sat_scores) / len(sat_scores), 1) if sat_scores else None

    return {
        "total": len(all_tickets),
        "open": total_open,
        "closed": len(all_tickets) - total_open,
        "overdue": total_overdue,
        "critical": total_critical,
        "avg_satisfaction": avg_sat,
        "by_department": list(dept_stats.values()),
    }


# ─── Ticket Detail ────────────────────────────────────────────────────────────

@router.get("/tickets/{ticket_id}")
async def get_ticket(
    ticket_id: str,
    current_user: UserMongo = Depends(get_current_user),
):
    from beanie import PydanticObjectId
    ticket = await TicketMongo.get(PydanticObjectId(ticket_id))
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {
        "id": str(ticket.id),
        "ticket_code": ticket.ticket_code,
        "status": ticket.status,
        "description": ticket.description,
        "dept_id": ticket.dept_id,
        "issue_category": ticket.issue_category,
        "priority_label": ticket.priority_label,
        "priority_score": ticket.priority_score,
        "priority_source": ticket.priority_source,
        "ai_routing_reason": ticket.ai_routing_reason,
        "suggestions": ticket.ai_suggestions,
        "seasonal_alert": ticket.seasonal_alert,
        "reporter_name": ticket.reporter_name,
        "ward_id": ticket.ward_id,
        "sla_deadline": ticket.sla_deadline,
        "created_at": ticket.created_at,
        "assigned_officer_id": ticket.assigned_officer_id,
        "technician_id": ticket.technician_id,
        "scheduled_date": ticket.scheduled_date,
        "ai_suggested_date": ticket.ai_suggested_date,
        "status_timeline": ticket.status_timeline,
        "remarks": ticket.remarks,
        "photo_url": ticket.photo_url,
        "before_photo_url": ticket.before_photo_url,
        "after_photo_url": ticket.after_photo_url,
    }


# ─── Actions ──────────────────────────────────────────────────────────────────

class StatusUpdateEvent(BaseModel):
    status: str
    reason: Optional[str] = None
    new_dept_id: Optional[str] = None


@router.patch("/tickets/{ticket_id}/status")
async def update_status(
    ticket_id: str,
    event: StatusUpdateEvent,
    current_user: UserMongo = Depends(require_ward_officer),
):
    ticket = await TicketService.change_status(
        ticket_id=ticket_id,
        new_status=event.status,
        actor_id=str(current_user.id),
        actor_role=current_user.role,
        reason=event.reason,
        new_dept_id=event.new_dept_id,
    )
    # Append to status_timeline
    ticket.status_timeline.append({
        "status": event.status,
        "timestamp": datetime.utcnow().isoformat(),
        "actor_role": current_user.role,
        "note": event.reason or "",
    })
    await ticket.save()
    return {"id": str(ticket.id), "status": ticket.status}


class AssignRequest(BaseModel):
    officer_id: Optional[str] = None
    technician_id: Optional[str] = None


@router.post("/tickets/{ticket_id}/assign")
async def assign_ticket(
    ticket_id: str,
    data: AssignRequest,
    current_user: UserMongo = Depends(require_ward_officer),
):
    """Assign a ticket to an officer and/or a field technician."""
    from beanie import PydanticObjectId
    ticket = await TicketMongo.get(PydanticObjectId(ticket_id))
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if data.officer_id:
        ticket.assigned_officer_id = data.officer_id
        ticket.assigned_at = datetime.utcnow()
        if ticket.status == "OPEN":
            ticket.status = "ASSIGNED"  # type: ignore

    if data.technician_id:
        ticket.technician_id = data.technician_id

    ticket.status_timeline.append({
        "status": "ASSIGNED",
        "timestamp": datetime.utcnow().isoformat(),
        "actor_role": current_user.role,
        "note": f"Assigned by {current_user.name}",
    })
    await ticket.save()
    return {
        "id": str(ticket.id),
        "assigned_officer_id": ticket.assigned_officer_id,
        "technician_id": ticket.technician_id,
        "status": ticket.status,
    }


class RemarkRequest(BaseModel):
    text: str


@router.post("/tickets/{ticket_id}/remark")
async def add_remark(
    ticket_id: str,
    data: RemarkRequest,
    current_user: UserMongo = Depends(get_current_user),
):
    """Add an officer remark to a ticket."""
    from beanie import PydanticObjectId
    ticket = await TicketMongo.get(PydanticObjectId(ticket_id))
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket.remarks.append({
        "text": data.text,
        "timestamp": datetime.utcnow().isoformat(),
        "officer_id": str(current_user.id),
        "officer_role": current_user.role,
    })
    await ticket.save()
    return {"message": "Remark added", "total_remarks": len(ticket.remarks)}


class ScheduleRequest(BaseModel):
    scheduled_date: datetime


@router.patch("/tickets/{ticket_id}/schedule")
async def schedule_ticket(
    ticket_id: str,
    data: ScheduleRequest,
    current_user: UserMongo = Depends(require_ward_officer),
):
    """Set or update the scheduled work date for a ticket."""
    from beanie import PydanticObjectId
    ticket = await TicketMongo.get(PydanticObjectId(ticket_id))
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket.scheduled_date = data.scheduled_date
    ticket.status_timeline.append({
        "status": "SCHEDULED",
        "timestamp": datetime.utcnow().isoformat(),
        "actor_role": current_user.role,
        "note": f"Work scheduled for {data.scheduled_date.strftime('%d %b %Y')} by {current_user.name}",
    })
    await ticket.save()
    return {"id": str(ticket.id), "scheduled_date": ticket.scheduled_date}


class OverridePriorityEvent(BaseModel):
    priority_score: float
    reason: str


@router.post("/tickets/{ticket_id}/override-priority")
async def override_priority(
    ticket_id: str,
    event: OverridePriorityEvent,
    current_user: UserMongo = Depends(require_ward_officer),
):
    from beanie import PydanticObjectId

    ticket = await TicketMongo.get(PydanticObjectId(ticket_id))
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Clamp and re-label
    score = max(0.0, min(100.0, event.priority_score))
    if score >= 80:
        label = PriorityLabel.CRITICAL
    elif score >= 60:
        label = PriorityLabel.HIGH
    elif score >= 35:
        label = PriorityLabel.MEDIUM
    else:
        label = PriorityLabel.LOW

    ticket.priority_score = score
    ticket.priority_label = label
    ticket.priority_source = "human_override"
    await ticket.save()

    return {
        "id": str(ticket.id),
        "priority_score": ticket.priority_score,
        "priority_label": ticket.priority_label,
        "priority_source": ticket.priority_source,
    }


# ─── Helper ───────────────────────────────────────────────────────────────────

def _ticket_list_item(t: TicketMongo) -> dict:
    return {
        "id": str(t.id),
        "ticket_code": t.ticket_code,
        "status": t.status,
        "dept_id": t.dept_id,
        "issue_category": t.issue_category,
        "priority_label": t.priority_label,
        "priority_score": t.priority_score,
        "created_at": t.created_at,
        "sla_deadline": t.sla_deadline,
        "ward_id": t.ward_id,
        "seasonal_alert": t.seasonal_alert,
        "assigned_officer_id": t.assigned_officer_id,
        "technician_id": t.technician_id,
        "scheduled_date": t.scheduled_date,
        "ai_suggested_date": t.ai_suggested_date,
    }
