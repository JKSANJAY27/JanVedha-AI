"""
MongoDB Document: AuditLog

Mirrors app/models/audit_log.py (SQLAlchemy) → Beanie ODM.

IMMUTABILITY RULE (same as the SQLite version):
  - No update. No delete. Ever.
  - The repository layer exposes write() only.
  - Any audit doc written is permanent.

Stores old_value / new_value as native BSON dicts (richer than TEXT in SQLite).
"""
from beanie import Document, Indexed
from pydantic import Field
from typing import Optional, Any, Dict
from datetime import datetime


class AuditLogMongo(Document):
    """
    Append-only immutable audit trail.
    Collection: audit_logs

    DO NOT add update or delete operations to this collection.
    """
    ticket_id: Optional[Indexed(str)] = None   # ObjectId string of TicketMongo  # type: ignore[valid-type]
    action: Indexed(str)                        # e.g. "TICKET_CREATED"           # type: ignore[valid-type]
    old_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None
    actor_id: Optional[str] = None             # ObjectId string of UserMongo
    actor_role: Optional[str] = Field(None, max_length=50)
    ip_address: Optional[str] = Field(None, max_length=45)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "audit_logs"
        indexes = [
            "ticket_id",
            "action",
            "created_at",
        ]

    class Config:
        populate_by_name = True
