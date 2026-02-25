"""
MongoDB Document: User

Represents a civic system user (officer, commissioner, admin, public user, etc.)
Collection: users
"""
from beanie import Document, Indexed
from pydantic import Field
from typing import Optional
from datetime import datetime

from app.enums import UserRole


class UserMongo(Document):
    name: str = Field(..., max_length=100)
    phone: Optional[Indexed(str, unique=True)] = None   # type: ignore[valid-type]
    email: Optional[Indexed(str, unique=True)] = None   # type: ignore[valid-type]
    password_hash: Optional[str] = None
    role: UserRole = UserRole.PUBLIC_USER
    ward_id: Optional[int] = None
    zone_id: Optional[int] = None
    dept_id: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "users"
        indexes = [
            "role",
            "ward_id",
        ]

    class Config:
        populate_by_name = True
