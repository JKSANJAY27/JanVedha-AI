"""
MongoDB Document: IssueMemory

Stores recurring/seasonal issue patterns per ward per month.
Used by the MemoryAgent to generate proactive alerts when similar patterns emerge.
"""
from beanie import Document, Indexed
from pydantic import Field
from typing import Optional, List
from datetime import datetime


class IssueMemoryMongo(Document):
    """
    Tracks recurring/seasonal civic issue patterns.
    Collection: issue_memories

    Design: One document per (ward_id, issue_category, month, year) combination.
    The memory_agent upserts this document whenever a matching critical/high issue is resolved.
    """
    ward_id: Indexed(int)                               # type: ignore[valid-type]
    issue_category: Indexed(str)                        # type: ignore[valid-type]
    dept_id: str
    month: int                                          # 1-12
    year: int
    occurrence_count: int = 1
    avg_severity_score: float = 0.0
    avg_resolution_days: Optional[float] = None
    keywords: List[str] = Field(default_factory=list)  # extracted from descriptions
    sample_ticket_ids: List[str] = Field(default_factory=list, max_items=5)
    last_seen_description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "issue_memories"
        indexes = [
            "ward_id",
            "issue_category",
            "month",
            [("ward_id", 1), ("issue_category", 1), ("month", 1)],
        ]

    class Config:
        populate_by_name = True
