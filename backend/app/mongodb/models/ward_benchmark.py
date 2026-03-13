"""
MongoDB Document: WardBenchmark

Stores synthetic peer ward performance metrics for cross-ward benchmarking.
Collection: ward_benchmarks
"""
from beanie import Document
from pydantic import Field
from typing import Dict, Optional
from datetime import datetime


class WardBenchmarkMongo(Document):
    ward_name: str
    ward_id: int
    avg_resolution_days_by_dept: Dict[str, float] = Field(
        default_factory=dict,
        description="e.g. {'roads': 4.2, 'electrical': 2.1}"
    )
    ticket_volume: int = 0
    technician_count: int = 0
    resolution_rate_pct: float = 0.0
    top_practice: str = ""
    notes: Optional[str] = None
    seeded: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "ward_benchmarks"

    class Config:
        populate_by_name = True
