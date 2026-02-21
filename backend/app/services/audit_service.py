from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert
from datetime import datetime

from app.models.audit_log import AuditLog

async def write_audit(
    db: AsyncSession,
    action: str,
    ticket_id: Optional[int] = None,
    actor_id: Optional[int] = None,
    actor_role: Optional[str] = None,
    old_value: Optional[Dict[str, Any]] = None,
    new_value: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None
) -> None:
    """
    Write-only. No update. No delete. No exceptions.
    If this fails, the entire parent transaction should fail.
    Log every: TICKET_CREATED, STATUS_CHANGED, BUDGET_APPROVED,
    PRIORITY_OVERRIDDEN, SLA_BREACHED, AUTO_ESCALATED, CITIZEN_CONFIRMED_FIXED,
    CITIZEN_DISPUTED, ANNOUNCEMENT_DRAFTED, ANNOUNCEMENT_APPROVED
    """
    audit_entry = AuditLog(
        ticket_id=ticket_id,
        action=action,
        actor_id=actor_id,
        actor_role=actor_role,
        old_value=old_value,
        new_value=new_value,
        ip_address=ip_address,
        created_at=datetime.utcnow()
    )
    db.add(audit_entry)
    # Note: caller is responsible for committing the session to ensure atomicity
