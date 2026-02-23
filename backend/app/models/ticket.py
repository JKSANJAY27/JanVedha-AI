from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey, func
from datetime import datetime
from .base import Base
import enum

try:
    from geoalchemy2 import Geography
    HAS_GEOALCHEMY = True
except ImportError:
    HAS_GEOALCHEMY = False

class TicketSource(str, enum.Enum):
    VOICE_CALL = "VOICE_CALL"
    WEB_PORTAL = "WEB_PORTAL"
    WHATSAPP = "WHATSAPP"
    SOCIAL_MEDIA = "SOCIAL_MEDIA"
    NEWS = "NEWS"
    CPGRAMS = "CPGRAMS"

class TicketStatus(str, enum.Enum):
    OPEN = "OPEN"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    CLOSED = "CLOSED"
    CLOSED_UNVERIFIED = "CLOSED_UNVERIFIED"
    REOPENED = "REOPENED"
    REJECTED = "REJECTED"

class PriorityLabel(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class Ticket(Base):
    __tablename__ = "tickets"
    id = Column(Integer, primary_key=True)
    ticket_code = Column(String(20), unique=True, nullable=False)
    source = Column(String(20), nullable=False)
    source_url = Column(Text)
    description = Column(Text, nullable=False)
    dept_id = Column(String(5), ForeignKey("departments.dept_id"), nullable=False)
    ward_id = Column(Integer)
    zone_id = Column(Integer)
    coordinates = Column(String(100))  # Store as string, e.g., "POINT(lat lng)"
    photo_url = Column(Text)
    before_photo_url = Column(Text)
    after_photo_url = Column(Text)
    reporter_phone = Column(String(15))
    reporter_name = Column(String(100))
    consent_given = Column(Boolean, default=False)
    consent_timestamp = Column(DateTime)
    language_detected = Column(String(20))
    ai_confidence = Column(Float)
    priority_score = Column(Float, default=0.0)
    priority_label = Column(String(10))
    status = Column(String(30), default="OPEN")
    report_count = Column(Integer, default=1)
    requires_human_review = Column(Boolean, default=False)
    estimated_cost = Column(Float)
    citizen_satisfaction = Column(Integer)
    sla_deadline = Column(DateTime)
    social_media_mentions = Column(Integer, default=0)
    assigned_officer_id = Column(Integer, ForeignKey("users.id"))
    blockchain_hash = Column(String(66))
    created_at = Column(DateTime, default=datetime.utcnow)
    assigned_at = Column(DateTime)
    resolved_at = Column(DateTime)
