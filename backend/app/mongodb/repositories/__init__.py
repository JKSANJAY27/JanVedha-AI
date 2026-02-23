"""Re-export repositories for convenient import."""
from .ticket_repo import TicketRepo
from .user_repo import UserRepo
from .department_repo import DepartmentRepo
from .announcement_repo import AnnouncementRepo
from .audit_repo import AuditRepo

__all__ = [
    "TicketRepo",
    "UserRepo",
    "DepartmentRepo",
    "AnnouncementRepo",
    "AuditRepo",
]
