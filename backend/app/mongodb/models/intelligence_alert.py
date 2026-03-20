"""
MongoDB Document: IntelligenceAlert

Stores AI-detected systemic patterns for the commissioner dashboard.
Collection: intelligence_alerts
"""
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from beanie import Document, Indexed
from pydantic import Field


class IntelligenceAlertMongo(Document):
    alert_id: Indexed(str, unique=True) = Field(default_factory=lambda: uuid.uuid4().hex[:10])  # type: ignore[valid-type]
    pattern_type: str  # "geographic_cluster" | "recurrence_spike" | "department_collapse" | "sentiment_drop"
    severity: str = "medium"  # "high" | "medium" | "low"
    fingerprint: Indexed(str)  # type: ignore[valid-type]  # deduplication key

    summary: str = ""
    detail: str = ""
    recommended_action: str = ""

    evidence: Dict[str, Any] = Field(default_factory=dict)

    affected_ward_ids: List[str] = Field(default_factory=list)
    affected_dept_id: Optional[str] = None
    affected_location: Optional[Dict[str, float]] = None  # {"lat": float, "lng": float}
    affected_area_label: Optional[str] = None

    status: str = "new"  # "new" | "acknowledged" | "actioned" | "resolved"
    acknowledged_by_id: Optional[str] = None
    acknowledged_by_name: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    commissioner_note: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None

    class Settings:
        name = "intelligence_alerts"
        indexes = [
            "alert_id",
            "fingerprint",
            "pattern_type",
            "severity",
            "status",
            "created_at",
            "expires_at",
        ]

    class Config:
        populate_by_name = True
