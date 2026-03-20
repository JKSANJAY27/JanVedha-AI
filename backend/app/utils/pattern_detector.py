"""
Pattern detection engine for the Systemic Issue Detector.

Four detection algorithms:
1. Geographic cluster: 5+ same-category tickets within ~500m in 7 days
2. Recurrence spike: new complaints at same location as recently resolved ticket
3. Department collapse: resolved < created for 3+ consecutive weeks
4. Sentiment drop: ward sentiment drops >15 points in 7 days
"""
import json
import logging
import math
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PATTERN 1 — Geographic cluster detection
# ---------------------------------------------------------------------------

async def detect_geographic_clusters(all_ward_ids: list) -> List[Dict]:
    """5+ same-category tickets within ~500m in the past 7 days."""
    alerts = []
    try:
        from app.mongodb.models.ticket import TicketMongo
        from app.mongodb.models.intelligence_alert import IntelligenceAlertMongo

        cutoff = datetime.utcnow() - timedelta(days=7)
        motor_col = TicketMongo.get_pymongo_collection()
        tickets = await motor_col.find(
            {
                "created_at": {"$gte": cutoff},
                "status": {"$ne": "CLOSED"},
                "location": {"$ne": None},
            },
            {"_id": 1, "location": 1, "issue_category": 1, "dept_id": 1, "ward_id": 1, "created_at": 1}
        ).to_list(None)

        # Compute grid cells (~500m ≈ 0.005 degrees)
        # Group by (cell_row, cell_col, category)
        groups: Dict[str, List] = {}
        for t in tickets:
            loc = t.get("location") or {}
            coords = loc.get("coordinates")  # GeoJSON [lng, lat]
            if not coords or len(coords) < 2:
                continue
            lng, lat = coords[0], coords[1]
            category = t.get("issue_category") or t.get("dept_id") or "general"

            cell_col = math.floor(lng / 0.005)
            cell_row = math.floor(lat / 0.005)
            key = f"{cell_row}_{cell_col}_{category}"
            if key not in groups:
                groups[key] = []
            groups[key].append(t)

        week_num = datetime.utcnow().isocalendar()[1]

        for key, cluster_tickets in groups.items():
            if len(cluster_tickets) < 5:
                continue

            parts = key.split("_")
            cell_row, cell_col = parts[0], parts[1]
            category = "_".join(parts[2:])

            fingerprint = f"geo_cluster_{key}_{week_num}"

            # Deduplication check
            existing = await IntelligenceAlertMongo.find_one(
                IntelligenceAlertMongo.fingerprint == fingerprint,
                IntelligenceAlertMongo.created_at >= (datetime.utcnow() - timedelta(days=7))
            )
            if existing:
                continue

            count = len(cluster_tickets)
            lats = []
            lngs = []
            for t in cluster_tickets:
                coords = (t.get("location") or {}).get("coordinates")
                if coords and len(coords) >= 2:
                    lngs.append(coords[0])
                    lats.append(coords[1])

            avg_lat = sum(lats) / len(lats) if lats else 0
            avg_lng = sum(lngs) / len(lngs) if lngs else 0

            severity = "high" if count >= 10 else ("medium" if count >= 7 else "low")
            ward_ids = list(set(str(t.get("ward_id", "")) for t in cluster_tickets if t.get("ward_id")))
            ticket_ids = [str(t["_id"]) for t in cluster_tickets]
            oldest = min((t.get("created_at") for t in cluster_tickets if t.get("created_at")), default=datetime.utcnow())

            alert = {
                "pattern_type": "geographic_cluster",
                "severity": severity,
                "fingerprint": fingerprint,
                "affected_ward_ids": ward_ids,
                "affected_dept_id": None,
                "affected_location": {"lat": avg_lat, "lng": avg_lng},
                "affected_area_label": f"Grid cell ({cell_row},{cell_col})",
                "evidence": {
                    "ticket_count": count,
                    "category": category,
                    "cell_center": {"lat": avg_lat, "lng": avg_lng},
                    "ticket_ids": ticket_ids[:20],
                    "oldest_ticket_date": oldest.isoformat() if oldest else None,
                    "ward_ids": ward_ids,
                    "cell_row": cell_row,
                    "cell_col": cell_col,
                },
            }
            alerts.append(alert)
    except Exception as e:
        logger.error(f"detect_geographic_clusters failed: {e}")
    return alerts


# ---------------------------------------------------------------------------
# PATTERN 2 — Recurrence spike detection
# ---------------------------------------------------------------------------

async def detect_recurrence_spikes(all_ward_ids: list) -> List[Dict]:
    """New complaints at same location+category as a ticket resolved in past 30 days."""
    alerts = []
    try:
        from app.mongodb.models.ticket import TicketMongo
        from app.mongodb.models.intelligence_alert import IntelligenceAlertMongo

        now = datetime.utcnow()
        motor_col = TicketMongo.get_pymongo_collection()

        # Resolved tickets in past 30 days
        resolved_cutoff = now - timedelta(days=30)
        resolved_tickets = await motor_col.find(
            {"status": "CLOSED", "resolved_at": {"$gte": resolved_cutoff}, "location": {"$ne": None}},
            {"_id": 1, "location": 1, "issue_category": 1, "dept_id": 1, "resolved_at": 1}
        ).to_list(None)

        # Build loc_key → resolved ticket map
        resolved_map: Dict[str, Dict] = {}
        for t in resolved_tickets:
            coords = (t.get("location") or {}).get("coordinates")
            if not coords or len(coords) < 2:
                continue
            lat = round(coords[1], 3)
            lng = round(coords[0], 3)
            category = t.get("issue_category") or t.get("dept_id") or "general"
            loc_key = f"{lat}_{lng}_{category}"
            resolved_map[loc_key] = t

        if not resolved_map:
            return alerts

        # Open/in_progress tickets in past 14 days at same locations
        new_cutoff = now - timedelta(days=14)
        new_tickets = await motor_col.find(
            {
                "status": {"$in": ["OPEN", "IN_PROGRESS", "ASSIGNED", "SCHEDULED"]},
                "created_at": {"$gte": new_cutoff},
                "location": {"$ne": None},
            },
            {"_id": 1, "location": 1, "issue_category": 1, "dept_id": 1, "ward_id": 1, "created_at": 1}
        ).to_list(None)

        # Group recurrences by loc_key
        recurrence_groups: Dict[str, List] = {}
        for t in new_tickets:
            coords = (t.get("location") or {}).get("coordinates")
            if not coords or len(coords) < 2:
                continue
            lat = round(coords[1], 3)
            lng = round(coords[0], 3)
            category = t.get("issue_category") or t.get("dept_id") or "general"
            loc_key = f"{lat}_{lng}_{category}"
            if loc_key in resolved_map:
                if loc_key not in recurrence_groups:
                    recurrence_groups[loc_key] = []
                recurrence_groups[loc_key].append(t)

        week_num = now.isocalendar()[1]

        for loc_key, recurrence_tickets in recurrence_groups.items():
            fingerprint = f"recurrence_{loc_key}_{week_num}"
            existing = await IntelligenceAlertMongo.find_one(
                IntelligenceAlertMongo.fingerprint == fingerprint,
                IntelligenceAlertMongo.created_at >= (now - timedelta(days=7))
            )
            if existing:
                continue

            original = resolved_map[loc_key]
            recurrence_count = len(recurrence_tickets)
            severity = "high" if recurrence_count >= 3 else "medium"
            category = loc_key.rsplit("_", 1)[0].rsplit("_", 1)[-1] if "_" in loc_key else "general"
            parts = loc_key.split("_")
            category = parts[2] if len(parts) >= 3 else "general"

            alert = {
                "pattern_type": "recurrence_spike",
                "severity": severity,
                "fingerprint": fingerprint,
                "affected_ward_ids": list(set(str(t.get("ward_id", "")) for t in recurrence_tickets if t.get("ward_id"))),
                "affected_dept_id": None,
                "affected_location": None,
                "affected_area_label": None,
                "evidence": {
                    "location_key": loc_key,
                    "original_ticket_id": str(original["_id"]),
                    "original_resolved_at": original.get("resolved_at").isoformat() if original.get("resolved_at") else None,
                    "recurrence_ticket_ids": [str(t["_id"]) for t in recurrence_tickets],
                    "recurrence_count": recurrence_count,
                    "category": category,
                },
            }
            alerts.append(alert)
    except Exception as e:
        logger.error(f"detect_recurrence_spikes failed: {e}")
    return alerts


# ---------------------------------------------------------------------------
# PATTERN 3 — Department collapse detection
# ---------------------------------------------------------------------------

async def detect_department_collapse(all_ward_ids: list) -> List[Dict]:
    """resolved < created for 3+ consecutive weeks in a department."""
    alerts = []
    try:
        from app.mongodb.models.dept_config import DeptConfigMongo
        from app.mongodb.models.ticket import TicketMongo
        from app.mongodb.models.intelligence_alert import IntelligenceAlertMongo

        now = datetime.utcnow()
        dept_configs = await DeptConfigMongo.find_all().to_list()
        motor_col = TicketMongo.get_pymongo_collection()

        for dept in dept_configs:
            categories = dept.ticket_categories
            week_num = now.isocalendar()[1]

            weekly_data = []
            for i in range(5, -1, -1):  # 6 weeks, oldest first
                week_start = now - timedelta(days=7 * (i + 1))
                week_end = now - timedelta(days=7 * i)

                created = await motor_col.count_documents({
                    "issue_category": {"$in": categories},
                    "created_at": {"$gte": week_start, "$lt": week_end},
                })
                resolved = await motor_col.count_documents({
                    "issue_category": {"$in": categories},
                    "status": "CLOSED",
                    "resolved_at": {"$gte": week_start, "$lt": week_end},
                })
                net = resolved - created
                weekly_data.append({
                    "week_label": f"W{6 - i}",
                    "week_start": week_start.isoformat(),
                    "week_end": week_end.isoformat(),
                    "created": created,
                    "resolved": resolved,
                    "net": net,
                })

            # Find longest consecutive negative run
            max_run = 0
            current_run = 0
            for w in weekly_data:
                if w["net"] < 0:
                    current_run += 1
                    max_run = max(max_run, current_run)
                else:
                    current_run = 0

            if max_run < 3:
                continue

            fingerprint = f"dept_collapse_{dept.dept_id}_{week_num}"
            existing = await IntelligenceAlertMongo.find_one(
                IntelligenceAlertMongo.fingerprint == fingerprint,
                IntelligenceAlertMongo.created_at >= (now - timedelta(days=7))
            )
            if existing:
                continue

            total_backlog = sum(abs(w["net"]) for w in weekly_data if w["net"] < 0)
            open_count = await motor_col.count_documents({
                "issue_category": {"$in": categories},
                "status": {"$in": ["OPEN", "IN_PROGRESS", "ASSIGNED"]},
            })

            severity = "high" if max_run >= 5 else "medium"
            alert = {
                "pattern_type": "department_collapse",
                "severity": severity,
                "fingerprint": fingerprint,
                "affected_ward_ids": [],
                "affected_dept_id": dept.dept_id,
                "affected_location": None,
                "affected_area_label": dept.dept_name,
                "evidence": {
                    "dept_id": dept.dept_id,
                    "dept_name": dept.dept_name,
                    "consecutive_negative_weeks": max_run,
                    "weekly_data": weekly_data,
                    "total_backlog_growth": total_backlog,
                    "current_open_count": open_count,
                },
            }
            alerts.append(alert)
    except Exception as e:
        logger.error(f"detect_department_collapse failed: {e}")
    return alerts


# ---------------------------------------------------------------------------
# PATTERN 4 — Sentiment drop detection
# ---------------------------------------------------------------------------

async def detect_sentiment_drops(all_ward_ids: list) -> List[Dict]:
    """Ward social media sentiment drops >15 points in 7 days."""
    alerts = []
    try:
        from app.mongodb.models.social_post import SocialPostMongo
        from app.mongodb.models.intelligence_alert import IntelligenceAlertMongo

        now = datetime.utcnow()
        motor_col = SocialPostMongo.get_pymongo_collection()

        # Get ward/sentiment data for past 14 days
        pipeline = [
            {"$match": {
                "scraped_at": {"$gte": now - timedelta(days=14)},
                "sentiment_score": {"$ne": None},
                "ward_id": {"$ne": None}
            }},
            {"$project": {
                "ward_id": 1,
                "sentiment_score": 1,
                "days_ago": {
                    "$divide": [
                        {"$subtract": [now, "$scraped_at"]},
                        86400000  # ms per day
                    ]
                }
            }},
            {"$group": {
                "_id": {
                    "ward_id": "$ward_id",
                    "is_recent": {"$lte": ["$days_ago", 7]}
                },
                "avg_sentiment": {"$avg": "$sentiment_score"},
                "count": {"$sum": 1}
            }}
        ]

        results = await motor_col.aggregate(pipeline).to_list(None)

        # Organise by ward
        ward_sentiments: Dict[str, Dict] = {}
        for r in results:
            ward_id = str(r["_id"]["ward_id"])
            is_recent = r["_id"]["is_recent"]
            if ward_id not in ward_sentiments:
                ward_sentiments[ward_id] = {}
            key = "recent" if is_recent else "previous"
            ward_sentiments[ward_id][key] = r["avg_sentiment"]

        week_num = now.isocalendar()[1]
        for ward_id, data in ward_sentiments.items():
            prev_avg = data.get("previous")
            curr_avg = data.get("recent")
            if prev_avg is None or curr_avg is None:
                continue

            drop = prev_avg - curr_avg
            if drop <= 15:
                continue

            fingerprint = f"sentiment_drop_{ward_id}_{week_num}"
            existing = await IntelligenceAlertMongo.find_one(
                IntelligenceAlertMongo.fingerprint == fingerprint,
                IntelligenceAlertMongo.created_at >= (now - timedelta(days=7))
            )
            if existing:
                continue

            severity = "high" if drop > 30 else "medium"
            alert = {
                "pattern_type": "sentiment_drop",
                "severity": severity,
                "fingerprint": fingerprint,
                "affected_ward_ids": [ward_id],
                "affected_dept_id": None,
                "affected_location": None,
                "affected_area_label": f"Ward {ward_id}",
                "evidence": {
                    "ward_id": ward_id,
                    "previous_week_avg": round(prev_avg, 1),
                    "current_week_avg": round(curr_avg, 1),
                    "drop_magnitude": round(drop, 1),
                },
            }
            alerts.append(alert)
    except Exception as e:
        logger.error(f"detect_sentiment_drops failed (graceful): {e}")
    return alerts


# ---------------------------------------------------------------------------
# MAIN RUNNER
# ---------------------------------------------------------------------------

async def run_all_detections() -> Dict[str, Any]:
    """Run all four detectors, generate Gemini narratives, insert alerts."""
    from app.utils.metrics import get_all_ward_ids

    all_ward_ids = await get_all_ward_ids()

    # Run all four detectors independently (errors in one don't block others)
    all_new_alerts: List[Dict] = []

    for detector_fn, name in [
        (detect_geographic_clusters, "geographic_clusters"),
        (detect_recurrence_spikes, "recurrence_spikes"),
        (detect_department_collapse, "department_collapse"),
        (detect_sentiment_drops, "sentiment_drops"),
    ]:
        try:
            results = await detector_fn(all_ward_ids)
            all_new_alerts.extend(results)
        except Exception as e:
            logger.error(f"Detector {name} failed: {e}")

    if not all_new_alerts:
        return {"new_alerts": 0}

    # Single Gemini call for all new alerts
    try:
        narratives = await _generate_narratives(all_new_alerts)
    except Exception as e:
        logger.error(f"Gemini narrative generation failed: {e}")
        narratives = []

    # Merge narratives back
    for i, alert in enumerate(all_new_alerts):
        narr = next((n for n in narratives if n.get("index") == i), None)
        if narr:
            alert["summary"] = narr.get("summary", "")
            alert["detail"] = narr.get("detail", "")
            alert["recommended_action"] = narr.get("recommended_action", "")
        else:
            pt = alert.get("pattern_type", "unknown")
            area = alert.get("affected_area_label") or (
                ", ".join(alert.get("affected_ward_ids", [])) or "the jurisdiction"
            )
            alert["summary"] = f"Pattern detected: {pt} in {area}"
            alert["detail"] = json.dumps(alert.get("evidence", {}))
            alert["recommended_action"] = "Manual review required — AI analysis unavailable"

    # Insert into MongoDB
    from app.mongodb.models.intelligence_alert import IntelligenceAlertMongo
    now = datetime.utcnow()
    inserted_ids = []
    for alert_data in all_new_alerts:
        alert_doc = IntelligenceAlertMongo(
            expires_at=now + timedelta(days=14),
            status="new",
            **{k: v for k, v in alert_data.items() if k in IntelligenceAlertMongo.model_fields}
        )
        await alert_doc.insert()
        inserted_ids.append(alert_doc.alert_id)

    # Notify all commissioners
    try:
        await _notify_commissioners_of_alerts(all_new_alerts)
    except Exception as e:
        logger.error(f"Commissioner notification failed: {e}")

    # Update last_run timestamp in settings collection
    try:
        from app.mongodb.database import get_motor_client
        db_name = __import__("app.core.config", fromlist=["settings"]).settings.MONGODB_URI.rsplit("/", 1)[-1].split("?")[0] or "civicai"
        client = get_motor_client()
        await client[db_name]["app_settings"].update_one(
            {"key": "intelligence_last_run"},
            {"$set": {"value": now.isoformat()}},
            upsert=True
        )
    except Exception:
        pass

    return {"new_alerts": len(all_new_alerts), "alert_ids": inserted_ids}


async def _generate_narratives(alerts: List[Dict]) -> List[Dict]:
    """Single Gemini call to generate summaries for all new alerts."""
    try:
        from app.core.config import settings
        import google.generativeai as genai

        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")

        evidence_list = [
            {"index": i, "pattern_type": a["pattern_type"], "evidence": a.get("evidence", {})}
            for i, a in enumerate(alerts)
        ]

        prompt = f"""You are an intelligence analyst for a municipal commissioner.

The following civic governance patterns have been automatically detected. For each pattern, generate:
1. A concise summary (1 sentence, max 20 words, factual)
2. A detailed explanation (2-3 sentences with the specific numbers and what they indicate)
3. A recommended action (1 sentence, specific and actionable for a municipal commissioner)

Patterns detected:
{json.dumps(evidence_list, indent=2)}

Respond in this JSON format:
{{
  "narratives": [
    {{
      "index": 0,
      "summary": "...",
      "detail": "...",
      "recommended_action": "..."
    }}
  ]
}}

Pattern type context:
- geographic_cluster: Same category complaints concentrated in a small area — likely a systemic infrastructure failure
- recurrence_spike: New complaints at same location as recently "resolved" tickets — possible incomplete or shoddy resolution
- department_collapse: Department's backlog growing for multiple consecutive weeks — capacity problem
- sentiment_drop: Ward social media sentiment falling fast — public dissatisfaction is building

Be direct. Write for a senior official, not the public."""

        response = await model.generate_content_async(prompt)
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        parsed = json.loads(text)
        return parsed.get("narratives", [])
    except Exception as e:
        logger.error(f"_generate_narratives failed: {e}")
        return []


async def _notify_commissioners_of_alerts(alerts: List[Dict]) -> None:
    """Create in-app notifications for commissioners."""
    try:
        from app.mongodb.models.user import UserMongo
        from app.enums import UserRole

        commissioners = await UserMongo.find(
            UserMongo.role.in_([UserRole.COMMISSIONER, UserRole.SUPER_ADMIN])
        ).to_list()

        from app.mongodb.database import get_motor_client
        from app.core.config import settings
        db_name = settings.MONGODB_URI.rsplit("/", 1)[-1].split("?")[0] or "civicai"
        client = get_motor_client()
        col = client[db_name]["supervisor_notifications"]

        now = datetime.utcnow()
        for alert in alerts:
            for comm in commissioners:
                await col.insert_one({
                    "user_id": str(comm.id),
                    "type": "intelligence_alert",
                    "title": f"New pattern detected: {alert['pattern_type']}",
                    "body": alert.get("summary", ""),
                    "read": False,
                    "created_at": now,
                })
    except Exception as e:
        logger.error(f"_notify_commissioners_of_alerts failed: {e}")
