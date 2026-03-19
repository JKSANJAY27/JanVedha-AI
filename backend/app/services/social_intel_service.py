"""
Social Intelligence Service — JanVedha AI
Orchestrates NewsAPI + Gemini AI scraping, filters and structures posts via Gemini,
persists to MongoDB SocialPostMongo, and provides AI-powered analytics queries.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any


from app.core.config import settings
from app.mongodb.models.social_post import SocialPostMongo
from app.services.scrapers.base import ScrapedItem

logger = logging.getLogger("social_intel")

# ── Ward → area name mapping ──────────────────────────────────────────────────
WARD_LOCATION_MAP: Dict[int, str] = {
    1: "Kathivakkam", 2: "Ennore", 3: "Ernavoor", 4: "Ajax",
    5: "Tiruvottiyur", 6: "Kaladipet", 7: "Rajakadai",
    8: "Kodungaiyur West", 9: "Kodungaiyur East", 15: "Edyanchavadi",
    18: "Manali", 19: "Mathur", 23: "Puzhal", 26: "Madhavaram",
    34: "Tondiarpet", 35: "New Washermenpet", 36: "Old Washermenpet",
    38: "Perambur", 39: "Vyasarpadi", 43: "George Town", 44: "Broadway",
    47: "Sowcarpet", 56: "Ayanavaram", 58: "Purasavakkam", 60: "Royapuram",
    61: "Anna Salai", 62: "Chepauk", 64: "Kolathur", 67: "Villivakkam",
    73: "Thiru Vi Ka Nagar", 75: "Otteri", 79: "Kilpauk", 88: "Ambattur",
    97: "Korattur", 106: "Anna Nagar West", 111: "Aminjikarai",
    114: "Chetpet", 115: "Egmore", 118: "Choolaimedu",
    127: "Choolaimedu", 128: "Chepauk", 129: "Nungambakkam",
    131: "Gopalapuram", 132: "Royapettah", 134: "Kodambakkam",
    135: "Triplicane", 136: "T Nagar", 137: "Mylapore",
    139: "Alwarpet", 140: "Nandanam", 141: "RA Puram",
    144: "West Mambalam", 145: "Koyambedu", 146: "Virugambakkam",
    150: "Vadapalani", 151: "KK Nagar", 152: "Ashok Nagar",
    156: "Mugdha Nagar", 160: "Alandur", 165: "Adambakkam",
    170: "Kotturpuram", 173: "Adyar", 175: "Adyar",
    176: "Besant Nagar", 178: "Thiruvanmiyur", 179: "Velachery",
    181: "Perungudi", 192: "Sholinganallur", 195: "Ullagaram",
    198: "Madipakkam",
}


# ─────────────────────────────────────────────────────────────────────────────
# Main scrape orchestrator
# ─────────────────────────────────────────────────────────────────────────────

CIVIC_KEYWORDS_CAT = {
    "Sanitation": ["garbage", "waste", "trash", "litter", "dump", "sewage", "drain", "gutter", "clean"],
    "Water Supply": ["water", "borewell", "pipeline", "tap", "supply", "drought", "shortage"],
    "Infrastructure": ["pothole", "road", "bridge", "footpath", "pavement", "repair", "construction"],
    "Electricity": ["power", "electricity", "outage", "blackout", "light", "streetlight", "transformer"],
    "Public Safety": ["encroach", "stray", "dog", "safety", "crime", "accident", "traffic"],
    "Health": ["mosquito", "disease", "dengue", "malaria", "hospital", "health", "sanit"],
    "Environment": ["flood", "waterlog", "pollution", "tree", "park", "green", "rain"],
    "Transport": ["bus", "metro", "auto", "taxi", "transport", "signal", "parking"],
}

URGENCY_KEYWORDS = {
    "critical": ["death", "flood", "collapse", "emergency", "crisis", "severe", "fatal"],
    "high": ["danger", "hazard", "outbreak", "urgent", "accident", "protest"],
    "medium": ["complain", "issue", "problem", "resident", "disruption"],
}

def _quick_tag(text: str) -> tuple[str, str, str]:
    """Rule-based category/urgency/sentiment from article text — no AI needed."""
    low = text.lower()
    cat = "Other"
    for c, kws in CIVIC_KEYWORDS_CAT.items():
        if any(k in low for k in kws):
            cat = c
            break
    urgency = "low"
    for u, kws in URGENCY_KEYWORDS.items():
        if any(k in low for k in kws):
            urgency = u
            break
    neg_words = ["problem", "fail", "broken", "dead", "crisis", "poor", "bad", "lack", "damage", "dirty"]
    pos_words = ["resolve", "fixed", "improve", "complete", "success", "award", "clean"]
    neg = sum(1 for w in neg_words if w in low)
    pos = sum(1 for w in pos_words if w in low)
    sentiment = "negative" if neg > pos else ("positive" if pos > neg else "neutral")
    return cat, urgency, sentiment


async def run_social_scrape(
    keywords: Optional[List[str]] = None,
    max_results: int = 25,
    ward_id: Optional[int] = None,
) -> int:
    """
    Scrape pipeline — FAST PATH (no Gemini filter gate):
    1. Fetch real news articles from NewsAPI.org  ← always runs first
    2. Save ALL NewsAPI articles directly to MongoDB with quick keyword tagging
    3. Generate 3 Gemini AI posts as supplemental context
    4. Returns count of new posts saved.
    """
    city = settings.DEMO_CITY or "Chennai"
    area = WARD_LOCATION_MAP.get(ward_id, "") if ward_id is not None else ""

    # ── Step 1: Fetch NewsAPI articles ──────────────────────────────────────
    newsapi_items: List[ScrapedItem] = []
    if settings.NEWS_API_KEY:
        from app.services.scrapers.newsapi import NewsApiScraper
        scraper = NewsApiScraper(settings)
        kw = [area] if area else []
        newsapi_items = await scraper.safe_scrape(kw, max_results=40)
        logger.info("NewsAPI fetched %d raw articles (key=%s...)", len(newsapi_items), settings.NEWS_API_KEY[:8])
    else:
        logger.error("NEWS_API_KEY is empty — NewsAPI scraper disabled!")

    # ── Step 2: Save ALL NewsAPI articles directly (no Gemini filter) ───────
    saved = 0
    dedup_window = datetime.utcnow() - timedelta(hours=48)

    for item in newsapi_items:
        try:
            if item.source_url:
                existing = await SocialPostMongo.find_one(
                    SocialPostMongo.source_url == item.source_url,
                    SocialPostMongo.scraped_at >= dedup_window,
                )
                if existing:
                    continue

            # Quick keyword-based tagging (no AI needed for this step)
            cat, urgency, sentiment = _quick_tag(item.content)

            # Extract a clean title/summary from the article title
            lines = item.content.split("\n")
            title_line = lines[0].strip() if lines else ""
            summary = title_line[:120] if title_line else item.content[:120]

            doc = SocialPostMongo(
                platform="news",
                source_url=item.source_url or "",
                author=item.author or item.metadata.get("source_name", "News"),
                content=item.content,
                location=area or city,
                ward_id=ward_id,
                category=item.category or cat,
                urgency=item.urgency or urgency,
                sentiment=item.sentiment or sentiment,
                summary=item.summary or summary,
                action_needed=item.action_needed,
                ai_generated=False,
                relevance_score=None,
                gemini_insight=None,
                keywords=item.keywords,
                post_timestamp=item.post_timestamp,
                metadata={
                    **item.metadata,
                    "source": "newsapi_org",
                    "title": item.metadata.get("title", title_line),
                },
            )
            await doc.insert()
            saved += 1
        except Exception as e:
            logger.error("Failed to save NewsAPI article: %s", e)

    logger.info("Saved %d new NewsAPI articles (ward=%s)", saved, ward_id)

    # ── Step 3: Add 3 Gemini AI posts as supplemental context ───────────────
    try:
        from app.services.social_intel.gemini_intel import fetch_gemini_civic_issues
        gemini_items = await fetch_gemini_civic_issues(ward_id=ward_id, city=city, area=area, count=3)
        for item in gemini_items:
            try:
                doc = SocialPostMongo(
                    platform="gemini_ai",
                    source_url=item.source_url or "",   # Google News search URL
                    author="Gemini AI",
                    content=item.content,
                    location=area or city,
                    ward_id=ward_id,
                    category=item.category,
                    urgency=item.urgency,
                    sentiment=item.sentiment,
                    summary=item.summary,
                    action_needed=item.action_needed,
                    ai_generated=True,
                    keywords=item.keywords,
                    post_timestamp=item.post_timestamp,
                    metadata=item.metadata,
                )
                await doc.insert()
                saved += 1
            except Exception as e:
                logger.error("Failed to save Gemini post: %s", e)
    except Exception as e:
        logger.error("Gemini civic issues fetch failed: %s", e)

    logger.info("Total saved this scrape: %d posts (ward=%s)", saved, ward_id)
    return saved


# ─────────────────────────────────────────────────────────────────────────────
# Analytics: Ward Sentiment (AI-powered)
# ─────────────────────────────────────────────────────────────────────────────

async def get_sentiment_overview(ward_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Return AI-powered sentiment analysis for the ward (last 7 days).
    Uses Gemini to produce a sentiment score, label, and narrative.
    Falls back to count-based if no AI key.
    """
    since = datetime.utcnow() - timedelta(days=7)
    query = [SocialPostMongo.scraped_at >= since]
    if ward_id is not None:
        query.append(SocialPostMongo.ward_id == ward_id)

    posts = await SocialPostMongo.find(*query).sort(-SocialPostMongo.scraped_at).to_list()

    if not posts:
        return {
            "total": 0, "positive": 0, "neutral": 0, "negative": 0,
            "score": 0.0, "label": "No Data",
            "narrative": "No civic signals have been collected yet. Click 'Refresh Data' to start.",
            "top_concerns": [],
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "ai_powered": False,
        }

    posts_data = [_post_to_dict(p) for p in posts]
    area = WARD_LOCATION_MAP.get(ward_id, settings.DEMO_CITY or "Chennai") if ward_id else (settings.DEMO_CITY or "Chennai")

    from app.services.social_intel.gemini_intel import generate_ward_sentiment
    return await generate_ward_sentiment(posts_data=posts_data, ward_area=area, ward_id=ward_id)


# ─────────────────────────────────────────────────────────────────────────────
# Analytics: Emerging Issues (AI-powered)
# ─────────────────────────────────────────────────────────────────────────────

async def get_emerging_issues(
    ward_id: Optional[int] = None,
    hours: int = 72,
    limit: int = 6,
) -> List[Dict[str, Any]]:
    """
    Return top emerging civic issue clusters from the last N hours.
    Uses Gemini to identify patterns and provide insights.
    """
    since = datetime.utcnow() - timedelta(hours=hours)
    query = [SocialPostMongo.scraped_at >= since]
    if ward_id is not None:
        query.append(SocialPostMongo.ward_id == ward_id)

    posts = await SocialPostMongo.find(*query).sort(-SocialPostMongo.scraped_at).to_list()

    if not posts:
        return []

    posts_data = [_post_to_dict(p) for p in posts]
    area = WARD_LOCATION_MAP.get(ward_id, settings.DEMO_CITY or "Chennai") if ward_id else (settings.DEMO_CITY or "Chennai")

    from app.services.social_intel.gemini_intel import generate_emerging_issues
    return await generate_emerging_issues(posts_data=posts_data, ward_area=area, limit=limit)


# ─────────────────────────────────────────────────────────────────────────────
# Analytics: Social Posts (paginated)
# ─────────────────────────────────────────────────────────────────────────────

async def get_social_posts(
    ward_id: Optional[int] = None,
    platform: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """Return paginated social posts, newest first."""
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


async def get_scrape_status(ward_id: Optional[int] = None) -> Dict[str, Any]:
    """Return last scrape time and post count for the given ward."""
    query = []
    if ward_id is not None:
        query.append(SocialPostMongo.ward_id == ward_id)

    total = await SocialPostMongo.find(*query).count()
    last_post = (
        await SocialPostMongo.find(*query)
        .sort(-SocialPostMongo.scraped_at)
        .first_or_none()
    )
    return {
        "total_posts": total,
        "last_scraped_at": last_post.scraped_at.isoformat() if last_post and last_post.scraped_at else None,
        "ward_id": ward_id,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

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
        "action_needed": p.action_needed,
        "gemini_insight": p.gemini_insight,
        "ai_generated": p.ai_generated,
        "relevance_score": p.relevance_score,
        "keywords": p.keywords,
        "scraped_at": p.scraped_at.isoformat() if p.scraped_at else None,
        "post_timestamp": p.post_timestamp.isoformat() if p.post_timestamp else None,
    }
