"""
Officer API — authenticated endpoints for ward/dept officers.
Fully rewritten to use MongoDB (Beanie).
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.core.dependencies import get_current_user, require_ward_officer
from app.mongodb.models.user import UserMongo
from app.mongodb.models.ticket import TicketMongo
from app.services.ticket_service import TicketService
from app.enums import UserRole

router = APIRouter()


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
            TicketMongo.dept_id == current_user.dept_id
        ).sort(-TicketMongo.priority_score).limit(limit).to_list()

    else:
        # Commissioner / Super Admin
        tickets = await TicketMongo.find_all().sort(
            -TicketMongo.priority_score
        ).limit(limit).to_list()

    return [
        {
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
        }
        for t in tickets
    ]


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
    }


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
    return {"id": str(ticket.id), "status": ticket.status}


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
    from app.enums import PriorityLabel

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
