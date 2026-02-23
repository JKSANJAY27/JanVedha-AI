"""Re-export all Beanie Document models for convenient import."""
from .user import UserMongo
from .ticket import TicketMongo
from .department import DepartmentMongo
from .announcement import AnnouncementMongo
from .audit_log import AuditLogMongo
from .ward_dept_officer import WardDeptOfficerMongo
from .ward_prediction import WardPredictionMongo

__all__ = [
    "UserMongo",
    "TicketMongo",
    "DepartmentMongo",
    "AnnouncementMongo",
    "AuditLogMongo",
    "WardDeptOfficerMongo",
    "WardPredictionMongo",
]
