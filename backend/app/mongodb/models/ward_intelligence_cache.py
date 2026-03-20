"""
MongoDB Document: WardIntelligenceCache

Stores cached results from Gemini AI intelligence endpoints to prevent
excessive API calls on every dashboard load. Data is refreshed explicitly
via a triggered refresh action, not on every page load.
"""
from beanie import Document, Indexed
from pydantic import Field
from typing import Optional, List, Any, Dict
from datetime import datetime


class WardIntelligenceCache(Document):
    """
    Cached AI-generated intelligence for a given ward.
    Collection: ward_intelligence_cache
    """
    ward_id: Indexed(int)                               # type: ignore[valid-type]
    cache_type: Indexed(str)                            # type: ignore[valid-type]
    # "briefing" | "root_causes" | "predictions"

    # Briefing fields
    briefing: Optional[str] = None

    # Root causes fields (stored as JSON-serializable list)
    root_causes: Optional[List[Dict[str, Any]]] = None

    # Predictive alerts fields (stored as JSON-serializable list)
    alerts: Optional[List[Dict[str, Any]]] = None

    computed_at: datetime = Field(default_factory=datetime.utcnow)
    is_stale: bool = False

    class Settings:
        name = "ward_intelligence_cache"
        indexes = [
            "ward_id",
            "cache_type",
            "computed_at",
        ]

    class Config:
        populate_by_name = True
