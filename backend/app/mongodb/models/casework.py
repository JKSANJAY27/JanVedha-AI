"""
MongoDB Document: Casework

Constituent casework log — tracks complaints received by councillors outside
the formal ticket system, and ties them to tickets.
Collection: casework
"""
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from beanie import Document, Indexed
from pydantic import BaseModel, Field

from app.enums import TicketStatus

class ConstituentData(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = Field(None, description="Stored as-is, mask on display")
    address: Optional[str] = None
    preferred_language: Literal["english", "tamil", "both"] = "both"

class ComplaintData(BaseModel):
    description: str = Field(..., description="Raw description as logged")
    category: Optional[str] = Field(None, description="issue category")
    location_description: Optional[str] = None
    urgency: Literal["low", "medium", "high"] = "medium"
    how_received: Literal["walk_in", "phone_call", "whatsapp", "other"] = "other"

class VoiceNoteData(BaseModel):
    file_path: Optional[str] = Field(None, description="Path to uploaded audio")
    transcript: Optional[str] = Field(None, description="Gemini transcription")
    extracted_data: Optional[Dict[str, Any]] = Field(None, description="Structured extraction")

class FollowUpData(BaseModel):
    follow_up_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    language: Literal["english", "tamil", "both"] = "both"
    english_text: Optional[str] = None
    tamil_text: Optional[str] = None
    sent: bool = False
    sent_at: Optional[datetime] = None
    sent_via: Optional[Literal["whatsapp_manual", "telegram", "other"]] = None


class CaseworkMongo(Document):
    casework_id: Indexed(str, unique=True) = Field(default_factory=lambda: uuid.uuid4().hex[:10])
    ward_id: Indexed(int)
    councillor_id: Indexed(str)
    councillor_name: Optional[str] = None
    
    constituent: ConstituentData = Field(default_factory=ConstituentData)
    complaint: ComplaintData
    voice_note: VoiceNoteData = Field(default_factory=VoiceNoteData)
    
    linked_ticket_id: Optional[str] = None
    ticket_created: bool = False
    
    follow_ups: List[FollowUpData] = Field(default_factory=list)
    
    status: Literal["logged", "ticket_linked", "ticket_created", "follow_up_sent", "resolved", "escalated"] = "logged"
    
    escalation_flag: bool = False
    escalation_reason: Optional[str] = None
    
    notes: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "casework"
        indexes = [
            "ward_id",
            "councillor_id",
            "constituent.phone",
            "complaint.category",
            "status",
            "created_at",
        ]

    class Config:
        populate_by_name = True
