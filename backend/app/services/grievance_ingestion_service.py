"""
GrievanceIngestionService — JanVedha AI

Core orchestrator for the real-time public grievance pipeline:
  1. Scrape all configured sources concurrently
  2. Dedup against previously ingested grievances
  3. AI-structure raw content via Gemini (category, severity, ward, sentiment)
  4. Assess severity with 2-layer scoring (keyword + AI)
  5. Auto-generate tickets for serious grievances (severity >= HIGH)

Inspired by Scrapify-Labs' scraper_manager.py architecture.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any, Tuple

import httpx

from app.core.config import settings
from app.mongodb.models.grievance import GrievanceMongo
from app.services.scrapers.base import ScrapedItem

logger = logging.getLogger("grievance_ingestion")

# ─────────────────────────────────────────────────────────────────────────────
# Severity keyword matching (fast rule-based layer)
# ─────────────────────────────────────────────────────────────────────────────
SEVERITY_KEYWORDS = {
    "critical": [
        "death", "dead", "died", "fatal", "collapse", "collapsed", "building collapse",
        "flood", "tsunami", "earthquake", "explosion", "fire", "electrocution",
        "epidemic", "pandemic", "cholera", "typhoid", "gas leak", "bridge collapse",
    ],
    "high": [
        "danger", "hazard", "dengue", "malaria", "outbreak", "accident", "injury",
        "protest", "strike", "open manhole", "live wire", "dangling wire",
        "sewage overflow", "water contamination", "stray dog attack", "bite",
        "road cave", "sinkhole", "waterlogging", "no water",
    ],
    "medium": [
        "complaint", "issue", "problem", "pothole", "garbage", "broken",
        "not working", "damaged", "delay", "disruption", "stench",
        "mosquito", "stagnant", "blocked drain", "street light",
    ],
}

# Gemini structuring prompt
STRUCTURING_PROMPT = """You are an AI assistant for a civic governance platform in {city}, India.
Analyze the following public grievance text and extract structured information.

Text: "{content}"

Respond with ONLY a JSON object (no markdown, no explanation) with these fields:
{{
  "structured_summary": "one-line summary (max 100 chars)",
  "category": "one of: Sanitation, Water Supply, Infrastructure, Electricity, Public Safety, Health, Environment, Transport, Other",
  "subcategory": "specific issue type (e.g. pothole, sewage overflow, etc)",
  "dept_id": "department code (D01-D14, see mapping below)",
  "location_text": "extracted location or area name, null if none",
  "ward_id": "integer ward number if mentioned, null if unknown",
  "severity": "critical, high, medium, or low",
  "severity_score": "float 0.0-1.0 (1.0 = most severe)",
  "severity_reasoning": "brief explanation of severity assessment",
  "sentiment": "negative, neutral, or positive",
  "affected_population": "estimated number of people affected, null if unknown"
}}

Department mapping:
D01=Roads & Bridges, D02=Buildings, D03=Water Supply, D04=Sewage & Drainage,
D05=Solid Waste, D06=Street Lighting, D07=Parks, D08=Health & Sanitation,
D09=Fire & Emergency, D10=Traffic, D11=Revenue, D12=Social Welfare,
D13=Education, D14=Disaster Management
"""

GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash:generateContent"
)


# ─────────────────────────────────────────────────────────────────────────────
# Main ingestion pipeline
# ─────────────────────────────────────────────────────────────────────────────

async def run_grievance_ingestion(
    ward_id: Optional[int] = None,
    keywords: Optional[List[str]] = None,
    max_results: int = 25,
) -> Dict[str, Any]:
    """
    Run the full grievance ingestion pipeline.
    Returns stats about what was scraped, structured, and ticketed.
    """
    city = settings.DEMO_CITY or settings.CITY_NAME or "Chennai"

    # Default civic keywords
    if not keywords:
        keywords = [
            f"{city} civic complaint",
            f"{city} water problem",
            f"{city} road damage",
            f"{city} garbage",
            f"{city} drainage",
        ]

    stats = {
        "scraped": 0,
        "new_after_dedup": 0,
        "structured": 0,
        "auto_ticketed": 0,
        "flagged_for_review": 0,
        "errors": 0,
        "by_platform": {},
    }

    # ── Step 1: Scrape all configured sources ────────────────────────────
    scraped_items = await _scrape_all_sources(keywords, max_results)
    stats["scraped"] = len(scraped_items)

    # Count by platform
    for item in scraped_items:
        platform = item.platform
        stats["by_platform"][platform] = stats["by_platform"].get(platform, 0) + 1

    if not scraped_items:
        logger.info("No items scraped — pipeline complete.")
        return stats

    # ── Step 2-5: Process each scraped item ──────────────────────────────
    dedup_window = datetime.utcnow() - timedelta(hours=72)

    for item in scraped_items:
        try:
            # Step 2: Dedup
            source_id = _compute_source_id(item)
            existing = await GrievanceMongo.find_one(
                GrievanceMongo.source_platform == item.platform,
                GrievanceMongo.source_id == source_id,
                GrievanceMongo.ingested_at >= dedup_window,
            )
            if existing:
                continue

            stats["new_after_dedup"] += 1

            # Step 3: AI structuring
            structured_data = await _structure_with_gemini(item.content, city)

            # Step 4: Keyword severity (fast layer)
            keyword_severity, keyword_score = _keyword_severity(item.content)

            # Merge AI + keyword severity (take the higher one)
            ai_score = structured_data.get("severity_score", 0.0)
            final_score = max(float(ai_score), keyword_score)
            final_severity = _score_to_severity(final_score)

            # Step 5: Persist as GrievanceMongo
            grievance = GrievanceMongo(
                source_platform=item.platform,
                source_id=source_id,
                source_url=item.source_url or "",
                raw_content=item.content,
                author=item.author,
                structured_summary=structured_data.get("structured_summary"),
                category=structured_data.get("category", item.category),
                subcategory=structured_data.get("subcategory", item.subcategory),
                dept_id=structured_data.get("dept_id"),
                location_text=structured_data.get("location_text", item.location),
                ward_id=structured_data.get("ward_id", ward_id),
                severity=final_severity,
                severity_score=final_score,
                severity_reasoning=structured_data.get("severity_reasoning"),
                sentiment=structured_data.get("sentiment", item.sentiment or "neutral"),
                affected_population=structured_data.get("affected_population"),
                original_timestamp=item.post_timestamp,
                keywords=item.keywords,
                metadata={
                    **(item.metadata or {}),
                    "ai_structured": bool(structured_data),
                    "keyword_severity": keyword_severity,
                    "keyword_score": keyword_score,
                    "ai_severity_score": ai_score,
                },
            )

            stats["structured"] += 1

            # Step 5b: Auto-ticket if severity is HIGH or CRITICAL
            auto_threshold = getattr(settings, "GRIEVANCE_AUTO_TICKET_THRESHOLD", 0.7)
            review_threshold = getattr(settings, "GRIEVANCE_REVIEW_THRESHOLD", 0.4)

            if final_score >= auto_threshold:
                ticket = await _create_ticket_from_grievance(grievance)
                if ticket:
                    grievance.auto_ticket_generated = True
                    grievance.ticket_id = str(ticket.id)
                    grievance.ticket_code = ticket.ticket_code
                    grievance.status = "ticket_created"
                    stats["auto_ticketed"] += 1
                else:
                    grievance.status = "processed"
            elif final_score >= review_threshold:
                grievance.status = "processed"
                stats["flagged_for_review"] += 1
            else:
                grievance.status = "processed"

            grievance.processed_at = datetime.utcnow()
            await grievance.insert()

        except Exception as e:
            logger.error("Failed to process grievance item: %s", e, exc_info=True)
            stats["errors"] += 1

    logger.info(
        "Grievance ingestion complete: scraped=%d, new=%d, structured=%d, auto_ticketed=%d",
        stats["scraped"], stats["new_after_dedup"],
        stats["structured"], stats["auto_ticketed"],
    )
    return stats


# ─────────────────────────────────────────────────────────────────────────────
# Scraper orchestration
# ─────────────────────────────────────────────────────────────────────────────

async def _scrape_all_sources(
    keywords: List[str], max_results: int
) -> List[ScrapedItem]:
    """Run all configured grievance scrapers concurrently."""
    tasks = []

    # 1. Twitter/X (via Apify)
    try:
        from app.services.scrapers.twitter_scraper import TwitterScraper
        scraper = TwitterScraper(settings)
        tasks.append(scraper.safe_scrape(keywords, max_results))
    except Exception as e:
        logger.error("Twitter scraper init failed: %s", e)

    # 2. India Civic Portals (Crawl4AI / BS4)
    try:
        from app.services.scrapers.municipal_scraper import IndiaCivicScraper
        scraper = IndiaCivicScraper(settings)
        tasks.append(scraper.safe_scrape(keywords, max_results))
    except Exception as e:
        logger.error("India Civic scraper init failed: %s", e)

    # 3. CPGRAMS Mock
    try:
        from app.services.scrapers.cpgrams_scraper import CPGRAMSScraper
        scraper = CPGRAMSScraper(settings)
        tasks.append(scraper.safe_scrape(keywords, max_results))
    except Exception as e:
        logger.error("CPGRAMS scraper init failed: %s", e)

    # 4. News (existing — also routes through grievance pipeline)
    try:
        if settings.NEWS_API_KEY:
            from app.services.scrapers.newsapi import NewsApiScraper
            scraper = NewsApiScraper(settings)
            tasks.append(scraper.safe_scrape(keywords, max_results=15))
    except Exception as e:
        logger.error("News scraper init failed: %s", e)

    # 5. Reddit (existing, via Apify if available)
    try:
        if settings.APIFY_API_TOKEN:
            from app.services.scrapers.reddit_apify import ApifyRedditScraper
            scraper = ApifyRedditScraper(settings)
            tasks.append(scraper.safe_scrape(keywords, max_results=10))
        elif settings.REDDIT_CLIENT_ID:
            from app.services.scrapers.reddit import RedditScraper
            scraper = RedditScraper(settings)
            tasks.append(scraper.safe_scrape(keywords, max_results=10))
    except Exception as e:
        logger.error("Reddit scraper init failed: %s", e)

    if not tasks:
        logger.warning("No scrapers configured — nothing to scrape!")
        return []

    results = await asyncio.gather(*tasks, return_exceptions=True)
    all_items: List[ScrapedItem] = []
    for result in results:
        if isinstance(result, BaseException):
            logger.error("Scraper task failed: %s", result)
            continue
        all_items.extend(result)

    return all_items


# ─────────────────────────────────────────────────────────────────────────────
# Gemini AI structuring
# ─────────────────────────────────────────────────────────────────────────────

async def _structure_with_gemini(content: str, city: str) -> Dict[str, Any]:
    """Use Gemini Flash to structure raw grievance text."""
    if not settings.GEMINI_API_KEY:
        logger.info("GEMINI_API_KEY not set — skipping AI structuring")
        return {}

    prompt = STRUCTURING_PROMPT.format(city=city, content=content[:800])

    try:
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 1024,
                "responseMimeType": "application/json",
            },
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{GEMINI_API_URL}?key={settings.GEMINI_API_KEY}",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()

        candidates = data.get("candidates", [])
        if not candidates:
            return {}

        raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        return _parse_json(raw_text)

    except Exception as e:
        logger.error("Gemini structuring failed: %s", e)
        return {}


def _parse_json(raw: str) -> Dict[str, Any]:
    """Parse JSON from Gemini response, handling markdown code blocks."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        result = json.loads(text)
        return result if isinstance(result, dict) else {}
    except json.JSONDecodeError:
        # Try to find JSON object in text
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return {}


# ─────────────────────────────────────────────────────────────────────────────
# Severity helpers
# ─────────────────────────────────────────────────────────────────────────────

def _keyword_severity(text: str) -> Tuple[str, float]:
    """Fast keyword-based severity scoring."""
    text_lower = text.lower()
    for severity, keywords in SEVERITY_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            scores = {"critical": 0.95, "high": 0.75, "medium": 0.5}
            return severity, scores[severity]
    return "low", 0.2


def _score_to_severity(score: float) -> str:
    if score >= 0.85:
        return "critical"
    elif score >= 0.7:
        return "high"
    elif score >= 0.4:
        return "medium"
    return "low"


def _compute_source_id(item: ScrapedItem) -> str:
    """Deterministic ID for dedup based on platform + URL + content hash."""
    raw = f"{item.platform}:{item.source_url}:{item.content[:200]}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ─────────────────────────────────────────────────────────────────────────────
# Auto-ticket generation
# ─────────────────────────────────────────────────────────────────────────────

async def _create_ticket_from_grievance(grievance: GrievanceMongo):
    """Auto-create a TicketMongo from a high-severity grievance."""
    try:
        from app.services.ticket_service import TicketService
        from app.enums import TicketSource

        # Map platform to ticket source
        source_map = {
            "twitter": TicketSource.TWITTER,
            "cpgrams": TicketSource.CPGRAMS,
            "civic": TicketSource.SOCIAL_MEDIA,
            "news": TicketSource.NEWS,
            "reddit": TicketSource.SOCIAL_MEDIA,
            "municipal_portal": TicketSource.MUNICIPAL_PORTAL,
        }
        ticket_source = source_map.get(
            grievance.source_platform, TicketSource.SOCIAL_MEDIA
        )

        ticket = await TicketService.create_ticket(
            description=(
                f"[Auto-Ingested from {grievance.source_platform.upper()}] "
                f"{grievance.structured_summary or grievance.raw_content[:300]}"
            ),
            location_text=grievance.location_text or settings.CITY_NAME or "Chennai",
            reporter_phone="0000000000",  # auto-generated, no real phone
            consent_given=True,  # public data
            reporter_name=f"Auto-Ingested ({grievance.source_platform})",
            source=ticket_source,
            ward_id=grievance.ward_id,
        )
        logger.info(
            "Auto-created ticket %s from %s grievance (severity=%s, score=%.2f)",
            ticket.ticket_code, grievance.source_platform,
            grievance.severity, grievance.severity_score,
        )
        return ticket

    except Exception as e:
        logger.error("Failed to auto-create ticket from grievance: %s", e)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Stats helpers (for API/dashboard)
# ─────────────────────────────────────────────────────────────────────────────

async def get_grievance_stats(ward_id: Optional[int] = None) -> Dict[str, Any]:
    """Aggregate stats for the grievance dashboard."""
    query = []
    if ward_id is not None:
        query.append(GrievanceMongo.ward_id == ward_id)

    total = await GrievanceMongo.find(*query).count()
    auto_ticketed = await GrievanceMongo.find(
        *query, GrievanceMongo.auto_ticket_generated == True  # noqa: E712
    ).count()
    pending = await GrievanceMongo.find(
        *query, GrievanceMongo.status == "pending"
    ).count()

    # Severity breakdown
    severity_counts = {}
    for sev in ["critical", "high", "medium", "low"]:
        severity_counts[sev] = await GrievanceMongo.find(
            *query, GrievanceMongo.severity == sev
        ).count()

    # Platform breakdown
    all_grievances = await GrievanceMongo.find(*query).to_list()
    platform_counts: Dict[str, int] = {}
    for g in all_grievances:
        platform_counts[g.source_platform] = platform_counts.get(g.source_platform, 0) + 1

    # Last scrape time
    last = await GrievanceMongo.find(*query).sort(-GrievanceMongo.ingested_at).first_or_none()

    return {
        "total": total,
        "auto_ticketed": auto_ticketed,
        "pending_review": pending,
        "severity": severity_counts,
        "by_platform": platform_counts,
        "last_ingested_at": last.ingested_at.isoformat() if last else None,
        "ward_id": ward_id,
    }
