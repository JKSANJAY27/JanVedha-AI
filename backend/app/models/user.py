from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from datetime import datetime
from .base import Base
import enum

class UserRole(str, enum.Enum):
    WARD_OFFICER = "WARD_OFFICER"
    ZONAL_OFFICER = "ZONAL_OFFICER"
    DEPT_HEAD = "DEPT_HEAD"
    COMMISSIONER = "COMMISSIONER"
    COUNCILLOR = "COUNCILLOR"
    SUPER_ADMIN = "SUPER_ADMIN"
    PUBLIC_USER = "PUBLIC_USER"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    phone = Column(String(15), unique=True)
    email = Column(String(100), unique=True)
    password_hash = Column(String(255))
    role = Column(String(30), nullable=False)
    ward_id = Column(Integer)
    zone_id = Column(Integer)
    dept_id = Column(String(5), ForeignKey("departments.dept_id"))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
