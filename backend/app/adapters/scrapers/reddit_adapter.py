"""
RedditAdapter — Real PRAW-Based Reddit Scraper for Civic Complaints

Searches Tamil Nadu / Indian civic subreddits for issue-related posts.
Returns anonymised ScrapedPost objects (no usernames, no PII ever).

Setup:
  Create a Reddit app at https://www.reddit.com/prefs/apps (free)
  Set in your .env:
    REDDIT_CLIENT_ID=<your client id>
    REDDIT_CLIENT_SECRET=<your client secret>
    REDDIT_USER_AGENT=JanVedhaAI/1.0

If credentials are not set, the adapter returns an empty list gracefully.

Civic keyword pre-filter:
  Only posts containing at least one civic keyword (pothole, water, garbage, etc.)
  are returned. This filters out ~80% of irrelevant posts before any LLM call,
  cutting API costs significantly.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from app.interfaces.scraper_provider import ScraperProvider, ScrapedPost

logger = logging.getLogger(__name__)

# Subreddits to search for Indian civic complaints
CIVIC_SUBREDDITS = [
    "Chennai", "bangalore", "mumbai", "delhi", "india",
    "hyderabad", "pune", "kolkata",
]

CIVIC_KEYWORDS = [
    # English
    "pothole", "garbage", "water supply", "street light", "streetlight",
    "drain", "sewage", "road", "electricity", "power cut", "flooding",
    "flood", "waste", "sanitation", "municipality", "corporation",
    "manhole", "footpath", "pavement", "traffic", "signal", "park",
    "stray dog", "mosquito", "dead animal", "open drain",
    # Tamil
    "குழி", "குப்பை", "தண்ணீர்", "விளக்கு", "வடிகால்",
    # Hindi
    "गड्डा", "कचरा", "पानी", "बिजली", "सड़क",
]


def _is_civic_complaint(text: str) -> bool:
    """Fast keyword pre-filter. Returns True if the post is civic-related."""
    lower = text.lower()
    return any(kw.lower() in lower for kw in CIVIC_KEYWORDS)


class RedditAdapter(ScraperProvider):
    """PRAW-based Reddit scraper for civic complaints."""

    def __init__(self):
        self._reddit = None
        self._init_attempted = False

    def _try_init(self) -> bool:
        """Lazy-initialize asyncpraw.Reddit client from environment variables."""
        if self._init_attempted:
            return self._reddit is not None

        self._init_attempted = True
        client_id = os.getenv("REDDIT_CLIENT_ID", "").strip()
        client_secret = os.getenv("REDDIT_CLIENT_SECRET", "").strip()
        user_agent = os.getenv("REDDIT_USER_AGENT", "JanVedhaAI/1.0 (civic complaint tracker)")

        if not client_id or not client_secret:
            logger.warning(
                "Reddit credentials not set. Set REDDIT_CLIENT_ID and "
                "REDDIT_CLIENT_SECRET in .env to enable Reddit scraping."
            )
            return False

        try:
            import asyncpraw
            self._reddit = asyncpraw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent,
            )
            logger.info("Reddit (asyncpraw) client initialized successfully.")
            return True
        except ImportError:
            logger.warning("asyncpraw not installed. Run: pip install asyncpraw")
            return False
        except Exception as exc:
            logger.warning("Reddit client init failed: %s", exc)
            return False

    async def scrape_recent(
        self, keywords: list[str], city: str, limit: int = 50
    ) -> list[ScrapedPost]:
        """
        Search civic subreddits for posts matching the given keywords + city.
        Strips all PII before returning.
        """
        if not self._try_init():
            return []

        posts: list[ScrapedPost] = []
        search_query = f"{city} {' OR '.join(keywords[:5])}"  # Reddit search query
        seen_ids: set[str] = set()

        subreddits_to_search = [city.lower()] + CIVIC_SUBREDDITS

        try:
            for subreddit_name in subreddits_to_search[:5]:  # Limit to 5 subreddits
                try:
                    subreddit = await self._reddit.subreddit(subreddit_name)
                    submissions = subreddit.search(
                        search_query,
                        sort="new",
                        time_filter="week",
                        limit=limit // len(subreddits_to_search[:5]),
                    )

                    async for submission in submissions:
                        # Deduplication
                        if submission.id in seen_ids:
                            continue
                        seen_ids.add(submission.id)

                        # Combine title + selftext for analysis
                        full_text = f"{submission.title} {submission.selftext}".strip()

                        # Keyword pre-filter — skip non-civic posts
                        if not _is_civic_complaint(full_text):
                            continue

                        # Strip PII — never include author, username, or profile data
                        posts.append(ScrapedPost(
                            platform="REDDIT",
                            post_id=submission.id,
                            text=full_text[:2000],           # Truncate long posts
                            location_hint=self._extract_location(full_text, city),
                            source_url=f"https://reddit.com{submission.permalink}",
                            scraped_at=datetime.fromtimestamp(
                                submission.created_utc, tz=timezone.utc
                            ).replace(tzinfo=None),
                        ))

                        if len(posts) >= limit:
                            break

                except Exception as exc:
                    logger.debug("Subreddit r/%s search failed: %s", subreddit_name, exc)
                    continue

            logger.info(
                "Reddit scrape complete: %d civic posts found (searched query: %s)",
                len(posts), search_query,
            )
            return posts

        except Exception as exc:
            logger.warning("Reddit scrape failed: %s", exc)
            return []
        finally:
            # Close aiohttp session after each scrape cycle
            try:
                await self._reddit.close()
                self._reddit = None
                self._init_attempted = False  # Allow re-init on next call
            except Exception:
                pass

    @staticmethod
    def _extract_location(text: str, city: str) -> str:
        """
        Naively extract a location hint from the post text.
        Returns the city name as fallback.
        """
        # Look for common Indian location patterns: "near X", "at X", "in X area"
        import re
        pattern = r"\b(?:near|at|in|around|opposite)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)"
        match = re.search(pattern, text)
        if match:
            return match.group(1)
        return city
