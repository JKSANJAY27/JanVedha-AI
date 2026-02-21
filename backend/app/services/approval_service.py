from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException

from app.models.ticket import Ticket
from app.core.rbac import ROLE_PERMISSIONS, UserRole
from app.services.audit_service import write_audit

class ApprovalService:
    @staticmethod
    async def approve_budget(db: AsyncSession, ticket_id: int, actor_id: int, actor_role: str, amount: float) -> dict:
        permissions = ROLE_PERMISSIONS.get(actor_role)
        if not permissions:
            raise HTTPException(status_code=403, detail="Invalid role")
            
        max_budget = permissions.get("can_approve_budget_max")
        if max_budget is not None and amount > max_budget:
            raise HTTPException(status_code=403, detail=f"Amount exceeds authorization limit of {max_budget}")
            
        result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
        ticket = result.scalar_one_or_none()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")
            
        # In a real system, there would be a BudgetApproval model/table
        # For Phase 1MVP, we just write an audit log
        await write_audit(
            db=db,
            action="BUDGET_APPROVED",
            ticket_id=ticket.id,
            actor_id=actor_id,
            actor_role=actor_role,
            new_value={"amount": amount}
        )
        return {"ticket_id": ticket.id, "amount_approved": amount, "approved_by": actor_id}

    @staticmethod
    async def override_priority(db: AsyncSession, ticket_id: int, actor_id: int, actor_role: str, new_score: float, reason: str) -> Ticket:
        permissions = ROLE_PERMISSIONS.get(actor_role)
        if not permissions or not permissions.get("can_override_priority"):
            raise HTTPException(status_code=403, detail="Not authorized to override priority")
            
        result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
        ticket = result.scalar_one_or_none()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")
            
        old_score = ticket.priority_score
        ticket.priority_score = min(100.0, max(0.0, float(new_score)))
        
        if ticket.priority_score >= 80: ticket.priority_label = "CRITICAL"
        elif ticket.priority_score >= 60: ticket.priority_label = "HIGH"
        elif ticket.priority_score >= 35: ticket.priority_label = "MEDIUM"
        else: ticket.priority_label = "LOW"
        
        await write_audit(
            db=db,
            action="PRIORITY_OVERRIDDEN",
            ticket_id=ticket.id,
            actor_id=actor_id,
            actor_role=actor_role,
            old_value={"score": old_score},
            new_value={"score": ticket.priority_score, "reason": reason}
        )
        return ticket
