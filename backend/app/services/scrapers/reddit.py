"""
Reddit Scraper — adapted from Scrapify Labs for JanVedha AI.
Uses PRAW if Reddit keys are configured, otherwise skip.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from functools import partial
from typing import List

from app.services.scrapers.base import BaseScraper, ScrapedItem


class RedditScraper(BaseScraper):
    platform = "reddit"

    def is_configured(self) -> bool:
        return bool(self.settings.REDDIT_CLIENT_ID and self.settings.REDDIT_CLIENT_SECRET)

    async def scrape(self, keywords: List[str], max_results: int = 20) -> List[ScrapedItem]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._scrape_sync, keywords, max_results)

    def _scrape_sync(self, keywords: List[str], max_results: int) -> List[ScrapedItem]:
        try:
            import praw
        except ImportError:
            self.logger.error("praw not installed")
            return []

        reddit = praw.Reddit(
            client_id=self.settings.REDDIT_CLIENT_ID,
            client_secret=self.settings.REDDIT_CLIENT_SECRET,
            user_agent=self.settings.REDDIT_USER_AGENT,
        )

        items: List[ScrapedItem] = []
        query = " OR ".join(keywords)
        limit = max(max_results, 10)

        try:
            for submission in reddit.subreddit("all").search(query, sort="new", time_filter="week", limit=limit):
                content = f"{submission.title}\n\n{submission.selftext}".strip()
                items.append(ScrapedItem(
                    platform="reddit",
                    source_url=f"https://reddit.com{submission.permalink}",
                    author=str(submission.author) if submission.author else None,
                    content=content,
                    post_timestamp=datetime.fromtimestamp(submission.created_utc, tz=timezone.utc),
                    keywords=[k for k in keywords if k.lower() in content.lower()],
                    metadata={
                        "subreddit": str(submission.subreddit),
                        "score": submission.score,
                        "num_comments": submission.num_comments,
                    },
                ))
                if len(items) >= max_results:
                    break
        except Exception as e:
            self.logger.error("Reddit search failed: %s", e)

        return items
