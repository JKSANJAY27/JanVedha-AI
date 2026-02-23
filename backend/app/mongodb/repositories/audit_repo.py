"""
Repository: AuditRepo

IMMUTABILITY CONTRACT — same as the SQLite version:
  - NO update method.
  - NO delete method.
  - write() is the only public entry point.
  - Once written, an audit entry is permanent.
"""
from typing import Optional, Dict, Any
from datetime import datetime

from app.mongodb.models.audit_log import AuditLogMongo


class AuditRepo:
    """Write-only repository for the audit_logs collection."""

    @staticmethod
    async def write(
        action: str,
        ticket_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        actor_role: Optional[str] = None,
        old_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLogMongo:
        """
        Append a new immutable audit entry.

        Supported actions (mirrors the SQLite schema commentary):
          TICKET_CREATED, STATUS_CHANGED, BUDGET_APPROVED,
          PRIORITY_OVERRIDDEN, SLA_BREACHED, AUTO_ESCALATED,
          CITIZEN_CONFIRMED_FIXED, CITIZEN_DISPUTED,
          ANNOUNCEMENT_DRAFTED, ANNOUNCEMENT_APPROVED,
          TICKET_REROUTED, TICKET_ESCALATED
        """
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
        return entry

    # ──────────────────────────────────────────────────────────────────────────
    # READ helpers (allowed — reading audit log is fine; only mutation is locked)
    # ──────────────────────────────────────────────────────────────────────────
    @staticmethod
    async def get_for_ticket(ticket_id: str, limit: int = 100):
        """Return the audit trail for a specific ticket, oldest-first."""
        return (
            await AuditLogMongo.find(AuditLogMongo.ticket_id == ticket_id)
            .sort(+AuditLogMongo.created_at)
            .limit(limit)
            .to_list()
        )
