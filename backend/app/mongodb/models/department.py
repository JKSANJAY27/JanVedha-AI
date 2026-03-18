"""
MongoDB Document: Department

Mirrors app/models/department.py (SQLAlchemy) → Beanie ODM.
dept_id (e.g. "D01", "D02") is used as a short identifier.
Each dept can be ward-scoped (ward_id not None) or global (ward_id None).
Ward-scoped departments take precedence during SLA lookups.
"""
from beanie import Document, Indexed
from pydantic import Field
from typing import Optional


class DepartmentMongo(Document):
    """
    Government department that handles civic complaints.
    Collection: departments
    dept_id: short string like "D01"…"D14"
    ward_id: if set, this dept record is specific to that ward.
             if None, it's a global fallback.
    """
    dept_id: str = Field(..., max_length=10)          # e.g. "D01"
    ward_id: Optional[int] = None                      # None = global
    dept_name: str = Field(..., max_length=100)
    handles: Optional[str] = None          # Comma-separated list of issue types
    sla_days: int = 7
    is_external: bool = False
    parent_body: Optional[str] = Field(None, max_length=100)
    escalation_role: Optional[str] = Field(None, max_length=50)

    class Settings:
        name = "departments"
        indexes = [
            "ward_id",
            [("dept_id", 1), ("ward_id", 1)],  # composite index for fast per-ward lookup
        ]

    class Config:
        populate_by_name = True
