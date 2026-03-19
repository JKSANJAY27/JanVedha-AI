from typing import Optional, Literal
from datetime import datetime
from pydantic import Field, BaseModel
from beanie import Document
from pymongo import IndexModel, ASCENDING, DESCENDING

class SourceMedia(BaseModel):
    type: Literal["image", "video_clip"]
    original_path: str
    analysis_frame_path: str
    uploaded_at: datetime
    uploaded_by: str

class AIAnalysis(BaseModel):
    issue_detected: bool
    confidence_score: float
    issue_category: Optional[str] = None
    severity: Optional[str] = None
    issue_summary: Optional[str] = None
    detailed_description: Optional[str] = None
    suggested_ticket_title: Optional[str] = None
    suggested_priority: Optional[str] = None
    what_is_visible: str
    analysis_notes: Optional[str] = None

class Verification(BaseModel):
    verified_by_id: Optional[str] = None
    verified_by_name: Optional[str] = None
    verified_by_role: Optional[str] = None
    verified_at: Optional[datetime] = None
    verification_action: Optional[str] = None
    verifier_note: Optional[str] = None
    priority_override: Optional[str] = None

class CCTVAlert(Document):
    alert_id: str
    ward_id: str
    camera_id: str
    camera_location_description: str
    camera_lat: float
    camera_lng: float
    area_label: str

    source_media: SourceMedia
    ai_analysis: AIAnalysis
    status: str = "pending_verification"  # pending_verification | ticket_raised | dismissed | flagged_for_discussion
    verification: Optional[Verification] = None
    raised_ticket_id: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "cctv_alerts"
        use_state_management = True
        indexes = [
            IndexModel([("alert_id", ASCENDING)], unique=True),
            IndexModel([("ward_id", ASCENDING), ("status", ASCENDING)]),
            IndexModel([("created_at", DESCENDING)]),
        ]
