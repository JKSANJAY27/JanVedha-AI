"""Re-export all Beanie Document models for convenient import."""
from .user import UserMongo
from .ticket import TicketMongo
from .department import DepartmentMongo
from .announcement import AnnouncementMongo
from .audit_log import AuditLogMongo
from .ward_dept_officer import WardDeptOfficerMongo
from .ward_prediction import WardPredictionMongo
from .issue_memory import IssueMemoryMongo
from .priority_model import PriorityModelMongo
from .scheduled_event import ScheduledEventMongo
from .social_post import SocialPostMongo
from .ward_benchmark import WardBenchmarkMongo
# Pillar 3: Public Trust
from .notification import NotificationMongo
from .misinformation_flag import MisinformationFlagMongo
from .trust_score import TrustScoreMongo
from .ward_config import WardConfigMongo
# Feature: Infrastructure Opportunity & Proposals
from .proposal import ProposalMongo
# Feature: Constituent Casework
from .casework import CaseworkMongo
# Feature: Constituent Communication Center
from .ward_communication import WardCommunicationMongo
# Feature: Media & RTI Response Assistant
from .media_rti_response import MediaRtiResponseMongo
# Feature: CCTV Civic Issue Detection
from .camera import Camera
from .cctv_alert import CCTVAlert
# Feature: Ward Intelligence Cache (Gemini API result caching)
from .ward_intelligence_cache import WardIntelligenceCache
# Feature: Commissioner Dashboard features
from .dept_config import DeptConfigMongo
from .intelligence_alert import IntelligenceAlertMongo
from .escalation import EscalationMongo
from .commissioner_digest import CommissionerDigestMongo

__all__ = [
    "UserMongo",
    "TicketMongo",
    "DepartmentMongo",
    "AnnouncementMongo",
    "AuditLogMongo",
    "WardDeptOfficerMongo",
    "WardPredictionMongo",
    "IssueMemoryMongo",
    "PriorityModelMongo",
    "ScheduledEventMongo",
    "SocialPostMongo",
    "WardBenchmarkMongo",
    # Pillar 3
    "NotificationMongo",
    "MisinformationFlagMongo",
    "TrustScoreMongo",
    "WardConfigMongo",
    "ProposalMongo",
    "CaseworkMongo",
    "WardCommunicationMongo",
    "MediaRtiResponseMongo",
    "Camera",
    "CCTVAlert",
    "WardIntelligenceCache",
    # Commissioner features
    "DeptConfigMongo",
    "IntelligenceAlertMongo",
    "EscalationMongo",
    "CommissionerDigestMongo",
]
