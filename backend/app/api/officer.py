from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_ward_officer
from app.models.user import User
from app.models.ticket import Ticket
from app.services.ticket_service import TicketService

router = APIRouter()

@router.get("/tickets")
async def get_tickets(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Very basic list for Phase 1 MVP
    result = await db.execute(select(Ticket))
    return result.scalars().all()

@router.get("/tickets/{id}")
async def get_ticket(id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Ticket).where(Ticket.id == id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket

class StatusUpdateEvent(BaseModel):
    status: str
    reason: str = None

@router.patch("/tickets/{id}/status")
async def update_status(id: int, event: StatusUpdateEvent, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_ward_officer)):
    ticket = await TicketService.change_status(
        db=db,
        ticket_id=id,
        new_status=event.status,
        actor_id=current_user.id,
        actor_role=current_user.role,
        reason=event.reason
    )
    await db.commit()
    return {"id": ticket.id, "status": ticket.status}

from app.services.approval_service import ApprovalService

class BudgetApproveEvent(BaseModel):
    amount: float

@router.post("/tickets/{id}/approve-budget")
async def approve_budget(id: int, event: BudgetApproveEvent, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await ApprovalService.approve_budget(
        db=db,
        ticket_id=id,
        actor_id=current_user.id,
        actor_role=current_user.role,
        amount=event.amount
    )

class OverridePriorityEvent(BaseModel):
    priority_score: float
    reason: str

@router.post("/tickets/{id}/override-priority")
async def override_priority(id: int, event: OverridePriorityEvent, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    ticket = await ApprovalService.override_priority(
        db=db,
        ticket_id=id,
        actor_id=current_user.id,
        actor_role=current_user.role,
        new_score=event.priority_score,
        reason=event.reason
    )
    await db.commit()
    return {"id": ticket.id, "priority_score": ticket.priority_score, "priority_label": ticket.priority_label}
