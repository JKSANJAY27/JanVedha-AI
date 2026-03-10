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
    if current_user.role == UserRole.SUPERVISOR:
        # Supervisors see ALL tickets — they are the routing authority
        tickets = await TicketMongo.find_all().sort(
            -TicketMongo.priority_score
        ).limit(limit).to_list()

    elif current_user.role == UserRole.COUNCILLOR:
        # Councillors are scoped to their ward
        if current_user.ward_id is not None:
            tickets = await TicketMongo.find(
                TicketMongo.ward_id == current_user.ward_id
            ).sort(-TicketMongo.priority_score).limit(limit).to_list()
        else:
            tickets = await TicketMongo.find_all().sort(
                -TicketMongo.priority_score
            ).limit(limit).to_list()

    elif current_user.role == UserRole.JUNIOR_ENGINEER:
        # JE sees tickets for their dept (ward filter is optional)
        query_filters = [TicketMongo.dept_id == current_user.dept_id]
        if current_user.ward_id is not None:
            query_filters.append(TicketMongo.ward_id == current_user.ward_id)
        tickets = await TicketMongo.find(
            *query_filters
        ).sort(-TicketMongo.priority_score).limit(limit).to_list()

    elif current_user.role == UserRole.FIELD_STAFF:
        tickets = await TicketMongo.find(
            TicketMongo.technician_id == str(current_user.id)
        ).sort(-TicketMongo.priority_score).limit(limit).to_list()

    else:
        # Commissioner / Super Admin — all tickets
        tickets = await TicketMongo.find_all().sort(
            -TicketMongo.priority_score
        ).limit(limit).to_list()

    return [_ticket_list_item(t) for t in tickets]


@router.get("/tickets/assigned-to-me")
async def get_my_tickets(
    current_user: UserMongo = Depends(get_current_user),
):
    """Returns tickets directly assigned to the current officer/technician."""
    if current_user.role == UserRole.FIELD_STAFF:
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

    if current_user.role == UserRole.SUPERVISOR:
        # Supervisors see all tickets for the full operational picture
        all_tickets = await TicketMongo.find_all().to_list()
    elif current_user.role == UserRole.COUNCILLOR:
        if current_user.ward_id is not None:
            all_tickets = await TicketMongo.find(
                TicketMongo.ward_id == current_user.ward_id
            ).to_list()
        else:
            all_tickets = await TicketMongo.find_all().to_list()
    elif current_user.role == UserRole.JUNIOR_ENGINEER:
        query_filters = [TicketMongo.dept_id == current_user.dept_id]
        if current_user.ward_id is not None:
            query_filters.append(TicketMongo.ward_id == current_user.ward_id)
        all_tickets = await TicketMongo.find(*query_filters).to_list()
    else:
        all_tickets = await TicketMongo.find_all().to_list()

    now = datetime.utcnow()
    open_statuses = {"OPEN", "ASSIGNED", "SCHEDULED", "IN_PROGRESS"}

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
        "completion_deadline": ticket.completion_deadline,
        "completion_deadline_confirmed_by": ticket.completion_deadline_confirmed_by,
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

class ValidateRequest(BaseModel):
    category_confirmed: bool
    is_duplicate: bool
    ward_confirmed: bool

@router.post("/tickets/{ticket_id}/validate")
async def validate_ticket(
    ticket_id: str,
    data: ValidateRequest,
    current_user: UserMongo = Depends(require_ward_officer),
):
    """Supervisor validates a ticket before assignment."""
    from beanie import PydanticObjectId
    ticket = await TicketMongo.get(PydanticObjectId(ticket_id))
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket.is_validated = True
    ticket.status_timeline.append({
        "status": ticket.status,
        "timestamp": datetime.utcnow().isoformat(),
        "actor_role": current_user.role,
        "note": f"Validated by {current_user.name}. Category OK: {data.category_confirmed}, Duplicate: {data.is_duplicate}, Ward OK: {data.ward_confirmed}.",
    })
    await ticket.save()
    return {"id": str(ticket.id), "status": ticket.status, "is_validated": ticket.is_validated}

@router.get("/staff/junior-engineers")
async def get_junior_engineers(
    current_user: UserMongo = Depends(require_ward_officer),
):
    """Fetch Junior Engineers for the current ward."""
    engineers = await UserMongo.find(
        UserMongo.role == UserRole.JUNIOR_ENGINEER,
        UserMongo.ward_id == current_user.ward_id
    ).to_list()
    
    return [
        {"id": str(je.id), "name": je.name, "email": je.email}
        for je in engineers
    ]


@router.get("/staff/field")
async def get_field_staff(
    current_user: UserMongo = Depends(require_ward_officer),
):
    """Fetch Field Staff for the current ward."""
    staff = await UserMongo.find(
        UserMongo.role == UserRole.FIELD_STAFF,
        UserMongo.ward_id == current_user.ward_id
    ).to_list()
    
    return [
        {"id": str(s.id), "name": s.name, "email": s.email}
        for s in staff
    ]


class AssignFieldRequest(BaseModel):
    technician_id: str
    scheduled_date: datetime


@router.post("/tickets/{ticket_id}/assign-field")
async def assign_field_staff(
    ticket_id: str,
    data: AssignFieldRequest,
    current_user: UserMongo = Depends(require_ward_officer),
):
    """Assign a ticket to a field technician. Automatically sets status to IN_PROGRESS."""
    from beanie import PydanticObjectId
    ticket = await TicketMongo.get(PydanticObjectId(ticket_id))
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket.technician_id = data.technician_id
    ticket.scheduled_date = data.scheduled_date
    # Once a technician is assigned, work begins → IN_PROGRESS
    ticket.status = TicketStatus.IN_PROGRESS  # type: ignore

    ticket.status_timeline.append({
        "status": "IN_PROGRESS",
        "timestamp": datetime.utcnow().isoformat(),
        "actor_role": current_user.role,
        "note": f"Field technician assigned and work started for {data.scheduled_date.strftime('%Y-%m-%d')} by {current_user.name}",
    })
    await ticket.save()
    return {
        "id": str(ticket.id),
        "status": ticket.status,
        "technician_id": ticket.technician_id,
        "scheduled_date": ticket.scheduled_date
    }


@router.get("/tickets/{ticket_id}/smart-schedule")
async def get_smart_schedule(
    ticket_id: str,
    current_user: UserMongo = Depends(require_ward_officer),
):
    from app.services.ai.smart_assigner import generate_smart_schedule
    result = await generate_smart_schedule(ticket_id)
    if not result:
        raise HTTPException(status_code=400, detail="Cannot generate schedule. Ensure technicians exist in this ward/dept and the ticket is valid.")
    return result


class SmartAssignReassignment(BaseModel):
    ticket_id: str
    new_date: datetime
    new_technician_id: str

class SmartAssignRequest(BaseModel):
    suggested_date: datetime
    suggested_technician_id: str
    postponed_tickets: List[SmartAssignReassignment] = []


@router.post("/tickets/{ticket_id}/smart-assign")
async def apply_smart_schedule(
    ticket_id: str,
    data: SmartAssignRequest,
    current_user: UserMongo = Depends(require_ward_officer),
):
    from beanie import PydanticObjectId
    
    target_ticket = await TicketMongo.get(PydanticObjectId(ticket_id))
    if not target_ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    target_ticket.technician_id = data.suggested_technician_id
    target_ticket.scheduled_date = data.suggested_date
    if target_ticket.status in [TicketStatus.OPEN, TicketStatus.ASSIGNED]:
        target_ticket.status = TicketStatus.SCHEDULED  # type: ignore
    
    target_ticket.status_timeline.append({
        "status": target_ticket.status,
        "timestamp": datetime.utcnow().isoformat(),
        "actor_role": current_user.role,
        "note": f"Smart assigned to field staff and scheduled for {data.suggested_date.strftime('%Y-%m-%d')} by AI Suggestion",
    })
    await target_ticket.save()

    # Apply postponements
    for p in data.postponed_tickets:
        pt_ticket = await TicketMongo.get(PydanticObjectId(p.ticket_id))
        if pt_ticket:
            old_date_str = pt_ticket.scheduled_date.strftime('%Y-%m-%d') if pt_ticket.scheduled_date else 'Unknown'
            pt_ticket.technician_id = p.new_technician_id
            pt_ticket.scheduled_date = p.new_date
            pt_ticket.status_timeline.append({
                "status": pt_ticket.status,
                "timestamp": datetime.utcnow().isoformat(),
                "actor_role": current_user.role,
                "note": f"Automatically postponed from {old_date_str} to {p.new_date.strftime('%Y-%m-%d')} to accommodate higher priority issue.",
            })
            await pt_ticket.save()

    return {"message": "Smart assignment applied successfully."}


class SeedTechRequest(BaseModel):
    dept_id: str

@router.post("/staff/seed-technicians")
async def seed_technicians(
    data: SeedTechRequest,
    current_user: UserMongo = Depends(require_ward_officer),
):
    ward_id = current_user.ward_id
    if not ward_id:
        raise HTTPException(status_code=400, detail="User must have a ward_id")
    
    # Check if already seeded
    existing = await UserMongo.find(UserMongo.role == UserRole.FIELD_STAFF, UserMongo.ward_id == ward_id, UserMongo.dept_id == data.dept_id).to_list()
    if existing:
        return {"message": f"Technicians already exist in Ward {ward_id} for Dept {data.dept_id}"}
    
    import random
    names = ["Raju", "Kartik", "Suresh"]
    for i, name in enumerate(names):
        code = str(random.randint(1000, 9999))
        tech = UserMongo(
            name=f"{name} (Tech)",
            phone=f"9900{ward_id}{i}{code}",
            email=f"tech_{ward_id}_{data.dept_id}_{i}_{code}@janvedha.local",
            role=UserRole.FIELD_STAFF,
            ward_id=ward_id,
            dept_id=data.dept_id,
        )
        await tech.insert()
    
    return {"message": f"Successfully seeded 3 technicians in Ward {ward_id} for Dept {data.dept_id}"}


class ProofUploadRequest(BaseModel):
    photo_url: str


@router.post("/tickets/{ticket_id}/proof")
async def upload_proof(
    ticket_id: str,
    data: ProofUploadRequest,
    current_user: UserMongo = Depends(require_ward_officer),
):
    from beanie import PydanticObjectId
    ticket = await TicketMongo.get(PydanticObjectId(ticket_id))
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket.after_photo_url = data.photo_url
    ticket.status_timeline.append({
        "status": ticket.status,
        "timestamp": datetime.utcnow().isoformat(),
        "actor_role": current_user.role,
        "note": f"Proof uploaded by {current_user.name}",
    })
    await ticket.save()
    return {"id": str(ticket.id), "after_photo_url": ticket.after_photo_url}


@router.get("/tickets/{ticket_id}/location-history")
async def get_location_history(
    ticket_id: str,
    current_user: UserMongo = Depends(get_current_user),
):
    """Get recent tickets in the same ward with the same category to identify recurring issues."""
    from beanie import PydanticObjectId
    ticket = await TicketMongo.get(PydanticObjectId(ticket_id))
    if not ticket or not ticket.ward_id:
        return []

    history = await TicketMongo.find(
        TicketMongo.ward_id == ticket.ward_id,
        TicketMongo.issue_category == ticket.issue_category,
        TicketMongo.id != ticket.id
    ).sort(-TicketMongo.created_at).limit(5).to_list()

    return [
        {
            "id": str(t.id),
            "ticket_code": t.ticket_code,
            "status": t.status,
            "created_at": t.created_at,
            "description": t.description
        }
        for t in history
    ]


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


# ─── Completion Deadline ───────────────────────────────────────────────────────

class CompletionDeadlineRequest(BaseModel):
    completion_deadline: datetime
    use_ai_suggestion: bool = False


@router.patch("/tickets/{ticket_id}/set-completion-deadline")
async def set_completion_deadline(
    ticket_id: str,
    data: CompletionDeadlineRequest,
    current_user: UserMongo = Depends(require_ward_officer),
):
    """
    Supervisor sets a completion deadline for a ticket.
    - Must not breach the SLA deadline.
    - Creates a calendar reminder event of type 'deadline'.
    - Stores on ticket as completion_deadline.
    """
    from beanie import PydanticObjectId
    from app.mongodb.models.scheduled_event import ScheduledEventMongo

    ticket = await TicketMongo.get(PydanticObjectId(ticket_id))
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Normalize incoming datetime to naive UTC
    requested_deadline = data.completion_deadline.replace(tzinfo=None)
    now_utc = datetime.utcnow()

    # ── SLA Guard ─────────────────────────────────────────────────────────────
    if ticket.sla_deadline and requested_deadline > ticket.sla_deadline:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Completion deadline would breach SLA",
                "sla_deadline": ticket.sla_deadline.isoformat(),
                "requested": requested_deadline.isoformat(),
            },
        )

    if requested_deadline < now_utc:
        raise HTTPException(
            status_code=400, detail="Completion deadline cannot be in the past"
        )

    # ── Save deadline on ticket ───────────────────────────────────────────────
    ticket.completion_deadline = requested_deadline
    ticket.completion_deadline_confirmed_by = str(current_user.id)
    # Setting the completion deadline means the JE has planned this — auto-set SCHEDULED
    if ticket.status in ["OPEN", "ASSIGNED"]:
        from app.enums import TicketStatus as _TS
        ticket.status = _TS.SCHEDULED  # type: ignore
    ticket.status_timeline.append({
        "status": "SCHEDULED",
        "timestamp": now_utc.isoformat(),
        "actor_role": current_user.role,
        "note": (
            f"⏰ Completion deadline set to {requested_deadline.strftime('%d %b %Y')} "
            f"by {current_user.name}"
            + (" (AI suggestion accepted)" if data.use_ai_suggestion else " (manual override)")
        ),
    })
    await ticket.save()

    # ── Create / update calendar reminder event ───────────────────────────────
    # Remove any existing deadline event for this ticket
    await ScheduledEventMongo.find(
        ScheduledEventMongo.ticket_id == ticket_id,
        ScheduledEventMongo.event_type == "deadline",
    ).delete()

    event_obj = ScheduledEventMongo(
        dept_id=ticket.dept_id,
        ward_id=ticket.ward_id,
        ticket_id=ticket_id,
        ticket_code=ticket.ticket_code,
        scheduled_date=requested_deadline,
        is_ai_suggested=data.use_ai_suggestion,
        event_type="deadline",
        officer_id=str(current_user.id),
        priority_label=ticket.priority_label,
        issue_category=ticket.issue_category,
        ticket_description=ticket.description[:120] if ticket.description else None,
        notes=(
            f"⏰ Completion deadline reminder for ticket {ticket.ticket_code}. "
            f"SLA: {ticket.sla_deadline.strftime('%d %b %Y') if ticket.sla_deadline else 'N/A'}."
        ),
    )
    await event_obj.insert()

    return {
        "id": str(ticket.id),
        "ticket_code": ticket.ticket_code,
        "completion_deadline": ticket.completion_deadline,
        "sla_deadline": ticket.sla_deadline,
        "calendar_event_id": str(event_obj.id),
        "is_ai_suggestion": data.use_ai_suggestion,
    }



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


# ─── Priority Explainability ───────────────────────────────────────────────────

@router.get("/tickets/{ticket_id}/priority-explain")
async def explain_ticket_priority(
    ticket_id: str,
    current_user: UserMongo = Depends(get_current_user),
):
    """
    Returns an explainable breakdown of WHY a ticket received its priority score.

    Response includes:
    - Overall rule score and label
    - Per-component sub-scores (severity, impact, age, SLA, social)
    - ML model label probabilities (if model is active)
    - SHAP feature importance (if shap is installed)
    - Human-readable summary for the 'Why is this CRITICAL?' dashboard panel

    Perfect for councillor ward oversight and officer decision support.
    """
    from beanie import PydanticObjectId
    from datetime import datetime
    from app.services.ai.priority_agent import explain_priority

    ticket = await TicketMongo.get(PydanticObjectId(ticket_id))
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    now = datetime.utcnow()
    days_open = (now - ticket.created_at).days
    hours_remaining = (
        (ticket.sla_deadline - now).total_seconds() / 3600
        if ticket.sla_deadline else 168.0
    )

    explanation = explain_priority(
        issue_category=ticket.issue_category or "default",
        description=ticket.description,
        dept_id=ticket.dept_id,
        report_count=ticket.report_count,
        location_type="unknown",
        days_open=days_open,
        hours_until_sla_breach=hours_remaining,
        social_media_mentions=ticket.social_media_mentions,
        month=ticket.created_at.month,
        ward_id=ticket.ward_id or 0,
        day_of_week=ticket.created_at.weekday(),
        hour_of_day=ticket.created_at.hour,
    )

    return {
        "ticket_code": ticket.ticket_code,
        "stored_priority_score": ticket.priority_score,
        "stored_priority_label": ticket.priority_label,
        "stored_priority_source": ticket.priority_source,
        **explanation,
    }


class RecalculateRequest(BaseModel):
    new_report_count: Optional[int] = None
    new_social_mentions: Optional[int] = None


@router.post("/tickets/{ticket_id}/recalculate-priority")
async def recalculate_ticket_priority(
    ticket_id: str,
    data: RecalculateRequest,
    current_user: UserMongo = Depends(require_ward_officer),
):
    """
    Re-run priority scoring on an existing ticket with updated signals.
    Use this when:
    - The real-time scraper detects more social mentions of this complaint
    - Citizens have reported the same issue multiple times (report_count increased)

    This is the hook the Scrapify Labs integration will call.
    """
    from app.services.ai.priority_agent import recalculate_priority

    result = await recalculate_priority(
        ticket_id=ticket_id,
        new_report_count=data.new_report_count,
        new_social_mentions=data.new_social_mentions,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Ticket not found or recalculation failed")

    new_score, new_label, source = result
    return {
        "ticket_id": ticket_id,
        "new_priority_score": new_score,
        "new_priority_label": new_label,
        "source": source,
    }


# ─── Work Completion Verification ─────────────────────────────────────────────

class WorkCompletionRequest(BaseModel):
    after_photo_url: str                   # URL of the "after" photo submitted by technician
    notes: Optional[str] = None           # Optional technician notes


@router.post("/tickets/{ticket_id}/verify-completion")
async def verify_work_completion(
    ticket_id: str,
    data: WorkCompletionRequest,
    current_user: UserMongo = Depends(get_current_user),
):
    """
    Technician submits an 'after' photo and the AI verifies if the civic issue
    has been resolved by comparing it with the original 'before' photo.

    Flow:
    1. Technician takes after photo on site and submits its URL here
    2. System fetches both before (from ticket) & after images
    3. Gemini Vision analyses both + issue context → verdict
    4. Ticket updated with: after_photo_url, work_verified, verification result
    5. Status auto-transitions to PENDING_VERIFICATION (officer can then CLOSE)

    Args:
        ticket_id: MongoDB ObjectId of the ticket
        after_photo_url: URL of the technician's after-work photo
    """
    from beanie import PydanticObjectId
    from datetime import datetime
    from app.services.ai.work_verifier import verify_work_completion as _verify

    ticket = await TicketMongo.get(PydanticObjectId(ticket_id))
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Only technicians or ward officers can submit completion
    allowed = {UserRole.TECHNICIAN, UserRole.WARD_OFFICER,
               UserRole.COMMISSIONER, UserRole.SUPER_ADMIN}
    if current_user.role not in allowed:
        raise HTTPException(status_code=403, detail="Only technicians/officers can verify completion")

    # Need a before photo for comparison
    if not ticket.before_photo_url and not ticket.photo_url:
        # No before image — store result but cannot do AI verification
        ticket.after_photo_url = data.after_photo_url
        ticket.work_verified = None   # indeterminate
        ticket.work_verification_confidence = 0.0
        ticket.work_verification_method = "no_before_image"
        ticket.work_verification_explanation = (
            "Work marked as submitted. No before-photo was attached to this ticket, "
            "so AI comparison is not possible. Manual officer review required."
        )
        ticket.work_verified_at = datetime.utcnow()
        if ticket.status not in {"CLOSED", "REJECTED"}:
            ticket.status = "PENDING_VERIFICATION"  # type: ignore
        ticket.status_timeline.append({
            "status": "PENDING_VERIFICATION",
            "timestamp": datetime.utcnow().isoformat(),
            "actor_role": current_user.role,
            "note": f"After photo submitted (no before photo for AI comparison). Notes: {data.notes or ''}",
        })
        await ticket.save()
        return {
            "ticket_code": ticket.ticket_code,
            "work_verified": None,
            "confidence": 0.0,
            "method": "no_before_image",
            "explanation": ticket.work_verification_explanation,
            "change_detected": False,
        }

    before_url = ticket.before_photo_url or ticket.photo_url

    # Run AI verification (3-tier fallback: Gemini → SSIM → pixel)
    result = await _verify(
        before_url=before_url,
        after_url=data.after_photo_url,
        issue_category=ticket.issue_category or "general",
        description=ticket.description,
    )

    # Persist results to ticket
    ticket.after_photo_url = data.after_photo_url
    ticket.work_verified = result.verified
    ticket.work_verification_confidence = result.confidence
    ticket.work_verification_method = result.method
    ticket.work_verification_explanation = result.explanation
    ticket.work_verified_at = datetime.utcnow()

    # Auto-transition status
    if ticket.status not in {"CLOSED", "REJECTED"}:
        ticket.status = "PENDING_VERIFICATION"  # type: ignore

    ticket.status_timeline.append({
        "status": "PENDING_VERIFICATION",
        "timestamp": datetime.utcnow().isoformat(),
        "actor_role": current_user.role,
        "note": (
            f"AI Work Verification: {'✅ VERIFIED' if result.verified else '❌ NOT VERIFIED'} "
            f"(confidence={result.confidence:.0%}, method={result.method}). "
            f"{result.explanation}. "
            f"Notes: {data.notes or 'None'}"
        ),
    })

    await ticket.save()

    return {
        "ticket_code": ticket.ticket_code,
        **result.to_dict(),
        "ssim_score": result.ssim_score,
        "phash_distance": result.phash_distance,
        "status_updated_to": "PENDING_VERIFICATION",
    }


@router.get("/tickets/{ticket_id}/verification-result")
async def get_verification_result(
    ticket_id: str,
    current_user: UserMongo = Depends(get_current_user),
):
    """
    Returns the stored AI work verification result for a ticket.
    Used by the officer/councillor dashboard to display verification status.
    """
    from beanie import PydanticObjectId

    ticket = await TicketMongo.get(PydanticObjectId(ticket_id))
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return {
        "ticket_code": ticket.ticket_code,
        "before_photo_url": ticket.before_photo_url or ticket.photo_url,
        "after_photo_url": ticket.after_photo_url,
        "work_verified": ticket.work_verified,
        "confidence": ticket.work_verification_confidence,
        "method": ticket.work_verification_method,
        "explanation": ticket.work_verification_explanation,
        "verified_at": ticket.work_verified_at,
        "status": ticket.status,
    }


# ─── Helper ───────────────────────────────────────────────────────────────────

def _ticket_list_item(t: TicketMongo) -> dict:
    lat = t.location["coordinates"][1] if t.location and "coordinates" in t.location else None
    lng = t.location["coordinates"][0] if t.location and "coordinates" in t.location else None
    return {
        "id": str(t.id),
        "ticket_code": t.ticket_code,
        "status": t.status,
        "description": t.description,
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
        "work_verified": t.work_verified,
        "work_verification_confidence": t.work_verification_confidence,
        "lat": lat,
        "lng": lng,
    }
