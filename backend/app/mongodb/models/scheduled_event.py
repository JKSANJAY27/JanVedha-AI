"""
MongoDB Document: ScheduledEvent

Calendar entry for a department's work schedule.
Collection: scheduled_events
"""
from beanie import Document, Indexed
from pydantic import Field
from typing import Optional
from datetime import datetime


class ScheduledEventMongo(Document):
    """
    A single calendar entry that links a ticket to a scheduled work date.
    Collection: scheduled_events
    """
    dept_id: Indexed(str)                            # type: ignore[valid-type]
    ward_id: Optional[Indexed(int)] = None           # type: ignore[valid-type]
    ticket_id: Indexed(str)                          # type: ignore[valid-type]  # ObjectId of TicketMongo
    ticket_code: Optional[str] = None
    scheduled_date: datetime
    time_slot: Optional[str] = None                  # e.g. "09:00-11:00"
    officer_id: Optional[str] = None                 # Who scheduled it
    notes: Optional[str] = None
    is_ai_suggested: bool = False                    # True if suggested by AI
    event_type: str = "schedule"                     # "schedule" | "deadline"
    priority_label: Optional[str] = None             # Mirror from ticket for quick display
    issue_category: Optional[str] = None             # Mirror from ticket
    ticket_description: Optional[str] = None         # Short description for reminders
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "scheduled_events"
        indexes = [
            "dept_id",
            "ward_id",
            "ticket_id",
            "scheduled_date",
        ]

    class Config:
        populate_by_name = True
