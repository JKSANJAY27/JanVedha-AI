"""
MongoDB Document: Escalation

Councillor-to-commissioner escalation tracker.
Collection: escalations
"""
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from beanie import Document, Indexed
from pydantic import BaseModel, Field


class CommissionerResponse(BaseModel):
    action_type: Optional[str] = None  # "direct_resolution" | "dept_assignment" | "response_sent" | "escalated_further"
    response_text: Optional[str] = None
    assigned_dept_id: Optional[str] = None
    assigned_dept_name: Optional[str] = None
    responding_commissioner_id: Optional[str] = None
    responding_commissioner_name: Optional[str] = None
    responded_at: Optional[datetime] = None


class TimelineEvent(BaseModel):
    event: str
    actor: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    note: Optional[str] = None


class EscalationMongo(Document):
    escalation_id: Indexed(str, unique=True) = Field(default_factory=lambda: uuid.uuid4().hex[:10])  # type: ignore[valid-type]
    ward_id: str
    ward_name: str

    from_councillor_id: str
    from_councillor_name: str

    escalation_type: str = "constituent_complaint"
    # "constituent_complaint" | "infrastructure_failure" | "contractor_dispute"
    # | "inter_department" | "scheme_issue" | "other"

    subject: str
    description: str
    urgency: str = "normal"  # "high" | "medium" | "normal"

    linked_casework_id: Optional[str] = None
    linked_ticket_id: Optional[str] = None

    status: str = "received"
    # "received" | "acknowledged" | "in_progress" | "responded" | "closed"

    sla_hours: int = 240  # 48 for high, 120 for medium, 240 for normal
    sla_deadline: Optional[datetime] = None
    sla_breached: bool = False

    commissioner_response: CommissionerResponse = Field(default_factory=CommissionerResponse)
    timeline: List[TimelineEvent] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "escalations"
        indexes = [
            "escalation_id",
            "ward_id",
            "from_councillor_id",
            "status",
            "urgency",
            "sla_deadline",
            "created_at",
        ]

    class Config:
        populate_by_name = True
