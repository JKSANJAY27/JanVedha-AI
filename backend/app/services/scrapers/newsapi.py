"""
NewsAPI.org Scraper — JanVedha AI
Uses SIMPLE single-keyword queries (no complex boolean chains)
to ensure compatibility with NewsAPI free plan.
"""
from __future__ import annotations

import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import List

import httpx

from app.services.scrapers.base import BaseScraper, ScrapedItem

NEWSAPI_BASE_URL = "https://newsapi.org/v2/everything"

# These fallback queries are used only if no ward area is provided.
DEFAULT_CITY = "Chennai"
FALLBACK_QUERIES = [
    f"{DEFAULT_CITY} civic",
    f"{DEFAULT_CITY} pothole",
    f"{DEFAULT_CITY} garbage",
    f"{DEFAULT_CITY} water shortage",
    f"{DEFAULT_CITY} drainage",
    f"{DEFAULT_CITY} electricity",
]


class NewsApiScraper(BaseScraper):
    """Scraper using NewsAPI.org /v2/everything with simple queries."""
    platform = "news"

    def is_configured(self) -> bool:
        return bool(self.settings.NEWS_API_KEY)

    async def scrape(self, keywords: List[str], max_results: int = 30) -> List[ScrapedItem]:
        """
        Fetch civic news articles using multiple simple keyword searches.
        Simple queries avoid the 426 'Upgrade Required' error from NewsAPI.
        """
        if not self.settings.NEWS_API_KEY:
            self.logger.error("NEWS_API_KEY is not set — NewsAPI scraper disabled")
            return []

        from_date = (datetime.now(timezone.utc) - timedelta(days=27)).date().isoformat()

        all_items: List[ScrapedItem] = []
        seen_urls: set = set()

        # Build query list — prepend area-specific query if available
        queries = []
        if keywords:
            for kw in keywords:
                if kw and len(kw) < 30:
                    queries.extend([
                        f"{kw} civic",
                        f"{kw} infrastructure",
                        f"{kw} road",
                        f"{kw} water",
                        f"{kw} {DEFAULT_CITY}",
                    ])
                    break
        
        # Add fallbacks dynamically
        queries.extend(FALLBACK_QUERIES)

        # Run up to 4 queries to get enough articles (100/day rate limit)
        per_query = max(5, max_results // 4)
        for q in queries[:4]:
            items = await self._fetch_simple(q, from_date, page_size=per_query)
            self.logger.info("NewsAPI query '%s' → %d articles", q[:40], len(items))
            for item in items:
                if item.source_url not in seen_urls:
                    seen_urls.add(item.source_url)
                    all_items.append(item)
            if len(all_items) >= max_results:
                break

        self.logger.info("NewsAPI total unique articles: %d", len(all_items))
        return all_items[:max_results]

    async def _fetch_simple(self, query: str, from_date: str, page_size: int = 10) -> List[ScrapedItem]:
        """Execute one simple NewsAPI query."""
        params = {
            "q": query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": min(page_size, 20),
            "from": from_date,
            "apiKey": self.settings.NEWS_API_KEY,
        }

        items: List[ScrapedItem] = []
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(NEWSAPI_BASE_URL, params=params)

                if resp.status_code == 426:
                    err_msg = resp.text
                    self.logger.error(
                        "NewsAPI 426 (plan limit): '%s' - %s", query, err_msg
                    )
                    return []

                resp.raise_for_status()
                data = resp.json()

                if data.get("status") != "ok":
                    self.logger.warning(
                        "NewsAPI error: %s — %s", data.get("status"), data.get("message")
                    )
                    return []

                for article in data.get("articles", []):
                    url = article.get("url", "")
                    if not url:
                        continue
                    title = (article.get("title") or "").strip()
                    if title in ("[Removed]", "", None):
                        continue

                    description = (article.get("description") or "").strip()
                    content_snippet = (article.get("content") or "")[:400].strip()

                    parts = [p for p in [title, description, content_snippet] if p]
                    content = "\n\n".join(parts)
                    if not content:
                        continue

                    dt_str = article.get("publishedAt")
                    try:
                        dt = (
                            datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                            if dt_str else datetime.now(timezone.utc)
                        )
                    except Exception:
                        dt = datetime.now(timezone.utc)

                    source_name = article.get("source", {}).get("name") or "News"

                    items.append(ScrapedItem(
                        platform="news",
                        author=source_name,
                        content=content,
                        source_url=url,
                        post_timestamp=dt,
                        keywords=["newsapi", "civic", "india"],
                        metadata={
                            "source": "newsapi_org",
                            "source_name": source_name,
                            "title": title,
                            "query": query,
                        },
                    ))

        except httpx.HTTPStatusError as e:
            self.logger.error("NewsAPI HTTP %s for query '%s': %s", e.response.status_code, query, e)
        except Exception as e:
            self.logger.error("NewsAPI scraper error for query '%s': %s", query, e)

        return items
