"""
MongoDB Document: CommissionerDigest

Weekly performance digest for commissioners.
Collection: commissioner_digests
"""
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from beanie import Document, Indexed
from pydantic import Field


class DigestContent(dict):
    """Flexible dict for digest sections."""
    pass


class CommissionerDigestMongo(Document):
    digest_id: Indexed(str, unique=True) = Field(default_factory=lambda: uuid.uuid4().hex[:8])  # type: ignore[valid-type]
    week_label: str  # e.g. "Week of 16 Jun 2025"
    week_start: datetime
    week_end: datetime
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    generated_by: str = "scheduler"  # "scheduler" | "manual"
    triggered_by_id: Optional[str] = None
    generation_status: str = "success"  # "success" | "generation_failed"

    raw_data: Dict[str, Any] = Field(default_factory=dict)

    digest: Dict[str, Any] = Field(default_factory=dict)
    # Keys: executive_summary, top_concern, ward_performance_narrative,
    # department_health_narrative, escalations_narrative,
    # intelligence_alerts_narrative, cctv_narrative,
    # recommended_priority_action, positive_highlight

    pdf_path: Optional[str] = None
    is_current_week: bool = True

    class Settings:
        name = "commissioner_digests"
        indexes = [
            "digest_id",
            "week_label",
            "week_start",
            "generated_at",
            "generated_by",
        ]

    class Config:
        populate_by_name = True
