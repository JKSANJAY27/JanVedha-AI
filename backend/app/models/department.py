from sqlalchemy import Column, Integer, String, Text, Boolean
from .base import Base

class Department(Base):
    __tablename__ = "departments"
    dept_id = Column(String(5), primary_key=True)
    dept_name = Column(String(100), nullable=False)
    handles = Column(Text)
    sla_days = Column(Integer, nullable=False)
    is_external = Column(Boolean, default=False)
    parent_body = Column(String(100))
    escalation_role = Column(String(50))
