"""
MongoDB Document: Ticket

Mirrors app/models/ticket.py (SQLAlchemy) → Beanie ODM.
Enums are re-used from the original model to avoid duplication.

MongoDB-specific design choices:
  - coordinates stored as GeoJSON Point (enables native $near / $geoWithin queries)
  - audit_trail embedded as a lightweight summary array (full audit in AuditLogMongo)
"""
from beanie import Document, Indexed
from pydantic import Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# Re-use enums from the existing SQLAlchemy model — no duplication
from app.models.ticket import TicketSource, TicketStatus, PriorityLabel


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
    source: TicketSource
    source_url: Optional[str] = None
    description: str
    dept_id: Indexed(str)                            # type: ignore[valid-type]
    ward_id: Optional[Indexed(int)] = None           # type: ignore[valid-type]
    zone_id: Optional[int] = None

    # Location — GeoJSON for native geospatial queries
    # Format: {"type": "Point", "coordinates": [lng, lat]}
    location: Optional[Dict[str, Any]] = Field(
        None,
        description='GeoJSON Point e.g. {"type":"Point","coordinates":[80.27,12.97]}'
    )
    # Raw string fallback (kept for parity with SQLite schema)
    coordinates: Optional[str] = None

    photo_url: Optional[str] = None
    before_photo_url: Optional[str] = None
    after_photo_url: Optional[str] = None

    reporter_phone: Optional[str] = Field(None, max_length=15)
    reporter_name: Optional[str] = Field(None, max_length=100)

    # DPDP Compliance
    consent_given: bool = False
    consent_timestamp: Optional[datetime] = None

    # AI metadata
    language_detected: Optional[str] = None
    ai_confidence: Optional[float] = None

    # Priority
    priority_score: float = 0.0
    priority_label: Optional[PriorityLabel] = None

    # Lifecycle
    status: Indexed(TicketStatus) = TicketStatus.OPEN  # type: ignore[valid-type]
    report_count: int = 1
    requires_human_review: bool = False

    # Cost & satisfaction
    estimated_cost: Optional[float] = None
    citizen_satisfaction: Optional[int] = None

    # SLA
    sla_deadline: Optional[datetime] = None

    # Social signal
    social_media_mentions: int = 0

    # Assignment
    assigned_officer_id: Optional[str] = None   # ObjectId of UserMongo
    assigned_at: Optional[datetime] = None

    # Immutability record
    blockchain_hash: Optional[str] = Field(None, max_length=66)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None

    class Settings:
        name = "tickets"
        indexes = [
            "status",
            "priority_label",
            "dept_id",
            "ward_id",
            "created_at",
            [("location", "2dsphere")],   # enables geospatial queries
        ]

    class Config:
        populate_by_name = True
