"""
ApprovalService — budget approvals and priority overrides.
Fully rewritten to use MongoDB (Beanie).
"""
from fastapi import HTTPException
from beanie import PydanticObjectId

from app.mongodb.models.ticket import TicketMongo
from app.enums import PriorityLabel
from app.core.rbac import ROLE_PERMISSIONS


class ApprovalService:

    @staticmethod
    async def approve_budget(
        ticket_id: str,
        actor_id: str,
        actor_role: str,
        amount: float,
    ) -> dict:
        permissions = ROLE_PERMISSIONS.get(actor_role)
        if not permissions:
            raise HTTPException(status_code=403, detail="Invalid role")

        max_budget = permissions.get("can_approve_budget_max")
        if max_budget is not None and amount > max_budget:
            raise HTTPException(
                status_code=403,
                detail=f"Amount exceeds authorization limit of {max_budget}"
            )

        ticket = await TicketMongo.get(PydanticObjectId(ticket_id))
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        # Write audit log
        from app.services.audit_service import write_audit
        await write_audit(
            action="BUDGET_APPROVED",
            ticket_id=ticket_id,
            actor_id=actor_id,
            actor_role=actor_role,
            new_value={"amount": amount},
        )
        return {
            "ticket_id": ticket_id,
            "amount_approved": amount,
            "approved_by": actor_id,
        }

    @staticmethod
    async def override_priority(
        ticket_id: str,
        actor_id: str,
        actor_role: str,
        new_score: float,
        reason: str,
    ) -> TicketMongo:
        permissions = ROLE_PERMISSIONS.get(actor_role)
        if not permissions or not permissions.get("can_override_priority"):
            raise HTTPException(
                status_code=403,
                detail="Not authorized to override priority"
            )

        ticket = await TicketMongo.get(PydanticObjectId(ticket_id))
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        old_score = ticket.priority_score
        new_score = min(100.0, max(0.0, float(new_score)))

        if new_score >= 80: ticket.priority_label = PriorityLabel.CRITICAL
        elif new_score >= 60: ticket.priority_label = PriorityLabel.HIGH
        elif new_score >= 35: ticket.priority_label = PriorityLabel.MEDIUM
        else: ticket.priority_label = PriorityLabel.LOW

        ticket.priority_score = new_score
        ticket.priority_source = "human_override"
        await ticket.save()

        from app.services.audit_service import write_audit
        await write_audit(
            action="PRIORITY_OVERRIDDEN",
            ticket_id=ticket_id,
            actor_id=actor_id,
            actor_role=actor_role,
            old_value={"score": old_score},
            new_value={"score": new_score, "reason": reason},
        )
        return ticket
