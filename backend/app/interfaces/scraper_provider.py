from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ScrapedPost:
    """
    Anonymised scraped post. NO username, NO profile info. Ever.
    Only issue content + location hint + source traceability.
    """
    platform: str        # REDDIT | TWITTER | YOUTUBE | NEWS
    post_id: str         # platform-specific ID (for deduplication)
    text: str            # issue description text only
    location_hint: str   # location text if present in post
    source_url: str      # direct URL to original post
    scraped_at: datetime

class ScraperProvider(ABC):

    @abstractmethod
    async def scrape_recent(
        self, keywords: list[str], city: str, limit: int = 50
    ) -> list[ScrapedPost]:
        """
        Scrape public posts matching keywords for a city.
        Must strip all PII before returning.
        Must check post_id against DB before returning (deduplication).
        """
        pass
