"""
Central enums for the JanVedha AI domain.
Previously spread across app/models/*.py (SQLAlchemy). Now a single source of truth.
"""
import enum


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


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    COMMISSIONER = "COMMISSIONER"
    ZONAL_OFFICER = "ZONAL_OFFICER"
    WARD_OFFICER = "WARD_OFFICER"
    DEPT_HEAD = "DEPT_HEAD"
    COUNCILLOR = "COUNCILLOR"
    TECHNICIAN = "TECHNICIAN"
    PUBLIC_USER = "PUBLIC_USER"
