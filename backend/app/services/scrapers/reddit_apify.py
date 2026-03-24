"""
Reddit Scraper via Apify for JanVedha AI — Grievance Ingestion

Adapted from Scrapify-Labs' ApifyRedditScraper.
Uses Apify's Reddit Scraper actor — no Reddit API keys needed!
Falls back gracefully if Apify token is not set.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from app.services.scrapers.base import BaseScraper, ScrapedItem

logger = logging.getLogger(__name__)


class ApifyRedditScraper(BaseScraper):
    """Scrape Reddit via Apify — no Reddit API keys required."""

    platform = "reddit"

    # Trudax Reddit Scraper (most popular, reliable)
    ACTOR_ID = "trudax~reddit-scraper"

    def is_configured(self) -> bool:
        return bool(self.settings.APIFY_API_TOKEN)

    async def scrape(self, keywords: List[str], max_results: int = 20) -> List[ScrapedItem]:
        try:
            from apify_client import ApifyClient
        except ImportError:
            self.logger.error("apify-client not installed — pip install apify-client")
            return []

        client = ApifyClient(self.settings.APIFY_API_TOKEN)
        items: List[ScrapedItem] = []

        for keyword in keywords:
            if len(items) >= max_results:
                break

            try:
                run_input = {
                    "searches": [keyword],
                    "maxItems": min(max_results - len(items), 15),
                    "sort": "new",
                    "type": "post",
                }

                self.logger.info("Apify Reddit: searching '%s'", keyword)
                run = client.actor(self.ACTOR_ID).call(run_input=run_input)

                for item in client.dataset(run["defaultDatasetId"]).iterate_items():
                    try:
                        content = (
                            item.get("title", "") + "\n\n" +
                            item.get("body", item.get("selftext", item.get("text", "")))
                        ).strip()

                        if not content or len(content) < 10:
                            continue

                        items.append(ScrapedItem(
                            platform="reddit",
                            source_url=item.get("url", item.get("postUrl", "")),
                            author=f"u/{item.get('author', item.get('username', 'unknown'))}",
                            content=content,
                            post_timestamp=_parse_timestamp(
                                item.get("createdAt", item.get("created_utc"))
                            ),
                            keywords=[keyword],
                            metadata={
                                "subreddit": item.get("subreddit", item.get("communityName", "")),
                                "score": item.get("ups", item.get("score", 0)),
                                "comments": item.get("numberOfComments", item.get("num_comments", 0)),
                                "source": "apify_reddit",
                            },
                        ))
                    except Exception as e:
                        self.logger.debug("Skipping Reddit post: %s", e)

                    if len(items) >= max_results:
                        break

            except Exception as e:
                self.logger.error("Apify Reddit failed for '%s': %s", keyword, e)

        return items[:max_results]


def _parse_timestamp(ts) -> Optional[datetime]:
    if not ts:
        return None
    try:
        if isinstance(ts, (int, float)):
            return datetime.utcfromtimestamp(ts)
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
