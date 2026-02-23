"""
MongoDB Document: Announcement

Mirrors app/models/announcement.py (SQLAlchemy) → Beanie ODM.
"""
from beanie import Document, Indexed
from pydantic import Field
from typing import Optional
from datetime import datetime


class AnnouncementMongo(Document):
    """
    Public announcements drafted and approved by officers.
    Collection: announcements
    """
    title: Optional[str] = Field(None, max_length=200)
    body: str

    # Officer IDs (ObjectId strings referencing UserMongo)
    drafted_by: Optional[str] = None
    approved_by: Optional[str] = None

    approved: bool = False

    # Related ticket (ObjectId string referencing TicketMongo)
    related_ticket_id: Optional[str] = None

    announcement_type: Optional[str] = Field(None, max_length=50)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    published_at: Optional[datetime] = None

    class Settings:
        name = "announcements"
        indexes = [
            "approved",
            "published_at",
        ]

    class Config:
        populate_by_name = True
