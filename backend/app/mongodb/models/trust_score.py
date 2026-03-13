"""
MongoDB Document: TrustScore

Monthly ward trust score snapshots for trend tracking.
Collection: trust_score_history
"""
from beanie import Document, Indexed
from pydantic import Field
from typing import Optional
from datetime import datetime


class TrustScoreMongo(Document):
    ward_id: Indexed(int)                             # type: ignore[valid-type]
    month: str                                        # "YYYY-MM"
    trust_score: float                               # 0–100

    # Component metrics
    on_time_rate: float = 0.0                        # SLA compliance rate
    avg_resolution_hours: float = 0.0
    verified_completion_rate: float = 0.0
    citizen_satisfaction: float = 0.0
    reopen_rate: float = 0.0

    # Raw counts for drilldown
    total_resolved: int = 0
    resolved_within_sla: int = 0
    verified_resolutions: int = 0
    total_sentiment_posts: int = 0
    positive_sentiment_posts: int = 0
    reopened_tickets: int = 0

    computed_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "trust_score_history"
        indexes = [
            "ward_id",
            "month",
            [("ward_id", 1), ("month", -1)],
        ]

    class Config:
        populate_by_name = True
