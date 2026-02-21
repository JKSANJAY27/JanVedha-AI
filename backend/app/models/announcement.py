from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from .base import Base

class Announcement(Base):
    __tablename__ = "announcements"
    id = Column(Integer, primary_key=True)
    title = Column(String(200))
    body = Column(Text, nullable=False)
    drafted_by = Column(Integer, ForeignKey("users.id"))
    approved_by = Column(Integer, ForeignKey("users.id"))
    approved = Column(Boolean, default=False)
    related_ticket_id = Column(Integer, ForeignKey("tickets.id"))
    announcement_type = Column(String(50))
    created_at = Column(DateTime, server_default="NOW()")
    published_at = Column(DateTime)
