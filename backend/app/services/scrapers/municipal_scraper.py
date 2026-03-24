"""
Indian Civic Portal Scraper for JanVedha AI — Grievance Ingestion

Adapted from Scrapify-Labs' IndiaCivicScraper.
Uses Crawl4AI (open-source AI web crawler) to scrape Indian government
portals for civic grievance data.

Tiered fallback:
  1. Crawl4AI (headless browser, always available)
  2. httpx + BeautifulSoup (lightweight fallback for simpler pages)
  3. Skip gracefully on failure

Sources scraped:
  - data.gov.in (Open Government Data)
  - MyGov India (citizen engagement)
  - Smart Cities India
  - Swachh Bharat Mission
  - India Environmental Portal
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import List, Optional, Dict, Any

from app.services.scrapers.base import BaseScraper, ScrapedItem

logger = logging.getLogger(__name__)

# Indian government data sources — all publicly accessible
INDIA_CIVIC_SOURCES = [
    {
        "name": "Open Government Data India",
        "url": "https://data.gov.in/search?title={keyword}",
        "type": "open_data",
    },
    {
        "name": "MyGov India",
        "url": "https://www.mygov.in/search/node/{keyword}",
        "type": "citizen_engagement",
    },
    {
        "name": "Smart Cities India",
        "url": "https://smartcities.gov.in/",
        "type": "smart_cities",
    },
    {
        "name": "Swachh Bharat Mission",
        "url": "https://sbm.gov.in/sbmdashboard/",
        "type": "sanitation",
    },
    {
        "name": "India Environmental Portal",
        "url": "https://www.indiaenvironmentportal.org.in/search/node/{keyword}",
        "type": "environment",
    },
]


class IndiaCivicScraper(BaseScraper):
    """
    Crawl4AI-powered scraper for Indian civic/government portals.
    Falls back to httpx+BeautifulSoup if Crawl4AI is unavailable.
    """

    platform = "civic"

    def __init__(self, settings, sources: Optional[List[Dict[str, Any]]] = None):
        super().__init__(settings)
        self.sources = sources or INDIA_CIVIC_SOURCES

    def is_configured(self) -> bool:
        return True  # Always available — uses open-source web crawling

    async def scrape(self, keywords: List[str], max_results: int = 20) -> List[ScrapedItem]:
        # Try Crawl4AI first
        try:
            return await self._scrape_crawl4ai(keywords, max_results)
        except ImportError:
            self.logger.info("crawl4ai not installed — falling back to httpx+BS4")
        except Exception as e:
            self.logger.error("Crawl4AI failed: %s — falling back to httpx+BS4", e)

        # Fallback: httpx + BeautifulSoup
        return await self._scrape_bs4(keywords, max_results)

    async def _scrape_crawl4ai(self, keywords: List[str], max_results: int) -> List[ScrapedItem]:
        """Primary: Crawl4AI headless browser scraping."""
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

        items: List[ScrapedItem] = []
        browser_config = BrowserConfig(headless=True, verbose=False)

        async with AsyncWebCrawler(config=browser_config) as crawler:
            for source in self.sources:
                if len(items) >= max_results:
                    break

                for keyword in keywords:
                    if len(items) >= max_results:
                        break

                    url = source["url"].format(keyword=keyword)
                    self.logger.info("Crawl4AI: %s → %s", source["name"], url)

                    try:
                        run_config = CrawlerRunConfig(
                            wait_until="domcontentloaded",
                            page_timeout=30000,
                        )
                        result = await crawler.arun(url=url, config=run_config)

                        if not result.success:
                            self.logger.warning(
                                "Crawl failed for %s: %s",
                                source["name"], result.error_message,
                            )
                            continue

                        content = result.markdown or ""
                        if not content or len(content) < 50:
                            continue

                        extracted = _extract_relevant_content(
                            content, keywords, source
                        )
                        items.extend(extracted[:max_results - len(items)])

                    except Exception as e:
                        self.logger.error("Crawl4AI error for %s: %s", source["name"], e)

        return items[:max_results]

    async def _scrape_bs4(self, keywords: List[str], max_results: int) -> List[ScrapedItem]:
        """Fallback: httpx + BeautifulSoup for simpler pages."""
        import httpx

        try:
            from bs4 import BeautifulSoup
        except ImportError:
            self.logger.error("beautifulsoup4 not installed — civic scraper fully disabled")
            return []

        items: List[ScrapedItem] = []

        async with httpx.AsyncClient(timeout=15.0) as client:
            for source in self.sources:
                if len(items) >= max_results:
                    break

                for keyword in keywords:
                    if len(items) >= max_results:
                        break

                    url = source["url"].format(keyword=keyword)
                    try:
                        resp = await client.get(
                            url,
                            headers={"User-Agent": "JanVedha-AI/2.0"},
                            follow_redirects=True,
                        )
                        if resp.status_code != 200:
                            continue

                        soup = BeautifulSoup(resp.text, "html.parser")

                        # Remove scripts and styles
                        for tag in soup(["script", "style", "nav", "footer", "header"]):
                            tag.decompose()

                        # Extract text paragraphs
                        paragraphs = soup.find_all(["p", "li", "h2", "h3", "article", "div"])
                        for para in paragraphs:
                            text = para.get_text(strip=True)
                            if len(text) < 30:
                                continue
                            # Check keyword relevance
                            matched = [k for k in keywords if k.lower() in text.lower()]
                            if not matched:
                                continue

                            # Try to find a link
                            link = para.find("a", href=True)
                            source_url = link["href"] if link else url

                            items.append(ScrapedItem(
                                platform="civic",
                                source_url=source_url,
                                author=source.get("name", "Indian Government"),
                                content=text[:2000],
                                post_timestamp=_extract_date(text),
                                keywords=matched,
                                metadata={
                                    "source_name": source.get("name", ""),
                                    "source_type": source.get("type", "civic"),
                                    "scraper": "bs4_fallback",
                                },
                            ))

                            if len(items) >= max_results:
                                break

                    except Exception as e:
                        self.logger.error("BS4 scraper error for %s: %s", source["name"], e)

        return items[:max_results]


def _extract_relevant_content(
    markdown: str, keywords: List[str], source: Dict[str, Any]
) -> List[ScrapedItem]:
    """Parse crawled markdown into ScrapedItem objects, filtering by keywords."""
    items: List[ScrapedItem] = []
    sections = re.split(r"\n---\n|\n#{1,3}\s|\n\n\n+", markdown)

    for section in sections:
        text = section.strip()
        if len(text) < 30:
            continue

        matched = [k for k in keywords if k.lower() in text.lower()]
        if not matched:
            continue

        # Try to extract links
        links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", text)
        source_url = links[0][1] if links else source.get("url", "")

        items.append(ScrapedItem(
            platform="civic",
            source_url=source_url,
            author=source.get("name", "Indian Government"),
            content=text[:2000],
            post_timestamp=_extract_date(text),
            metadata={
                "source_name": source.get("name", ""),
                "source_type": source.get("type", "civic"),
                "scraper": "crawl4ai",
            },
            keywords=matched,
        ))

    return items


def _extract_date(text: str) -> Optional[datetime]:
    """Try to find a date in the text."""
    patterns = [
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"(\d{4}-\d{2}-\d{2})",
        r"(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                from dateutil.parser import parse as dateparse
                return dateparse(match.group(1))
            except Exception:
                pass
    return None
