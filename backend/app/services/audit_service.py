"""
AuditService — immutable audit log using MongoDB (AuditLogMongo).
Write-only. Never updates or deletes audit entries.
"""
from typing import Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


async def write_audit(
    action: str,
    ticket_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    actor_role: Optional[str] = None,
    old_value: Optional[Dict[str, Any]] = None,
    new_value: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> None:
    """
    Write an audit log entry to MongoDB. Fire-and-forget safe.
    Never raises — failures are logged but do not abort parent operations.
    """
    try:
        from app.mongodb.models.audit_log import AuditLogMongo
        entry = AuditLogMongo(
            ticket_id=ticket_id,
            action=action,
            actor_id=actor_id,
            actor_role=actor_role,
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address,
            created_at=datetime.utcnow(),
        )
        await entry.insert()
    except Exception as exc:
        logger.error("Audit write failed (non-critical): action=%s error=%s", action, exc)
