"""
MongoDB Document: AuditAnchorMongo
Tracks batches of audit logs that have been anchored to the blockchain.
"""
from beanie import Document, Indexed
from pydantic import Field
from typing import Optional
from datetime import datetime

class AuditAnchorMongo(Document):
    """
    Tracks a batched blockchain anchor event.
    Collection: audit_anchors
    """
    batch_id: Indexed(str, unique=True)    # type: ignore[valid-type]
    data_hash: str                         # SHA-256 of the batched audit logs
    
    # Blockchain Details
    tx_hash: Optional[str] = None
    block_number: Optional[int] = None
    
    # Metadata
    anchor_count: int = 0                  # Number of audit_logs included in this batch
    status: str = "pending"                # pending | confirmed | failed
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    anchored_at: Optional[datetime] = None

    class Settings:
        name = "audit_anchors"
        indexes = [
            "batch_id",
            "created_at",
            "status",
        ]
