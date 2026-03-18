"""
Infrastructure Opportunity Spotter — ward zone analysis and AI recommendations.
Feature 1: Grid-based zone scoring from complaint patterns.
Feature 2: Proposal generation endpoint is in proposals.py.
"""
from __future__ import annotations

import json
import math
import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from app.core.dependencies import get_current_user
from app.mongodb.models.user import UserMongo
from app.enums import UserRole
from app.mongodb.database import get_motor_client
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger("opportunity")

# ── In-memory cache ──────────────────────────────────────────────────────────
# keyed (ward_id, days) → {"data": ..., "expires_at": datetime}
_zone_cache: Dict[tuple, Dict] = {}


def _require_dev_access(current_user: UserMongo = Depends(get_current_user)) -> UserMongo:
    allowed = {UserRole.COUNCILLOR, UserRole.SUPERVISOR, UserRole.SUPER_ADMIN, "COMMISSIONER"}
    if current_user.role not in allowed:
        raise HTTPException(status_code=403, detail="Councillor/Commissioner access required")
    return current_user


def _get_tickets_col():
    client = get_motor_client()
    uri = settings.MONGODB_URI
    db_name = uri.rsplit("/", 1)[-1].split("?")[0] or "civicai"
    if not db_name or db_name.startswith("mongodb"):
        db_name = "civicai"
    return client[db_name]["tickets"]


# ── Category → Infrastructure mapping ────────────────────────────────────────
INFRA_MAP = {
    "roads": "Road resurfacing or pothole repair",
    "road": "Road resurfacing or pothole repair",
    "water": "Water pipeline repair or new connection",
    "lighting": "Streetlight installation or upgrade",
    "drainage": "Stormwater drain construction or desilting",
    "waste": "Waste collection point or bin placement",
    "other": "General civic infrastructure audit",
}


async def _call_gemini_json(prompt: str, fallback: Dict) -> Dict:
    """Call Gemini, expect a JSON response. Returns fallback on error."""
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.3,
        )
        resp = await llm.ainvoke([("user", prompt)])
        text = resp.content.strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
        return json.loads(text)
    except Exception as e:
        logger.error(f"Gemini JSON call failed: {e}")
        return fallback


@router.get("/zones")
async def get_opportunity_zones(
    ward_id: Optional[int] = Query(None),
    days: int = Query(180, ge=30, le=365),
    current_user: UserMongo = Depends(_require_dev_access),
):
    """
    Analyse geo-tagged tickets to surface top underserved zones in a ward.
    Returns top 5 scored zones with AI narratives.
    """
    effective_ward = ward_id or current_user.ward_id

    # Check cache
    cache_key = (effective_ward, days)
    cached = _zone_cache.get(cache_key)
    if cached and cached["expires_at"] > datetime.utcnow():
        return cached["data"]

    col = _get_tickets_col()
    since = datetime.utcnow() - timedelta(days=days)

    raw_tickets = await col.find(
        {
            "ward_id": effective_ward,
        }
    ).to_list(length=5000)
    
    raw_tickets = [t for t in raw_tickets if isinstance(t.get("created_at"), datetime) and t["created_at"].replace(tzinfo=None) >= since]

    if len(raw_tickets) < 10:
        return {
            "ward_id": effective_ward,
            "analysis_period_days": days,
            "total_tickets_analyzed": len(raw_tickets),
            "zones": [],
            "empty_reason": "Not enough ticket data to analyze zones yet. Zones will appear once at least 10 geo-tagged tickets are in the system.",
        }

    now = datetime.utcnow()
    cutoff_30 = now - timedelta(days=30)
    cutoff_90 = now - timedelta(days=90)

    # Extract lat/lng from GeoJSON [lng, lat]
    tickets_with_loc = []
    for t in raw_tickets:
        loc = t.get("location")
        if loc and isinstance(loc, dict):
            coords = loc.get("coordinates")
            if coords and len(coords) >= 2:
                lng, lat = coords[0], coords[1]
                tickets_with_loc.append({**t, "_lat": lat, "_lng": lng})

    if not tickets_with_loc:
        return {
            "ward_id": effective_ward,
            "analysis_period_days": days,
            "total_tickets_analyzed": len(raw_tickets),
            "zones": [],
            "empty_reason": "No geo-tagged tickets found for this ward.",
        }

    # ── Step 1: Grid construction ─────────────────────────────────────────────
    lats = [t["_lat"] for t in tickets_with_loc]
    lngs = [t["_lng"] for t in tickets_with_loc]
    min_lat, max_lat = min(lats), max(lats)
    min_lng, max_lng = min(lngs), max(lngs)

    CELL_SIZE = 0.005  # ~500m

    cells: Dict[str, List[Dict]] = defaultdict(list)
    for t in tickets_with_loc:
        col_idx = int((t["_lng"] - min_lng) / CELL_SIZE)
        row_idx = int((t["_lat"] - min_lat) / CELL_SIZE)
        cell_id = f"{row_idx}_{col_idx}"
        t["_cell_row"] = row_idx
        t["_cell_col"] = col_idx
        cells[cell_id].append(t)

    # Discard cells with fewer than 3 tickets
    qualifying_cells = {cid: tix for cid, tix in cells.items() if len(tix) >= 3}

    if not qualifying_cells:
        return {
            "ward_id": effective_ward,
            "analysis_period_days": days,
            "total_tickets_analyzed": len(tickets_with_loc),
            "zones": [],
            "empty_reason": "No zones with 3+ tickets found. Try a longer lookback period.",
        }

    # ── Step 2: Per-cell scoring ──────────────────────────────────────────────
    cell_scores = []

    for cell_id, cell_tickets in qualifying_cells.items():
        complaint_volume = len(cell_tickets)

        # Recency weight
        recency_weight = 0
        for t in cell_tickets:
            created = t.get("created_at")
            if isinstance(created, datetime):
                if created >= cutoff_30:
                    recency_weight += 3
                elif created >= cutoff_90:
                    recency_weight += 2
                else:
                    recency_weight += 1
            else:
                recency_weight += 1

        # Recurrence score: same category at same approx location (lat/lng rounded to 3dp)
        loc_cat_counter: Counter = Counter()
        for t in cell_tickets:
            approx_lat = round(t["_lat"], 3)
            approx_lng = round(t["_lng"], 3)
            cat = (t.get("issue_category") or "other").lower()
            loc_cat_counter[(approx_lat, approx_lng, cat)] += 1

        recurrence_score = sum(1 for count in loc_cat_counter.values() if count >= 3)

        # Resolution failure rate
        unresolved = [
            t for t in cell_tickets
            if (t.get("status") or "OPEN") not in ("CLOSED", "RESOLVED", "REJECTED", "CLOSED_UNVERIFIED")
        ]
        resolution_failure_rate = len(unresolved) / complaint_volume

        # Dominant category
        cat_counter: Counter = Counter()
        for t in cell_tickets:
            cat_counter[(t.get("issue_category") or "other").lower()] += 1
        dominant_category = cat_counter.most_common(1)[0][0]

        # Category breakdown
        category_breakdown = dict(cat_counter)

        # Cell center
        cell_center_lat = sum(t["_lat"] for t in cell_tickets) / complaint_volume
        cell_center_lng = sum(t["_lng"] for t in cell_tickets) / complaint_volume

        # Cell bounds
        row_idx = cell_tickets[0]["_cell_row"]
        col_idx = cell_tickets[0]["_cell_col"]
        bounds = {
            "south": min_lat + row_idx * CELL_SIZE,
            "north": min_lat + (row_idx + 1) * CELL_SIZE,
            "west": min_lng + col_idx * CELL_SIZE,
            "east": min_lng + (col_idx + 1) * CELL_SIZE,
        }

        cell_scores.append({
            "cell_id": cell_id,
            "cell_row": row_idx,
            "cell_col": col_idx,
            "complaint_volume": complaint_volume,
            "recency_weight": recency_weight,
            "recurrence_score": recurrence_score,
            "resolution_failure_rate": round(resolution_failure_rate, 3),
            "dominant_category": dominant_category,
            "category_breakdown": category_breakdown,
            "cell_center": {"lat": round(cell_center_lat, 6), "lng": round(cell_center_lng, 6)},
            "bounds": bounds,
            "infrastructure_recommendation": INFRA_MAP.get(dominant_category, INFRA_MAP["other"]),
        })

    # Compute max values for normalisation
    max_recency = max((c["recency_weight"] for c in cell_scores), default=1) or 1
    max_recurrence = max((c["recurrence_score"] for c in cell_scores), default=1) or 1

    for c in cell_scores:
        c["opportunity_score"] = round(
            (c["recency_weight"] / max_recency * 40)
            + (c["recurrence_score"] / max_recurrence * 30)
            + (c["resolution_failure_rate"] * 20)
            + (min(c["complaint_volume"], 50) / 50 * 10),
            1,
        )

    # ── Step 3: Top 5 ─────────────────────────────────────────────────────────
    top_zones = sorted(cell_scores, key=lambda c: c["opportunity_score"], reverse=True)[:5]
    for rank, zone in enumerate(top_zones, 1):
        zone["rank"] = rank

    # ── Step 4: Gemini narratives ─────────────────────────────────────────────
    top_zones_data = [
        {
            "cell_id": z["cell_id"],
            "rank": z["rank"],
            "dominant_category": z["dominant_category"],
            "infrastructure_recommendation": z["infrastructure_recommendation"],
            "complaint_volume": z["complaint_volume"],
            "resolution_failure_rate": z["resolution_failure_rate"],
            "recurrence_score": z["recurrence_score"],
            "opportunity_score": z["opportunity_score"],
        }
        for z in top_zones
    ]

    narratives_prompt = f"""You are an infrastructure planning advisor for a municipal ward councillor.
Based on the following data about the top underserved zones in the ward, write a brief (2-3 sentence) recommendation for EACH zone explaining:
1. What the data shows about this zone
2. What infrastructure investment is recommended
3. Who would benefit and why it matters

Use only the numbers provided. Do not invent statistics.
Be direct and specific. Write in plain English suitable for a non-technical elected official.

Zone data:
{json.dumps(top_zones_data, indent=2)}

Respond in JSON format:
{{
  "zone_narratives": {{
    "<cell_id>": "<2-3 sentence narrative>",
    ...
  }}
}}"""

    fallback_narratives: Dict[str, str] = {
        z["cell_id"]: (
            f"This zone has {z['complaint_volume']} complaints with a {round(z['resolution_failure_rate']*100)}% "
            f"resolution failure rate, primarily around {z['dominant_category']} issues. "
            f"Recommended action: {z['infrastructure_recommendation']}."
        )
        for z in top_zones
    }

    narratives_resp = await _call_gemini_json(
        narratives_prompt,
        {"zone_narratives": fallback_narratives},
    )
    narratives = narratives_resp.get("zone_narratives", fallback_narratives)

    # Attach narratives to zones
    for zone in top_zones:
        zone["ai_narrative"] = narratives.get(zone["cell_id"], fallback_narratives.get(zone["cell_id"], ""))
        # Clean internal helper fields
        zone.pop("_lat", None)
        zone.pop("_lng", None)

    # ── Step 5: Build response ────────────────────────────────────────────────
    response = {
        "ward_id": effective_ward,
        "analysis_period_days": days,
        "total_tickets_analyzed": len(tickets_with_loc),
        "zones": top_zones,
        "min_lat": min_lat,
        "min_lng": min_lng,
    }

    # Cache for 6 hours
    _zone_cache[cache_key] = {
        "data": response,
        "expires_at": datetime.utcnow() + timedelta(hours=6),
    }

    return response


def invalidate_zone_cache(ward_id: int):
    """Call this when a new ticket is created for a ward."""
    keys_to_delete = [k for k in _zone_cache if k[0] == ward_id]
    for k in keys_to_delete:
        del _zone_cache[k]
