from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from datetime import datetime
from .base import Base

class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"))
    action = Column(String(100), nullable=False)
    old_value = Column(Text)
    new_value = Column(Text)
    actor_id = Column(Integer, ForeignKey("users.id"))
    actor_role = Column(String(50))
    ip_address = Column(String(45))
    created_at = Column(DateTime, default=datetime.utcnow)
    # NO update. NO delete. Ever.
