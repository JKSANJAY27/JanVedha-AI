"""
MongoDB Document: Notification

Stores citizen notification history for proactive communication.
Collection: notifications
"""
from beanie import Document, Indexed
from pydantic import Field
from typing import Optional
from datetime import datetime


class NotificationMongo(Document):
    ticket_id: Indexed(str)                           # type: ignore[valid-type]
    citizen_id: Optional[str] = None                  # ObjectId of UserMongo
    telegram_chat_id: Optional[str] = None
    event_type: str                                    # "ticket_acknowledged" | "technician_assigned" | "work_started" | "issue_resolved"
    message_sent: str                                 # Full message text
    language: str = "English"
    ward_id: Optional[int] = None
    delivered: bool = False
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "notifications"
        indexes = [
            "ticket_id",
            "citizen_id",
            "ward_id",
            "timestamp",
        ]

    class Config:
        populate_by_name = True
