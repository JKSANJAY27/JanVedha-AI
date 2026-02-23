from app.interfaces.scraper_provider import ScraperProvider, ScrapedPost
from datetime import datetime


class RedditAdapter(ScraperProvider):
    """Stub implementation of Reddit scraper provider."""

    async def scrape_recent(
        self, keywords: list[str], city: str, limit: int = 50
    ) -> list[ScrapedPost]:
        """Stub implementation - returns empty list."""
        return []
