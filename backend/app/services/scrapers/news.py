"""
News Scraper — adapted from Scrapify Labs for JanVedha AI.
Aggregates from GNews, Currents API, and NewsData.io concurrently.
"""
from __future__ import annotations

import asyncio
import urllib.parse
from datetime import datetime, timezone
from typing import List

import httpx

from app.services.scrapers.base import BaseScraper, ScrapedItem


class NewsScraper(BaseScraper):
    platform = "news"

    def is_configured(self) -> bool:
        return bool(
            self.settings.GNEWS_API_KEY
            or self.settings.CURRENTS_API_KEY
            or self.settings.NEWSDATA_API_KEY
        )

    async def scrape(self, keywords: List[str], max_results: int = 20) -> List[ScrapedItem]:
        query = " ".join(keywords)
        async with httpx.AsyncClient(timeout=15.0) as client:
            tasks = []
            if self.settings.GNEWS_API_KEY:
                tasks.append(self._fetch_gnews(client, query, max_results))
            if self.settings.CURRENTS_API_KEY:
                tasks.append(self._fetch_currents(client, query, max_results))
            if self.settings.NEWSDATA_API_KEY:
                tasks.append(self._fetch_newsdata(client, query, max_results))

            if not tasks:
                return []

            results = await asyncio.gather(*tasks, return_exceptions=True)

        seen_urls: set = set()
        final: List[ScrapedItem] = []
        for result in results:
            if isinstance(result, BaseException):
                self.logger.error("News API error: %s", result)
                continue
            for item in result:
                if len(final) >= max_results:
                    break
                if item.source_url not in seen_urls:
                    final.append(item)
                    seen_urls.add(item.source_url)

        return final

    async def _fetch_gnews(self, client: httpx.AsyncClient, keyword: str, limit: int) -> List[ScrapedItem]:
        encoded = urllib.parse.quote(keyword)
        url = (
            f"https://gnews.io/api/v4/search"
            f"?q={encoded}&token={self.settings.GNEWS_API_KEY}&max={limit}&lang=en"
        )
        items: List[ScrapedItem] = []
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            for article in data.get("articles", []):
                content = f"{article.get('title', '')}\n\n{article.get('description', '')}".strip()
                dt_str = article.get("publishedAt")
                try:
                    dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00")) if dt_str else datetime.now(timezone.utc)
                except Exception:
                    dt = datetime.now(timezone.utc)
                items.append(ScrapedItem(
                    platform="news",
                    author=article.get("source", {}).get("name", "GNews"),
                    content=content,
                    source_url=article.get("url", ""),
                    post_timestamp=dt,
                    keywords=[keyword],
                    metadata={"source": "gnews"},
                ))
        except Exception as e:
            self.logger.error("GNews failed: %s", e)
        return items

    async def _fetch_currents(self, client: httpx.AsyncClient, keyword: str, limit: int) -> List[ScrapedItem]:
        encoded = urllib.parse.quote(keyword)
        url = (
            f"https://api.currentsapi.services/v1/search"
            f"?keywords={encoded}&language=en&apiKey={self.settings.CURRENTS_API_KEY}&limit={limit}"
        )
        items: List[ScrapedItem] = []
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            for article in data.get("news", []):
                content = f"{article.get('title', '')}\n\n{article.get('description', '')}".strip()
                dt_str = article.get("published")
                try:
                    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S %z") if dt_str else datetime.now(timezone.utc)
                except Exception:
                    dt = datetime.now(timezone.utc)
                items.append(ScrapedItem(
                    platform="news",
                    author=article.get("author") or "Currents",
                    content=content,
                    source_url=article.get("url", ""),
                    post_timestamp=dt,
                    keywords=[keyword],
                    metadata={"source": "currents"},
                ))
        except Exception as e:
            self.logger.error("Currents API failed: %s", e)
        return items

    async def _fetch_newsdata(self, client: httpx.AsyncClient, keyword: str, limit: int) -> List[ScrapedItem]:
        encoded = urllib.parse.quote(keyword)
        url = (
            f"https://newsdata.io/api/1/news"
            f"?apikey={self.settings.NEWSDATA_API_KEY}&q={encoded}&language=en"
        )
        items: List[ScrapedItem] = []
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            for idx, article in enumerate(data.get("results", [])):
                if idx >= limit:
                    break
                content = f"{article.get('title', '')}\n\n{article.get('description', '')}".strip()
                creators = article.get("creator")
                author = creators[0] if isinstance(creators, list) and creators else article.get("source_id", "NewsData")
                dt_str = article.get("pubDate")
                try:
                    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc) if dt_str else datetime.now(timezone.utc)
                except Exception:
                    dt = datetime.now(timezone.utc)
                items.append(ScrapedItem(
                    platform="news",
                    author=author,
                    content=content,
                    source_url=article.get("link", ""),
                    post_timestamp=dt,
                    keywords=[keyword],
                    metadata={"source": "newsdata"},
                ))
        except Exception as e:
            self.logger.error("NewsData failed: %s", e)
        return items
