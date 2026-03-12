"""
MongoDB Document: SocialPost

Stores scraped and AI-structured social media posts for the
Social Intelligence layer of the Councillor/Commissioner dashboards.
Collection: social_posts
"""
from beanie import Document
from pydantic import Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class SocialPostMongo(Document):
    """
    A scraped social media / civic post enriched by Gemini AI.
    """
    platform: str                          # "twitter","reddit","news","civic","youtube","google_maps"
    source_url: str = ""
    author: Optional[str] = None
    content: str = ""

    # Geo info
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Ward mapping (best-effort from location text, or passed explicitly)
    ward_id: Optional[int] = None

    # AI structuring from Gemini
    category: Optional[str] = None         # "Infrastructure","Water Supply","Sanitation", etc.
    subcategory: Optional[str] = None
    urgency: Optional[str] = None          # "critical","high","medium","low"
    sentiment: Optional[str] = None        # "negative","neutral","positive"
    summary: Optional[str] = None          # one-liner from Gemini
    action_needed: Optional[str] = None

    # Scraper metadata
    keywords: List[str] = Field(default_factory=list)
    post_timestamp: Optional[datetime] = None   # when the original post was made
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Settings:
        name = "social_posts"
        indexes = [
            "platform",
            "ward_id",
            "sentiment",
            "urgency",
            "category",
            "scraped_at",
        ]

    class Config:
        populate_by_name = True
