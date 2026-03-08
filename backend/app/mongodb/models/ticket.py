"""
MongoDB Document: Ticket

Civic complaint ticket — the core domain object.
Collection: tickets
"""
from beanie import Document, Indexed
from pydantic import Field
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.enums import TicketSource, TicketStatus, PriorityLabel


class GeoPoint(dict):
    """
    GeoJSON Point for MongoDB 2dsphere index.
    Usage: GeoPoint.from_coords(lat=12.97, lng=80.27)
    """
    @classmethod
    def from_coords(cls, lat: float, lng: float) -> "GeoPoint":
        return cls(type="Point", coordinates=[lng, lat])  # GeoJSON: [lng, lat]


class TicketMongo(Document):
    """
    Civic complaint ticket — the core domain object.
    Collection: tickets
    """
    ticket_code: Indexed(str, unique=True)          # type: ignore[valid-type]
    source: TicketSource = TicketSource.WEB_PORTAL
    source_url: Optional[str] = None
    description: str
    dept_id: Indexed(str)                            # type: ignore[valid-type]
    issue_category: Optional[str] = None             # AI-extracted category (e.g. "pothole")
    ward_id: Optional[Indexed(int)] = None           # type: ignore[valid-type]
    zone_id: Optional[int] = None

    # Location — GeoJSON for native geospatial queries
    location: Optional[Dict[str, Any]] = Field(
        None,
        description='GeoJSON Point e.g. {"type":"Point","coordinates":[80.27,12.97]}'
    )
    coordinates: Optional[str] = None
    location_text: Optional[str] = None

    photo_url: Optional[str] = None
    before_photo_url: Optional[str] = None
    after_photo_url: Optional[str] = None

    reporter_phone: Optional[str] = Field(None, max_length=15)
    reporter_name: Optional[str] = Field(None, max_length=100)
    reporter_user_id: Optional[str] = None          # ObjectId of UserMongo

    # DPDP Compliance
    consent_given: bool = False
    consent_timestamp: Optional[datetime] = None

    # AI metadata
    language_detected: Optional[str] = None
    ai_confidence: Optional[float] = None
    ai_routing_reason: Optional[str] = None
    ai_suggestions: Optional[List[str]] = None       # 3 actionable suggestions

    # Priority
    priority_score: float = 0.0
    priority_label: Optional[PriorityLabel] = None
    priority_source: str = "rules"                   # "rules" | "ml" | "hybrid" | "llm"

    # Lifecycle
    status: TicketStatus = TicketStatus.OPEN  # type: ignore[valid-type]
    report_count: int = 1
    requires_human_review: bool = False
    is_validated: bool = False

    # Cost & satisfaction
    estimated_cost: Optional[float] = None
    citizen_satisfaction: Optional[int] = None

    # SLA
    sla_deadline: Optional[datetime] = None

    # Supervisor-confirmed completion deadline (≤ sla_deadline)
    completion_deadline: Optional[datetime] = None
    completion_deadline_confirmed_by: Optional[str] = None  # officer_id who confirmed

    # Social signal
    social_media_mentions: int = 0

    # Assignment
    assigned_officer_id: Optional[str] = None       # ObjectId of UserMongo
    assigned_at: Optional[datetime] = None
    technician_id: Optional[str] = None              # ObjectId of UserMongo (field technician)

    # Seasonal alert info
    seasonal_alert: Optional[str] = None             # populated by MemoryAgent

    # Scheduling
    scheduled_date: Optional[datetime] = None        # Finalized work date set by officer
    ai_suggested_date: Optional[datetime] = None     # AI-calculated suggested work date

    # Transparency timeline
    status_timeline: List[Dict[str, Any]] = Field(
        default_factory=list,
        description='List of {status, timestamp, actor_role, note} dicts'
    )

    # Officer remarks
    remarks: List[Dict[str, Any]] = Field(
        default_factory=list,
        description='List of {text, timestamp, officer_id} dicts'
    )

    # Immutability record
    blockchain_hash: Optional[str] = Field(None, max_length=66)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None

    # Work completion verification (AI-powered before/after comparison)
    work_verified: Optional[bool] = None          # True = AI confirmed work done
    work_verification_confidence: Optional[float] = None  # 0.0 – 1.0
    work_verification_method: Optional[str] = None  # "gemini_vision" | "ssim_local" | "pixel_fallback"
    work_verification_explanation: Optional[str] = None  # Human-readable verdict
    work_verified_at: Optional[datetime] = None

    class Settings:
        name = "tickets"
        indexes = [
            "status",
            "priority_label",
            "dept_id",
            "ward_id",
            "created_at",
            [("location", "2dsphere")],
        ]

    class Config:
        populate_by_name = True
