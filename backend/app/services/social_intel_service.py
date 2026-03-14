"""
Social Intelligence Service — JanVedha AI
Orchestrates news/civic/reddit scrapers, structures posts via Gemini,
and persists to MongoDB SocialPostMongo collection.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

import httpx

from app.core.config import settings
from app.mongodb.models.social_post import SocialPostMongo
from app.services.scrapers.base import ScrapedItem

logger = logging.getLogger("social_intel")

# ── Governance keywords that work for Indian civic content ──────────────────
DEFAULT_KEYWORDS = [
    "pothole", "water supply", "garbage", "electricity",
    "sewage", "road repair", "street light", "civic complaint",
]

# ── Ward → area name mapping (matches frontend constants.ts WARD_NAMES) ───────
# Actual Chennai Corporation ward IDs → area names used across the project
WARD_LOCATION_MAP: Dict[int, str] = {
    1: "Kathivakkam",
    2: "Ennore",
    3: "Ernavoor",
    4: "Ajax",
    5: "Tiruvottiyur",
    6: "Kaladipet",
    7: "Rajakadai",
    8: "Kodungaiyur West",
    9: "Kodungaiyur East",
    15: "Edyanchavadi",
    18: "Manali",
    19: "Mathur",
    23: "Puzhal",
    26: "Madhavaram",
    34: "Tondiarpet",
    35: "New Washermenpet",
    36: "Old Washermenpet",
    38: "Perambur",
    39: "Vyasarpadi",
    43: "George Town",
    44: "Broadway",
    47: "Sowcarpet",
    56: "Ayanavaram",
    58: "Purasavakkam",
    60: "Royapuram",
    61: "Anna Salai",
    62: "Chepauk",
    64: "Kolathur",
    67: "Villivakkam",
    73: "Thiru Vi Ka Nagar",
    75: "Otteri",
    79: "Kilpauk",
    88: "Ambattur",
    97: "Korattur",
    106: "Anna Nagar West",
    111: "Aminjikarai",
    114: "Chetpet",
    115: "Egmore",
    118: "Choolaimedu",
    127: "Choolaimedu",
    128: "Chepauk",
    129: "Nungambakkam",
    131: "Gopalapuram",
    132: "Royapettah",
    134: "Kodambakkam",
    135: "Triplicane",
    136: "T Nagar",
    137: "Mylapore",
    139: "Alwarpet",
    140: "Nandanam",
    141: "RA Puram",
    144: "West Mambalam",
    145: "Koyambedu",
    146: "Virugambakkam",
    150: "Vadapalani",
    151: "KK Nagar",
    152: "Ashok Nagar",
    156: "Mugdha Nagar",
    160: "Alandur",
    165: "Adambakkam",
    170: "Kotturpuram",
    173: "Adyar",
    175: "Adyar",
    176: "Besant Nagar",
    178: "Thiruvanmiyur",
    179: "Velachery",
    181: "Perungudi",
    192: "Sholinganallur",
    195: "Ullagaram",
    198: "Madipakkam",
}

GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-1.5-flash:generateContent"
)

SYSTEM_PROMPT = """You are an AI governance analyst for Indian local governance.
Analyze citizen complaints and news articles. For each post extract JSON with:
category (one of: Infrastructure, Water Supply, Sanitation, Electricity, Public Safety, Health, Transport, Environment, Governance, Other),
urgency (critical/high/medium/low), sentiment (negative/neutral/positive),
summary (max 80 chars), action_needed (one sentence).
Respond ONLY with valid JSON array, no markdown."""


# ── Scraper factory ──────────────────────────────────────────────────────────

def _get_scrapers():
    """Return list of configured scraper instances."""
    scrapers = []
    from app.services.scrapers.news import NewsScraper
    scrapers.append(NewsScraper(settings))

    if settings.REDDIT_CLIENT_ID and settings.REDDIT_CLIENT_SECRET:
        from app.services.scrapers.reddit import RedditScraper
        scrapers.append(RedditScraper(settings))

    return scrapers


# ── City & ward keyword scoping ──────────────────────────────────────────────

def _scope_keywords(keywords: List[str], ward_id: Optional[int] = None) -> List[str]:
    """
    Build an optimized boolean query string for search APIs to avoid length limits
    and impossible AND conditions.
    Returns a single-element list so it works seamlessly with scraper interfaces.
    """
    city = settings.DEMO_CITY or "Chennai"
    area = WARD_LOCATION_MAP.get(ward_id, "") if ward_id is not None else ""

    # Condense categories into a short OR group to fit within API limits (e.g. Gnews 100 max)
    # Using the core root words
    civic_terms = '"pothole" OR "garbage" OR "water" OR "road" OR "sewage" OR "civic" OR "power"'
    
    if area:
        # Search for either the exact area, or the city, but prioritize matching area if possible
        # Actually simplest is just requiring the area name
        location = f'"{area}"'
    else:
        location = f'"{city}"'

    query = f'{location} AND ({civic_terms})'
    
    # Return as a 1-element list so " ".join(keywords) in scrapers just uses this query directly
    return [query]


# ── Gemini LLM structuring ───────────────────────────────────────────────────

async def _structure_batch(items: List[ScrapedItem]) -> List[ScrapedItem]:
    """Call Gemini to fill in category/urgency/sentiment/summary."""
    if not settings.GEMINI_API_KEY or not items:
        return items

    posts_text = "\n\n".join(
        f"Post {i+1} [{it.platform}]:\n{it.content[:400]}"
        for i, it in enumerate(items)
    )
    prompt = (
        f"Analyze each of the following {len(items)} citizen posts from {settings.DEMO_CITY}.\n"
        f"Return a JSON array of {len(items)} objects with: "
        "category, urgency, sentiment, summary, action_needed.\n\n"
        f"Posts:\n{posts_text}"
    )

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 2048,
            "responseMimeType": "application/json",
        },
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{GEMINI_API_URL}?key={settings.GEMINI_API_KEY}",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(text)

            if isinstance(parsed, list):
                for item, struct in zip(items, parsed):
                    if isinstance(struct, dict):
                        item.category = struct.get("category")
                        item.urgency = struct.get("urgency")
                        item.sentiment = struct.get("sentiment")
                        item.summary = struct.get("summary")
                        item.action_needed = struct.get("action_needed")
    except Exception as e:
        logger.error("Gemini structuring failed: %s", e)

    return items


# ── Main scrape orchestrator ─────────────────────────────────────────────────

async def run_social_scrape(
    keywords: Optional[List[str]] = None,
    max_results: int = 15,
    ward_id: Optional[int] = None,
) -> int:
    """
    Run all configured scrapers concurrently, structure via Gemini,
    and persist new posts to MongoDB.
    Returns count of new posts saved.
    """
    kw = _scope_keywords(keywords or DEFAULT_KEYWORDS, ward_id=ward_id)
    scrapers = _get_scrapers()

    if not scrapers:
        logger.warning("No scrapers are configured — skipping scrape")
        return 0

    tasks = [s.safe_scrape(kw, max_results) for s in scrapers]
    results = await asyncio.gather(*tasks)

    all_items: List[ScrapedItem] = []
    for batch in results:
        all_items.extend(batch)

    logger.info("Scraped %d total items from %d scrapers", len(all_items), len(scrapers))

    if not all_items:
        return 0

    # Structure in batches of 10
    for i in range(0, len(all_items), 10):
        await _structure_batch(all_items[i:i + 10])  # type: ignore

    # Persist to MongoDB (deduplicate by source_url + content hash)
    saved = 0
    for item in all_items:
        try:
            # Simple dedup: skip if same source_url was scraped in last 24h
            if item.source_url:
                since = datetime.now(timezone.utc) - timedelta(hours=24)
                existing = await SocialPostMongo.find_one(
                    SocialPostMongo.source_url == item.source_url,
                    SocialPostMongo.scraped_at >= since,
                )
                if existing:
                    continue

            doc = SocialPostMongo(
                platform=item.platform,
                source_url=item.source_url or "",
                author=item.author,
                content=item.content,
                location=item.location,
                latitude=item.latitude,
                longitude=item.longitude,
                ward_id=ward_id,
                category=item.category,
                subcategory=item.subcategory,
                urgency=item.urgency,
                sentiment=item.sentiment,
                summary=item.summary,
                action_needed=item.action_needed,
                keywords=item.keywords,
                post_timestamp=item.post_timestamp,
                metadata=item.metadata,
            )
            await doc.insert()
            saved += 1
        except Exception as e:
            logger.error("Failed to save social post: %s", e)

    logger.info("Saved %d new social posts to MongoDB", saved)
    return saved


# ── Analytics queries ────────────────────────────────────────────────────────

async def get_sentiment_overview(ward_id: Optional[int] = None) -> Dict[str, Any]:
    """Return sentiment counts for the last 7 days."""
    since = datetime.now(timezone.utc) - timedelta(days=7)
    query = [SocialPostMongo.scraped_at >= since]
    if ward_id is not None:
        query.append(SocialPostMongo.ward_id == ward_id)

    posts = await SocialPostMongo.find(*query).to_list()

    counts: Dict[str, int] = {"positive": 0, "neutral": 0, "negative": 0, "unknown": 0}
    for p in posts:
        s = (p.sentiment or "unknown").lower()
        counts[s] = counts.get(s, 0) + 1

    total = len(posts)
    return {
        "total": total,
        "positive": counts["positive"],
        "neutral": counts["neutral"],
        "negative": counts["negative"],
        "score": round(float((counts["positive"] - counts["negative"]) / max(total, 1)), 2),  # type: ignore
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


async def get_emerging_issues(
    ward_id: Optional[int] = None,
    hours: int = 24,
    limit: int = 8,
) -> List[Dict[str, Any]]:
    """Return top emerging civic issue categories from social media in last N hours."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    query = [SocialPostMongo.scraped_at >= since]
    if ward_id is not None:
        query.append(SocialPostMongo.ward_id == ward_id)

    posts = await SocialPostMongo.find(*query).to_list()

    # Count by category
    cat_map: Dict[str, Dict[str, Any]] = {}
    for p in posts:
        cat = p.category or "Other"
        if cat not in cat_map:
            cat_map[cat] = {
                "category": cat,
                "count": 0,
                "negative_count": 0,
                "max_urgency": "low",
                "platforms": set(),
                "sample_summary": None,
            }
        cat_map[cat]["count"] += 1
        cat_map[cat]["platforms"].add(p.platform)
        if p.sentiment == "negative":
            cat_map[cat]["negative_count"] += 1
        if p.urgency and _urgency_rank(p.urgency) > _urgency_rank(cat_map[cat]["max_urgency"]):
            cat_map[cat]["max_urgency"] = p.urgency
        if not cat_map[cat]["sample_summary"] and p.summary:
            cat_map[cat]["sample_summary"] = p.summary

    result = sorted(cat_map.values(), key=lambda x: x["count"], reverse=True)[:limit]  # type: ignore
    # Convert set to list for JSON serialisation
    for item in result:
        item["platforms"] = list(item["platforms"])

    return result


async def get_social_posts(
    ward_id: Optional[int] = None,
    platform: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """Paginated social posts, newest first."""
    query = []
    if ward_id is not None:
        query.append(SocialPostMongo.ward_id == ward_id)
    if platform:
        query.append(SocialPostMongo.platform == platform)

    total = await SocialPostMongo.find(*query).count()
    offset = (page - 1) * page_size
    posts = (
        await SocialPostMongo.find(*query)
        .sort(-SocialPostMongo.scraped_at)
        .skip(offset)
        .limit(page_size)
        .to_list()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "results": [_post_to_dict(p) for p in posts],
    }


async def get_platform_stats(ward_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Count posts per platform."""
    query = []
    if ward_id is not None:
        query.append(SocialPostMongo.ward_id == ward_id)

    posts = await SocialPostMongo.find(*query).to_list()
    platform_counts: Dict[str, int] = {}
    for p in posts:
        platform_counts[p.platform] = platform_counts.get(p.platform, 0) + 1

    return [
        {"platform": k, "count": v}
        for k, v in sorted(platform_counts.items(), key=lambda x: x[1], reverse=True)
    ]


# ── Helpers ──────────────────────────────────────────────────────────────────

def _urgency_rank(u: str) -> int:
    return {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(u.lower(), 0)


def _post_to_dict(p: SocialPostMongo) -> Dict[str, Any]:
    return {
        "id": str(p.id),
        "platform": p.platform,
        "source_url": p.source_url,
        "author": p.author,
        "content": p.content[:300],
        "location": p.location,
        "ward_id": p.ward_id,
        "category": p.category,
        "urgency": p.urgency,
        "sentiment": p.sentiment,
        "summary": p.summary,
        "keywords": p.keywords,
        "scraped_at": p.scraped_at.isoformat() if p.scraped_at else None,
        "post_timestamp": p.post_timestamp.isoformat() if p.post_timestamp else None,
    }
