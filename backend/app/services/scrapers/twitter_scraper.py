"""
Twitter/X Scraper for JanVedha AI — Grievance Ingestion

Tiered fallback strategy (adapted from Scrapify-Labs):
  1. Apify Tweet Scraper actor (scalable, maintained)
  2. Graceful skip if no Apify token

Searches for civic grievance keywords + Chennai-specific hashtags.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from app.services.scrapers.base import BaseScraper, ScrapedItem

logger = logging.getLogger(__name__)

# Chennai civic keywords and handles
CIVIC_HASHTAGS = [
    "#ChennaiCivic", "#GCC", "#ChennaiCorpn", "#GreaterChennai",
    "#ChennaiFloods", "#ChennaiWater", "#ChennaiRoads",
    "@chenaboratn", "@chenaboratn_offl",
]


class TwitterScraper(BaseScraper):
    """Scrape Twitter/X for civic grievances using Apify."""

    platform = "twitter"

    # Apify Tweet Scraper V2 actor ID (from Scrapify-Labs)
    ACTOR_ID = "61RPP7dywgiy0JPD0"

    def is_configured(self) -> bool:
        return bool(self.settings.APIFY_API_TOKEN)

    async def scrape(self, keywords: List[str], max_results: int = 20) -> List[ScrapedItem]:
        if not self.settings.APIFY_API_TOKEN:
            self.logger.warning("APIFY_API_TOKEN not set — Twitter scraper disabled")
            return []

        try:
            from apify_client import ApifyClient
        except ImportError:
            self.logger.error("apify-client not installed — pip install apify-client")
            return []

        client = ApifyClient(self.settings.APIFY_API_TOKEN)
        items: List[ScrapedItem] = []

        # Combine user keywords with civic hashtags
        search_terms = keywords + CIVIC_HASHTAGS[:3]  # limit to avoid quota burn

        for keyword in search_terms:
            if len(items) >= max_results:
                break

            try:
                run_input = {
                    "searchTerms": [keyword],
                    "maxTweets": min(max_results - len(items), 15),
                    "sort": "Latest",
                }

                self.logger.info("Apify Twitter: searching '%s'", keyword)
                run = client.actor(self.ACTOR_ID).call(run_input=run_input)

                for tweet in client.dataset(run["defaultDatasetId"]).iterate_items():
                    try:
                        content = tweet.get("text", "")
                        if not content or len(content) < 10:
                            continue

                        author_info = tweet.get("author", {})
                        author = f"@{author_info.get('userName', 'unknown')}"

                        items.append(ScrapedItem(
                            platform="twitter",
                            source_url=tweet.get("url", ""),
                            author=author,
                            content=content,
                            post_timestamp=_parse_timestamp(tweet.get("createdAt")),
                            keywords=[keyword],
                            metadata={
                                "likes": tweet.get("likeCount", 0),
                                "retweets": tweet.get("retweetCount", 0),
                                "replies": tweet.get("replyCount", 0),
                                "views": tweet.get("viewCount", 0),
                                "source": "apify_twitter",
                                "engagement": (
                                    tweet.get("likeCount", 0) +
                                    tweet.get("retweetCount", 0) * 2 +
                                    tweet.get("replyCount", 0)
                                ),
                            },
                        ))
                    except Exception as e:
                        self.logger.debug("Skipping tweet: %s", e)

                    if len(items) >= max_results:
                        break

            except Exception as e:
                self.logger.error("Apify Twitter failed for '%s': %s", keyword, e)

        return items[:max_results]


def _parse_timestamp(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
