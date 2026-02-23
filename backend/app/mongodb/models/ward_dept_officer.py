"""
MongoDB Document: WardDeptOfficer

Mirrors app/models/ward_dept_officer.py (SQLAlchemy) → Beanie ODM.

In SQLite this is a composite-PK join table (ward_id, dept_id).
In MongoDB we model it as a document with a compound unique index on
(ward_id, dept_id) plus an officer reference.
"""
from beanie import Document, Indexed
from pydantic import Field
from typing import Optional


class WardDeptOfficerMongo(Document):
    """
    Maps a ward + department pair to the responsible officer.
    Collection: ward_dept_officers
    """
    ward_id: int
    dept_id: str = Field(..., max_length=5)    # e.g. "PWD"
    officer_id: Optional[str] = None            # ObjectId string of UserMongo

    class Settings:
        name = "ward_dept_officers"
        indexes = [
            # Compound unique index to replicate the composite PK semantics
            [("ward_id", 1), ("dept_id", 1)],
        ]

    class Config:
        populate_by_name = True
