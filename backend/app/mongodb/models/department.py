"""
MongoDB Document: Department

Mirrors app/models/department.py (SQLAlchemy) → Beanie ODM.
dept_id (e.g. "PWD", "HLTH") is stored as the MongoDB _id for 
natural key semantics — exactly like the SQLite primary key.
"""
from beanie import Document, Indexed
from pydantic import Field
from typing import Optional


class DepartmentMongo(Document):
    """
    Government department that handles civic complaints.
    Collection: departments
    Uses dept_id (short string) as the natural primary key.
    """
    # dept_id is the natural PK (e.g. "PWD", "HLTH") — mapped to _id
    dept_id: Indexed(str, unique=True)  # type: ignore[valid-type]
    dept_name: str = Field(..., max_length=100)
    handles: Optional[str] = None          # Comma-separated list of issue types
    sla_days: int
    is_external: bool = False
    parent_body: Optional[str] = Field(None, max_length=100)
    escalation_role: Optional[str] = Field(None, max_length=50)

    class Settings:
        name = "departments"

    class Config:
        populate_by_name = True
