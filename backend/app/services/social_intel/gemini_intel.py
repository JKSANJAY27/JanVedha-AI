"""
Gemini Intelligence Engine — JanVedha AI
Core AI module for the Social Intelligence feature.

Responsibilities:
  1. fetch_gemini_civic_issues()  — generate ward-specific civic issues from Gemini's knowledge
  2. filter_and_structure_articles() — filter NewsAPI articles for relevance + enrich with AI
  3. generate_ward_sentiment()    — AI-powered sentiment analysis of stored posts
  4. generate_emerging_issues()   — AI-powered emerging issue clusters from stored posts
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

import httpx

from app.core.config import settings
from app.services.scrapers.base import ScrapedItem

logger = logging.getLogger("gemini_intel")

GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash:generateContent"
)

# ─────────────────────────────────────────────────────────────────────────────
# Internal Gemini call helper
# ─────────────────────────────────────────────────────────────────────────────

async def _call_gemini(
    prompt: str,
    system_prompt: str,
    temperature: float = 0.15,
    max_tokens: int = 4096,
) -> Optional[str]:
    """Call Gemini and return the raw text response."""
    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set — skipping AI call")
        return None

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            # NOTE: do NOT set responseMimeType — it causes Gemini to silently
            # truncate JSON at the token boundary, producing invalid JSON.
            # We extract JSON from the text response ourselves.
        },
    }

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                f"{GEMINI_API_URL}?key={settings.GEMINI_API_KEY}",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
    except httpx.TimeoutException:
        logger.error("Gemini API timed out")
    except Exception as e:
        logger.error("Gemini API call failed: %s", e)
    return None


def _extract_json(text: str) -> str:
    """
    Robustly extract JSON from a Gemini text response.
    Handles: markdown code fences, leading/trailing prose, partial JSON.
    """
    if not text:
        return text

    # Strip markdown code fences: ```json ... ``` or ``` ... ```
    import re
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fenced:
        return fenced.group(1).strip()

    # Try to find the first JSON array or object
    text = text.strip()
    for start_char, end_char in [("[", "]"), ("{", "}")]:
        start = text.find(start_char)
        if start != -1:
            # Find the matching closing bracket by counting depth
            depth = 0
            end = -1
            in_string = False
            escape_next = False
            for i, ch in enumerate(text[start:], start):
                if escape_next:
                    escape_next = False
                    continue
                if ch == "\\" and in_string:
                    escape_next = True
                    continue
                if ch == '"' and not escape_next:
                    in_string = not in_string
                if in_string:
                    continue
                if ch == start_char:
                    depth += 1
                elif ch == end_char:
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            if end != -1:
                return text[start:end]

    return text


# ─────────────────────────────────────────────────────────────────────────────
# 1. Fetch civic issues from Gemini's own knowledge
# ─────────────────────────────────────────────────────────────────────────────

CIVIC_KNOWLEDGE_SYSTEM = """You are an expert on Indian municipal governance, specifically Tamil Nadu.
You have deep knowledge of civic issues, infrastructure problems, and citizen complaints
across Chennai and other Tamil Nadu cities. Provide accurate, realistic civic issue data.
Respond ONLY with valid JSON. No markdown, no explanation."""

async def fetch_gemini_civic_issues(
    ward_id: Optional[int],
    city: str = "Chennai",
    area: str = "",
    count: int = 8,
) -> List[ScrapedItem]:
    """
    Ask Gemini to generate realistic civic issue reports for the given ward/area
    based on its training knowledge of Tamil Nadu civic conditions.
    Returns a list of ScrapedItems (platform='gemini_ai').
    """
    location = area if area else city
    prompt = f"""Generate {count} realistic civic issue reports for {location}, Tamil Nadu, India.
These should reflect ACTUAL common problems in this area based on your knowledge.

For each issue, provide a JSON object with:
- "title": short headline (max 80 chars)
- "description": detailed description of the civic issue (2-3 sentences, realistic)
- "category": one of [Infrastructure, Water Supply, Sanitation, Electricity, Public Safety, Health, Transport, Environment, Governance]
- "urgency": one of [critical, high, medium, low]
- "sentiment": one of [negative, neutral, positive]
- "location": specific street/area name within {location}
- "action_needed": one concrete action the councillor/municipality should take

Focus on REAL, COMMON issues in Tamil Nadu such as:
- Pothole-riddled roads after monsoon
- Borewell/water supply failures
- Garbage collection delays
- Street light outages
- Open drain overflow
- Encroachment on footpaths
- Sewage leakage near residential areas

Return a JSON array of exactly {count} objects. No markdown."""

    text = await _call_gemini(prompt, CIVIC_KNOWLEDGE_SYSTEM, temperature=0.3)
    if not text:
        return []

    items: List[ScrapedItem] = []
    try:
        parsed = json.loads(_extract_json(text))
        if not isinstance(parsed, list):
            parsed = parsed.get("issues", []) or []

        for entry in parsed:
            if not isinstance(entry, dict):
                continue
            title = entry.get("title", "")
            description = entry.get("description", "")
            content = f"{title}\n\n{description}".strip()
            if not content:
                continue

            # Construct a Google News search URL so the post is clickable
            import urllib.parse as _urlparse
            search_q = _urlparse.quote_plus(f"India {entry.get('category', '')} {title}")
            google_news_url = (
                f"https://news.google.com/search?q={search_q}&hl=en-IN&gl=IN&ceid=IN:en"
            )

            items.append(ScrapedItem(
                platform="gemini_ai",
                author="Gemini AI",
                content=content,
                source_url=google_news_url,
                post_timestamp=datetime.now(timezone.utc),
                keywords=["ai_generated", location.lower()],
                category=entry.get("category"),
                urgency=entry.get("urgency"),
                sentiment=entry.get("sentiment"),
                summary=title[:80],
                action_needed=entry.get("action_needed"),
                location=entry.get("location", location),
                metadata={
                    "source": "gemini_knowledge",
                    "generated_for": location,
                    "ward_id": ward_id,
                    "search_url": google_news_url,
                },
            ))

    except (json.JSONDecodeError, KeyError) as e:
        logger.error("Failed to parse Gemini civic issues response: %s", e)

    logger.info("Gemini generated %d civic issue items for %s", len(items), location)
    return items


# ─────────────────────────────────────────────────────────────────────────────
# 2. Filter & structure NewsAPI articles through Gemini
# ─────────────────────────────────────────────────────────────────────────────

ARTICLE_FILTER_SYSTEM = """You are a civic intelligence analyst for Tamil Nadu municipal governance.
Your job is to review news articles and determine which ones are genuinely relevant to
local civic issues (infrastructure, water, roads, sanitation, electricity, public safety).
You extract structured information from relevant articles and discard irrelevant ones.
Respond ONLY with valid JSON. No markdown, no explanation."""

async def filter_and_structure_articles(
    articles: List[ScrapedItem],
    ward_id: Optional[int],
    city: str = "Chennai",
    area: str = "",
) -> List[ScrapedItem]:
    """
    Pass raw NewsAPI articles through Gemini for:
    1. Relevance filtering (score 0-1, keep >= 0.5)
    2. Category/urgency/sentiment extraction
    3. Summary generation
    
    Returns only the relevant, enriched articles.
    """
    if not articles or not settings.GEMINI_API_KEY:
        return articles

    location = area if area else city

    # Process in batches of 8 to stay within token limits
    batch_size = 8
    enriched: List[ScrapedItem] = []

    for i in range(0, len(articles), batch_size):
        batch = articles[i:i + batch_size]
        articles_text = "\n\n---\n\n".join(
            f"Article {j+1}:\nSource: {item.author or 'Unknown'}\n"
            f"URL: {item.source_url}\n"
            f"Content: {item.content[:500]}"
            for j, item in enumerate(batch)
        )

        prompt = f"""Review these {len(batch)} news articles and extract structured information.
We are building a civic intelligence dashboard for Indian municipal governance.

For each article, return a JSON object with:
- "index": article number (1-based)
- "relevance_score": float 0.0-1.0
  - 0.9+ = directly about a civic complaint, infrastructure failure, or public service issue in India
  - 0.7 = about Indian municipal governance, urban issues, public works, sanitation, transport
  - 0.5 = broadly about Indian infrastructure, civic policy, or public services
  - 0.3 = tangentially related (regional/national policy that affects civic life)
  - 0.1 = clearly irrelevant (entertainment, sports, finance, foreign news only)
- "keep": true if relevance_score >= 0.25, false only for clearly off-topic articles
- "category": one of [Infrastructure, Water Supply, Sanitation, Electricity, Public Safety, Health, Transport, Environment, Governance, Other]
- "urgency": one of [critical, high, medium, low]
- "sentiment": one of [negative, neutral, positive]
- "summary": ONE sentence (max 90 chars) describing the issue for a councillor
- "action_needed": what municipal action is needed (or null)
- "gemini_insight": very brief context (1 short sentence) about why this matters locally

Be GENEROUS with keeping articles. If the article is about ANY Indian city's civic issues,
urban challenges, infrastructure, public services, or government accountability — keep it.
Only reject clearly unrelated content (entertainment, sports, pure business/markets, foreign-only news).

Articles:
{articles_text}

Return a JSON array of {len(batch)} objects."""

        text = await _call_gemini(prompt, ARTICLE_FILTER_SYSTEM, temperature=0.1, max_tokens=3000)
        if not text:
            # On failure, pass through all articles unfiltered
            enriched.extend(batch)
            continue

        try:
            parsed = json.loads(_extract_json(text))
            if not isinstance(parsed, list):
                parsed = parsed.get("articles", []) or []

            for result in parsed:
                if not isinstance(result, dict):
                    continue
                idx = result.get("index", 1) - 1
                if idx < 0 or idx >= len(batch):
                    continue

                item = batch[idx]
                relevance = result.get("relevance_score", 0.0)
                keep = result.get("keep", relevance >= 0.25)

                if not keep or relevance < 0.25:
                    continue

                # Enrich the item with Gemini analysis
                item.category = result.get("category") or item.category
                item.urgency = result.get("urgency") or item.urgency
                item.sentiment = result.get("sentiment") or item.sentiment
                item.summary = result.get("summary") or item.summary
                item.action_needed = result.get("action_needed") or item.action_needed
                item.metadata["relevance_score"] = relevance
                item.metadata["gemini_insight"] = result.get("gemini_insight", "")
                enriched.append(item)

        except (json.JSONDecodeError, KeyError) as e:
            logger.error("Failed to parse Gemini filter response: %s", e)
            # Fallback: include all in batch
            enriched.extend(batch)

    logger.info(
        "Gemini filter: %d/%d articles kept as relevant",
        len(enriched), len(articles)
    )
    return enriched


# ─────────────────────────────────────────────────────────────────────────────
# 3. Generate ward sentiment analysis
# ─────────────────────────────────────────────────────────────────────────────

SENTIMENT_SYSTEM = """You are a ward sentiment analyst for Indian local governance.
You analyze collections of civic news articles and AI-generated issue reports
to produce a nuanced, accurate sentiment assessment for a municipal ward.
Respond ONLY with valid JSON. No markdown, no explanation."""

async def generate_ward_sentiment(
    posts_data: List[Dict[str, Any]],
    ward_area: str = "Chennai",
    ward_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Use Gemini to produce a sophisticated ward sentiment analysis from stored posts.
    
    Returns dict with: score, label, narrative, positive, neutral, negative, top_concerns
    """
    if not posts_data or not settings.GEMINI_API_KEY:
        return _fallback_sentiment(posts_data)

    # Build a structured summary of posts for analysis
    post_summaries = []
    for p in posts_data[:40]:  # Limit to 40 most recent posts
        summary_line = (
            f"[{p.get('platform', '?')}] "
            f"Category: {p.get('category', 'Unknown')} | "
            f"Urgency: {p.get('urgency', 'unknown')} | "
            f"Sentiment: {p.get('sentiment', 'unknown')} | "
            f"{p.get('summary') or p.get('content', '')[:100]}"
        )
        post_summaries.append(summary_line)

    posts_text = "\n".join(post_summaries)

    # Count raw sentiments for context
    raw_counts = {"positive": 0, "neutral": 0, "negative": 0}
    for p in posts_data:
        s = (p.get("sentiment") or "neutral").lower()
        if s in raw_counts:
            raw_counts[s] += 1

    total = len(posts_data)

    prompt = f"""Analyze the following {total} civic posts/articles from {ward_area}, Tamil Nadu.
These posts were collected from news sources and AI analysis over the last 7 days.

Raw sentiment counts: {raw_counts['positive']} positive, {raw_counts['neutral']} neutral, {raw_counts['negative']} negative

Posts summary:
{posts_text}

Provide a comprehensive ward sentiment analysis. Return a JSON object with:
- "score": float from -1.0 (very negative) to +1.0 (very positive)
  Based on severity, urgency, and breadth of issues. NOT just a simple ratio.
  Weight critical/high urgency negative posts more heavily.
- "label": one of ["Very Negative", "Negative", "Cautious", "Mixed", "Stable", "Positive", "Very Positive"]
- "narrative": 2-3 sentences describing the current civic mood in {ward_area}.
  Mention specific dominant issues. Be specific, actionable, and accurate.
  Write as if briefing a councillor. Example: "Ward sentiment is cautious this week.
  Residents are expressing frustration over prolonged water supply disruptions and 
  road damage following recent rains. Immediate action on borewells and pothole 
  repairs would significantly improve public perception."
- "positive": integer count of positive signals
- "neutral": integer count of neutral signals  
- "negative": integer count of negative signals
- "top_concerns": list of 3 main civic concerns as short strings (e.g. ["Water Supply", "Road Damage", "Garbage"])

Be specific, grounded, and accurate. Do not be overly optimistic if issues are severe."""

    text = await _call_gemini(prompt, SENTIMENT_SYSTEM, temperature=0.2, max_tokens=2048)
    if not text:
        return _fallback_sentiment(posts_data)

    try:
        result = json.loads(_extract_json(text))
        if not isinstance(result, dict):
            return _fallback_sentiment(posts_data)

        return {
            "total": total,
            "positive": result.get("positive", raw_counts["positive"]),
            "neutral": result.get("neutral", raw_counts["neutral"]),
            "negative": result.get("negative", raw_counts["negative"]),
            "score": float(result.get("score", 0.0)),
            "label": result.get("label", "Mixed"),
            "narrative": result.get("narrative", ""),
            "top_concerns": result.get("top_concerns", []),
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "ai_powered": True,
        }
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.error("Failed to parse Gemini sentiment response: %s", e)
        return _fallback_sentiment(posts_data)


def _fallback_sentiment(posts_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Simple count-based fallback when Gemini is unavailable."""
    counts = {"positive": 0, "neutral": 0, "negative": 0}
    for p in posts_data:
        s = (p.get("sentiment") or "neutral").lower()
        counts[s] = counts.get(s, 0) + 1
    total = len(posts_data)
    score = round((counts["positive"] - counts["negative"]) / max(total, 1), 2)
    return {
        "total": total,
        "positive": counts["positive"],
        "neutral": counts["neutral"],
        "negative": counts["negative"],
        "score": score,
        "label": "Mixed",
        "narrative": "",
        "top_concerns": [],
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "ai_powered": False,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. Generate emerging issues from stored posts
# ─────────────────────────────────────────────────────────────────────────────

EMERGING_SYSTEM = """You are a civic issue pattern analyst for Indian local governance.
You identify emerging civic issue clusters from collections of news articles and reports.
Your analysis should be specific, actionable, and ground-truthed in real Tamil Nadu conditions.
Respond ONLY with valid JSON. No markdown, no explanation."""

async def generate_emerging_issues(
    posts_data: List[Dict[str, Any]],
    ward_area: str = "Chennai",
    limit: int = 6,
) -> List[Dict[str, Any]]:
    """
    Use Gemini to identify and rank emerging civic issue clusters from stored posts.
    
    Returns list of issues with: category, urgency, headline, count, insight, source_urls
    """
    if not posts_data:
        return []

    if not settings.GEMINI_API_KEY:
        return _fallback_emerging_issues(posts_data, limit)

    # Build concise post summaries
    post_lines = []
    source_map: Dict[str, List[str]] = {}  # category → URLs

    for p in posts_data[:60]:  # Cap at 60 posts
        category = p.get("category", "Other")
        source_url = p.get("source_url", "")
        summary = p.get("summary") or p.get("content", "")[:120]
        urgency = p.get("urgency", "unknown")
        platform = p.get("platform", "?")

        post_lines.append(
            f"[{platform}] [{category}] [{urgency}] {summary}"
        )
        if source_url and source_url.startswith("http"):
            source_map.setdefault(category, [])
            if source_url not in source_map[category]:
                source_map[category].append(source_url)

    posts_text = "\n".join(post_lines)

    prompt = f"""Analyze these {len(posts_data)} civic posts/articles from {ward_area}, Tamil Nadu (last 72 hours).
Identify the top {limit} EMERGING civic issue clusters that councillors and municipal officers should prioritize.

Posts:
{posts_text}

For each emerging issue, return a JSON object with:
- "category": civic category name (specific is better, e.g. "Road Flooding" not just "Infrastructure")
- "urgency": highest urgency level seen [critical, high, medium, low]
- "headline": one punchy sentence describing the emerging issue (max 90 chars)
- "count": estimated number of posts/signals related to this issue
- "insight": 1-2 sentences of Gemini's analysis — WHY is this emerging, what's the root cause,
  what will happen if unaddressed? Be specific to Tamil Nadu civic context.
- "recommended_action": the single most important action to take (1 short sentence)
- "trend": one of ["spike", "steady", "first_reported"]

Rank by combination of: urgency + count + potential civic impact.
Only include genuinely emerging or significant issues, not minor or one-off complaints.

Return a JSON array of up to {limit} objects, ranked by priority (most urgent first)."""

    text = await _call_gemini(prompt, EMERGING_SYSTEM, temperature=0.2, max_tokens=3000)
    if not text:
        return _fallback_emerging_issues(posts_data, limit)

    try:
        parsed = json.loads(_extract_json(text))
        if not isinstance(parsed, list):
            parsed = parsed.get("issues", []) or []

        result = []
        for issue in parsed[:limit]:
            if not isinstance(issue, dict):
                continue
            category = issue.get("category", "Other")
            result.append({
                "category": category,
                "urgency": issue.get("urgency", "medium"),
                "headline": issue.get("headline", ""),
                "count": issue.get("count", 1),
                "insight": issue.get("insight", ""),
                "recommended_action": issue.get("recommended_action", ""),
                "trend": issue.get("trend", "steady"),
                "negative_count": issue.get("count", 1),  # for frontend compatibility
                "max_urgency": issue.get("urgency", "medium"),
                "sample_summary": issue.get("headline", ""),
                "platforms": ["news"],
                "source_urls": source_map.get(category, [])[:3],
                "ai_powered": True,
            })
        return result

    except (json.JSONDecodeError, KeyError) as e:
        logger.error("Failed to parse Gemini emerging issues response: %s", e)
        return _fallback_emerging_issues(posts_data, limit)


def _fallback_emerging_issues(
    posts_data: List[Dict[str, Any]],
    limit: int,
) -> List[Dict[str, Any]]:
    """Category-count based fallback."""
    cat_map: Dict[str, Dict[str, Any]] = {}
    for p in posts_data:
        cat = p.get("category") or "Other"
        if cat not in cat_map:
            cat_map[cat] = {
                "category": cat,
                "count": 0,
                "negative_count": 0,
                "max_urgency": "low",
                "sample_summary": None,
                "platforms": set(),
                "headline": "",
                "insight": "",
                "recommended_action": "",
                "trend": "steady",
                "source_urls": [],
                "ai_powered": False,
            }
        cat_map[cat]["count"] += 1
        cat_map[cat]["platforms"].add(p.get("platform", "news"))
        if p.get("sentiment") == "negative":
            cat_map[cat]["negative_count"] += 1
        if not cat_map[cat]["sample_summary"] and p.get("summary"):
            cat_map[cat]["sample_summary"] = p["summary"]
            cat_map[cat]["headline"] = p["summary"]
        src = p.get("source_url", "")
        if src and src.startswith("http") and src not in cat_map[cat]["source_urls"]:
            cat_map[cat]["source_urls"].append(src)

    result = sorted(cat_map.values(), key=lambda x: x["count"], reverse=True)[:limit]
    for item in result:
        item["platforms"] = list(item["platforms"])
        item["max_urgency"] = item.get("max_urgency", "medium")
    return result
