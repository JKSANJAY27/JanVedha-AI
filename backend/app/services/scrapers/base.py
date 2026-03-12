"""
Base scraper — adapted from Scrapify Labs for JanVedha AI.
Uses JanVedha's Settings instead of Scrapify's.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any


@dataclass
class ScrapedItem:
    """Lightweight data class for scraped content (replaces Scrapify's ScrapedPost)."""
    platform: str
    content: str
    source_url: str = ""
    author: Optional[str] = None
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    post_timestamp: Optional[datetime] = None
    keywords: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Filled in after AI structuring
    category: Optional[str] = None
    subcategory: Optional[str] = None
    urgency: Optional[str] = None
    sentiment: Optional[str] = None
    summary: Optional[str] = None
    action_needed: Optional[str] = None


class BaseScraper(ABC):
    """Abstract base for all platform scrapers."""

    platform: str = "unknown"

    def __init__(self, settings):
        self.settings = settings
        self.logger = logging.getLogger(f"scraper.{self.platform}")

    @abstractmethod
    async def scrape(self, keywords: List[str], max_results: int = 20) -> List[ScrapedItem]:
        ...

    @abstractmethod
    def is_configured(self) -> bool:
        ...

    async def safe_scrape(self, keywords: List[str], max_results: int = 20) -> List[ScrapedItem]:
        """Wrapper that catches exceptions so one failing scraper can't kill the job."""
        if not self.is_configured():
            self.logger.info("%s not configured — skipping", self.platform)
            return []
        try:
            return await self.scrape(keywords, max_results)
        except Exception as e:
            self.logger.error("%s scrape failed: %s", self.platform, e, exc_info=True)
            return []
