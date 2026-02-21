from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, INET
from .base import Base

class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"))
    action = Column(String(100), nullable=False)
    old_value = Column(JSONB)
    new_value = Column(JSONB)
    actor_id = Column(Integer, ForeignKey("users.id"))
    actor_role = Column(String(50))
    ip_address = Column(INET)
    created_at = Column(DateTime, server_default="NOW()")
    # NO update. NO delete. Ever.
