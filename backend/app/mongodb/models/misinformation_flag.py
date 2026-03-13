"""
MongoDB Document: MisinformationFlag

Stores flagged social media posts with AI-drafted responses.
Collection: misinformation_flags
"""
from beanie import Document, Indexed
from pydantic import Field
from typing import Optional, List
from datetime import datetime


class MisinformationFlagMongo(Document):
    post_id: str                                      # Original social post ID
    post_text: str                                    # Full text of the post
    platform: str = "twitter"
    ward_id: Optional[int] = None
    claim: str                                        # The false/misleading claim
    risk_level: str                                   # "high" | "medium" | "low"
    suggested_counter_data_needed: List[str] = Field(default_factory=list)
    counter_data: Optional[dict] = None              # Fetched ticket stats for context
    draft_response: Optional[str] = None             # Gemini-drafted counter-response
    status: str = "pending"                          # "pending" | "approved" | "dismissed"
    approved_response: Optional[str] = None
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    actioned_at: Optional[datetime] = None

    class Settings:
        name = "misinformation_flags"
        indexes = [
            "ward_id",
            "risk_level",
            "status",
            "detected_at",
        ]

    class Config:
        populate_by_name = True
