"""
MongoDB Document: User

Mirrors app/models/user.py (SQLAlchemy) → Beanie ODM.
Enums are re-used from the original model to avoid duplication.
"""
from beanie import Document, Indexed
from pydantic import Field
from typing import Optional
from datetime import datetime

# Re-use enums from the existing SQLAlchemy model — no duplication
from app.models.user import UserRole


class UserMongo(Document):
    """
    Represents a civic system user (officer, commissioner, admin, etc.)
    Collection: users
    """
    name: str = Field(..., max_length=100)
    phone: Optional[Indexed(str, unique=True)] = None   # type: ignore[valid-type]
    email: Optional[Indexed(str, unique=True)] = None   # type: ignore[valid-type]
    password_hash: Optional[str] = None
    role: UserRole
    ward_id: Optional[int] = None
    zone_id: Optional[int] = None
    # Reference to DepartmentMongo stored as dept_id string key (e.g. "PWD")
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
        # Allow ORM population (useful when migrating from SQLAlchemy objects)
        populate_by_name = True
