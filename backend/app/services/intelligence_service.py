"""
Intelligence Service — AI-powered insights for councillors (Pillar 1).
Provides:
1. Ward Reality Briefing (Daily narrative generation)
2. Root Cause Radar (Issue clustering & summarization)
3. Predictive Workload Alerts (Seasonal predictions)

CACHING STRATEGY:
- Every method checks MongoDB (WardIntelligenceCache) first.
- If a cached result exists and `refresh=False`, it is returned immediately.
- If `refresh=True` (or no cache exists), Gemini is called and the result is
  persisted to MongoDB, overwriting any previous cached entry.
- This means Gemini is NEVER called automatically on dashboard load — only when
  the user explicitly clicks "Refresh".
"""
from __future__ import annotations

import math
import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from app.mongodb.database import get_motor_client
from app.core.config import settings

logger = logging.getLogger("intelligence")


# ── Haversine Distance Helper ────────────────────────────────────────────────

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in meters using Haversine formula."""
    R = 6371000  # Radius of Earth in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0)**2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _get_tickets_collection():
    """Get the raw Motor tickets collection."""
    client = get_motor_client()
    uri = settings.MONGODB_URI
    db_name = uri.rsplit("/", 1)[-1].split("?")[0] or "civicai"
    if not db_name or db_name.startswith("mongodb"):
        db_name = "civicai"
    return client[db_name]["tickets"]


async def _call_gemini(prompt: str, fallback: str) -> str:
    """Call Gemini API with the given prompt. Returns fallback on error."""
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.3,
        )
        resp = await llm.ainvoke([("user", prompt)])
        return resp.content.strip()
    except Exception as e:
        logger.error(f"Gemini call failed: {e}")
        return fallback


# ── Cache helpers ────────────────────────────────────────────────────────────

async def _get_cache(ward_id: int, cache_type: str):
    """Return the WardIntelligenceCache document or None."""
    try:
        from app.mongodb.models.ward_intelligence_cache import WardIntelligenceCache
        return await WardIntelligenceCache.find_one(
            WardIntelligenceCache.ward_id == ward_id,
            WardIntelligenceCache.cache_type == cache_type,
        )
    except Exception as e:
        logger.warning(f"Cache read failed ({cache_type}, ward {ward_id}): {e}")
        return None


async def _save_cache(ward_id: int, cache_type: str, **fields) -> None:
    """Upsert a WardIntelligenceCache document."""
    try:
        from app.mongodb.models.ward_intelligence_cache import WardIntelligenceCache
        existing = await WardIntelligenceCache.find_one(
            WardIntelligenceCache.ward_id == ward_id,
            WardIntelligenceCache.cache_type == cache_type,
        )
        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
            existing.computed_at = datetime.utcnow()
            existing.is_stale = False
            await existing.save()
        else:
            doc = WardIntelligenceCache(
                ward_id=ward_id,
                cache_type=cache_type,
                computed_at=datetime.utcnow(),
                **fields,
            )
            await doc.insert()
    except Exception as e:
        logger.warning(f"Cache save failed ({cache_type}, ward {ward_id}): {e}")


# ── IntelligenceService ──────────────────────────────────────────────────────

class IntelligenceService:

    @staticmethod
    async def get_ward_briefing(ward_id: int, refresh: bool = False) -> str:
        """
        Returns the AI Morning Briefing for a ward.
        - Reads from MongoDB cache unless refresh=True.
        - On refresh, calls Gemini and persists the result.
        """
        if not refresh:
            cached = await _get_cache(ward_id, "briefing")
            if cached and cached.briefing:
                logger.info(f"Cache HIT: briefing ward={ward_id}")
                return cached.briefing

        # ── Build data for the prompt ────────────────────────────────────────
        col = _get_tickets_collection()
        now = datetime.utcnow()
        yesterday = now - timedelta(days=1)
        last_week = now - timedelta(days=7)

        recent_tickets = await col.find(
            {"ward_id": ward_id, "created_at": {"$gte": yesterday}}
        ).to_list(length=1000)

        weekly_tickets = await col.find(
            {"ward_id": ward_id, "created_at": {"$gte": last_week}}
        ).to_list(length=1000)

        recent_count = len(recent_tickets)
        weekly_count = len(weekly_tickets)

        issue_categories: Counter = Counter()
        open_count = 0
        overdue_count = 0
        for t in weekly_tickets:
            cat = t.get("issue_category") or "General"
            issue_categories[cat] += 1
            if t.get("status") in ("OPEN", "ASSIGNED", "IN_PROGRESS"):
                open_count += 1
            if t.get("sla_deadline") and t.get("status") not in ("CLOSED", "CLOSED_UNVERIFIED") and t["sla_deadline"] < now:
                overdue_count += 1

        top_issues = issue_categories.most_common(3)
        top_issues_str = ", ".join([f"{count}x {cat}" for cat, count in top_issues]) or "no issues"

        sentiment_desc = "neutral"
        try:
            from app.services.social_intel_service import get_sentiment_overview
            sentiment = await get_sentiment_overview(ward_id=ward_id)
            score = sentiment.get("score", 0)
            if score < -0.2:
                sentiment_desc = f"negative (score: {score:.2f})"
            elif score > 0.2:
                sentiment_desc = f"positive (score: {score:.2f})"
        except Exception:
            pass

        prompt = f"""You are an elite governance analyst writing a morning brief for the municipal Councillor of Ward {ward_id}.
Write a concise, exactly 5-sentence paragraph.

Data for this brief:
- New issues in the last 24 hours: {recent_count}
- Total issues this week: {weekly_count} ({open_count} still open, {overdue_count} overdue)
- Top recurring categories this week: {top_issues_str}
- Citizen sentiment on social media: {sentiment_desc}

Guidelines:
- Start with "Good morning."
- Sentence 1: State last night's new issue count.
- Sentence 2: Highlight the top recurring issue category and speculate on root cause if count is high (e.g. structural, seasonal).
- Sentence 3: Describe citizen sentiment and whether it improved or worsened.
- Sentence 4: Note how many tickets are overdue and the urgency.
- Sentence 5: Give 1-2 urgent recommended actions for today.
- Write as one solid paragraph. NO bullet points.
"""

        fallback = (
            f"Good morning. Ward {ward_id} received {recent_count} new civic complaints in the last 24 hours, "
            f"with {weekly_count} total issues this week. "
            f"The top recurring categories are {top_issues_str}. "
            f"Citizen sentiment is currently {sentiment_desc}. "
            f"There are {overdue_count} overdue tickets — prioritise these for immediate follow-up today."
        )

        result = await _call_gemini(prompt, fallback)

        # ── Persist to cache ─────────────────────────────────────────────────
        await _save_cache(ward_id, "briefing", briefing=result)

        return result

    @staticmethod
    async def get_root_cause_radar(ward_id: int, refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Clusters recent tickets geographically and by category to find systemic issues.
        - Reads from MongoDB cache unless refresh=True.
        - On refresh, calls Gemini (once per cluster, up to 5) and persists.
        """
        if not refresh:
            cached = await _get_cache(ward_id, "root_causes")
            if cached and cached.root_causes is not None:
                logger.info(f"Cache HIT: root_causes ward={ward_id}")
                return cached.root_causes

        # ── Build clusters ───────────────────────────────────────────────────
        col = _get_tickets_collection()
        since = datetime.utcnow() - timedelta(days=30)

        raw_tickets = await col.find(
            {
                "ward_id": ward_id,
                "created_at": {"$gte": since},
                "location.coordinates": {"$exists": True},
                "issue_category": {"$exists": True, "$ne": None},
            }
        ).to_list(length=500)

        if not raw_tickets:
            raw_tickets = await col.find(
                {
                    "ward_id": ward_id,
                    "location.coordinates": {"$exists": True},
                    "issue_category": {"$exists": True, "$ne": None},
                }
            ).to_list(length=500)

        if not raw_tickets:
            await _save_cache(ward_id, "root_causes", root_causes=[])
            return []

        loc_tickets = []
        for t in raw_tickets:
            coords = t.get("location", {}).get("coordinates")
            if coords and len(coords) == 2:
                loc_tickets.append(t)

        if not loc_tickets:
            await _save_cache(ward_id, "root_causes", root_causes=[])
            return []

        DISTANCE_THRESHOLD_METERS = 400
        MIN_CLUSTER_SIZE = 3

        clusters: List[Dict] = []
        visited = set()

        for i, t1 in enumerate(loc_tickets):
            if i in visited:
                continue

            cluster_members = [t1]
            visited.add(i)
            lon1, lat1 = t1["location"]["coordinates"]
            cat = t1.get("issue_category")

            for j, t2 in enumerate(loc_tickets):
                if j in visited:
                    continue
                if t2.get("issue_category") != cat:
                    continue
                lon2, lat2 = t2["location"]["coordinates"]
                dist = haversine_distance(lat1, lon1, lat2, lon2)
                if dist <= DISTANCE_THRESHOLD_METERS:
                    cluster_members.append(t2)
                    visited.add(j)

            if len(cluster_members) >= MIN_CLUSTER_SIZE:
                clusters.append({
                    "category": cat,
                    "count": len(cluster_members),
                    "center": [lon1, lat1],
                    "tickets": [str(t.get("ticket_code", t.get("_id"))) for t in cluster_members],
                    "sample_descriptions": [
                        t.get("description", "")[:120] for t in cluster_members[:5]
                    ]
                })

        clusters = sorted(clusters, key=lambda c: c["count"], reverse=True)[:5]

        results = []
        for cluster in clusters:
            cat = cluster["category"]
            count = cluster["count"]
            desc_str = " | ".join(cluster["sample_descriptions"])

            prompt = f"""Analyze {count} civic complaints about "{cat}" clustered within a 400m radius.

Sample citizen descriptions: {desc_str}

Write a 2-sentence Root Cause Radar alert for a municipal councillor:
- Sentence 1: State the pattern factually and precisely.
- Sentence 2: Propose a specific physical root cause hypothesis (e.g. a collapsed drain, aging pipeline, broken road base — NOT just "many reports").

Keep it punchy and actionable."""

            fallback = f"{count} '{cat}' complaints are clustered in a tight geographic area — this likely points to a single systemic infrastructure failure rather than isolated incidents."

            insight = await _call_gemini(prompt, fallback)

            results.append({
                "category": cat,
                "ticket_count": count,
                "insight": insight,
                "center": cluster["center"],
                "ticket_codes": cluster["tickets"][:10],
            })

        # ── Persist to cache ─────────────────────────────────────────────────
        await _save_cache(ward_id, "root_causes", root_causes=results)

        return results

    @staticmethod
    async def get_predictive_alerts(ward_id: int, refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Uses historical monthly ticket counts to detect seasonal spikes.
        - Reads from MongoDB cache unless refresh=True.
        - On refresh, calls Gemini and persists.
        """
        if not refresh:
            cached = await _get_cache(ward_id, "predictions")
            if cached and cached.alerts is not None:
                logger.info(f"Cache HIT: predictions ward={ward_id}")
                return cached.alerts

        # ── Compute predictions ──────────────────────────────────────────────
        col = _get_tickets_collection()
        cutoff = datetime.utcnow() - timedelta(days=365 * 2)

        historical = await col.find(
            {
                "ward_id": ward_id,
                "created_at": {"$gte": cutoff},
            },
            {"issue_category": 1, "created_at": 1}
        ).to_list(length=5000)

        if not historical:
            await _save_cache(ward_id, "predictions", alerts=[])
            return []

        monthly_by_cat: Dict[str, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
        for t in historical:
            cat = t.get("issue_category")
            if not cat:
                continue
            created = t.get("created_at")
            if isinstance(created, datetime):
                month = created.month
                monthly_by_cat[cat][month] += 1

        current_month = datetime.utcnow().month
        alerts = []

        for cat, monthly_counts in monthly_by_cat.items():
            if len(monthly_counts) < 2:
                continue

            total = sum(monthly_counts.values())
            avg = total / 12
            this_month_count = monthly_counts.get(current_month, 0)

            if avg > 0 and this_month_count > avg * 1.5:
                spike_ratio = this_month_count / avg
                pct_increase = int((spike_ratio - 1) * 100)

                prompt = f"""Write a 2-sentence Predictive Workload Alert for a municipal planner.

Data: "{cat}" complaints have historically spiked {pct_increase}% above average in this month (month {current_month}), based on the last 2 years of data for Ward {ward_id}. Historical average: {avg:.0f}/month, this month's historical avg: {this_month_count}.

Sentence 1: State the prediction factually with the numbers.
Sentence 2: Give a concrete operational recommendation (e.g. pre-allocate staff, schedule inspections, stock materials).
Be concise and actionable."""

                fallback = (
                    f"Historical data shows '{cat}' complaints spike {pct_increase}% in this period for Ward {ward_id}. "
                    f"Recommend pre-allocating additional staff and reviewing known hotspots before incidence rises."
                )

                narrative = await _call_gemini(prompt, fallback)

                alerts.append({
                    "category": cat,
                    "predicted_increase_pct": pct_increase,
                    "historical_avg": round(avg, 1),
                    "this_month_historical": this_month_count,
                    "narrative": narrative,
                    "month": current_month,
                })

        alerts.sort(key=lambda a: a["predicted_increase_pct"], reverse=True)
        result = alerts[:5]

        # ── Persist to cache ─────────────────────────────────────────────────
        await _save_cache(ward_id, "predictions", alerts=result)

        return result
