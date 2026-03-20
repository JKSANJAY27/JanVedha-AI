"""
Shared metric computation helpers for the commissioner dashboard.

All functions are pure (no side effects) and work on lists of
already-fetched ticket dicts or TicketMongo objects.
"""
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


def _ticket_val(ticket, field: str):
    """Safely get a field from either a dict or a Beanie document."""
    if isinstance(ticket, dict):
        return ticket.get(field)
    return getattr(ticket, field, None)


def compute_ticket_metrics(
    tickets: list,
    sla_days: int,
    reference_period_tickets: list = None
) -> dict:
    """
    Given a list of ticket dicts or TicketMongo objects, compute
    standard performance metrics including trend direction.
    """
    now = datetime.utcnow()
    sla_window = timedelta(days=sla_days)

    # Categorise
    resolved = [t for t in tickets if _ticket_val(t, "status") in ("CLOSED", "resolved")]
    open_t = [t for t in tickets if _ticket_val(t, "status") in ("OPEN", "open")]
    in_progress = [t for t in tickets if _ticket_val(t, "status") in ("IN_PROGRESS", "in_progress", "ASSIGNED", "SCHEDULED")]

    total = len(tickets)
    resolved_count = len(resolved)
    open_count = len(open_t)
    in_progress_count = len(in_progress)

    # Resolution rate
    resolution_rate_pct = round((resolved_count / total * 100), 1) if total > 0 else 0.0

    # Average resolution days
    resolution_times = []
    for t in resolved:
        created_at = _ticket_val(t, "created_at")
        resolved_at = _ticket_val(t, "resolved_at")
        if created_at and resolved_at:
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at)
                except Exception:
                    continue
            if isinstance(resolved_at, str):
                try:
                    resolved_at = datetime.fromisoformat(resolved_at)
                except Exception:
                    continue
            delta = (resolved_at - created_at).days
            if delta >= 0:
                resolution_times.append(delta)

    avg_resolution_days = round(sum(resolution_times) / len(resolution_times), 1) if resolution_times else None

    # SLA breach count for resolved
    sla_breach_count = 0
    for t in resolved:
        created_at = _ticket_val(t, "created_at")
        resolved_at = _ticket_val(t, "resolved_at")
        if created_at and resolved_at:
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at)
                except Exception:
                    continue
            if isinstance(resolved_at, str):
                try:
                    resolved_at = datetime.fromisoformat(resolved_at)
                except Exception:
                    continue
            if (resolved_at - created_at).days > sla_days:
                sla_breach_count += 1

    # Overdue: open/in_progress tickets past SLA
    overdue_count = 0
    overdue_cutoff = now - sla_window
    for t in open_t + in_progress:
        created_at = _ticket_val(t, "created_at")
        if created_at:
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at)
                except Exception:
                    continue
            if created_at < overdue_cutoff:
                overdue_count += 1

    # Trend direction (vs reference period)
    trend_direction = None
    trend_delta_days = None
    if reference_period_tickets is not None:
        ref_resolved = [t for t in reference_period_tickets if _ticket_val(t, "status") in ("CLOSED", "resolved")]
        ref_times = []
        for t in ref_resolved:
            created_at = _ticket_val(t, "created_at")
            resolved_at = _ticket_val(t, "resolved_at")
            if created_at and resolved_at:
                if isinstance(created_at, str):
                    try:
                        created_at = datetime.fromisoformat(created_at)
                    except Exception:
                        continue
                if isinstance(resolved_at, str):
                    try:
                        resolved_at = datetime.fromisoformat(resolved_at)
                    except Exception:
                        continue
                delta = (resolved_at - created_at).days
                if delta >= 0:
                    ref_times.append(delta)

        ref_avg = sum(ref_times) / len(ref_times) if ref_times else None
        if ref_avg is not None and avg_resolution_days is not None:
            trend_delta_days = round(avg_resolution_days - ref_avg, 1)
            if avg_resolution_days < ref_avg * 0.9:
                trend_direction = "improving"
            elif avg_resolution_days > ref_avg * 1.1:
                trend_direction = "worsening"
            else:
                trend_direction = "stable"
        else:
            trend_direction = "stable"

    return {
        "total_count": total,
        "open_count": open_count,
        "in_progress_count": in_progress_count,
        "resolved_count": resolved_count,
        "resolution_rate_pct": resolution_rate_pct,
        "avg_resolution_days": avg_resolution_days,
        "sla_breach_count": sla_breach_count,
        "overdue_count": overdue_count,
        "trend_direction": trend_direction,
        "trend_delta_days": trend_delta_days,
    }


async def get_all_ward_ids() -> List[str]:
    """Return all distinct ward_id values from the tickets collection."""
    try:
        from app.mongodb.models.ticket import TicketMongo
        pipeline = [
            {"$group": {"_id": "$ward_id"}},
            {"$match": {"_id": {"$ne": None}}},
        ]
        motor_col = TicketMongo.get_pymongo_collection()
        results = await motor_col.aggregate(pipeline).to_list(None)
        return [str(r["_id"]) for r in results if r["_id"] is not None]
    except Exception as e:
        logger.error(f"get_all_ward_ids failed: {e}")
        return []


async def get_technician_load(ward_ids: list = None) -> Dict[str, Dict]:
    """
    Query tickets for open/in_progress work grouped by technician.
    Returns { technician_id: { active_ticket_count, categories } }
    """
    try:
        from app.mongodb.models.ticket import TicketMongo
        open_statuses = ["OPEN", "IN_PROGRESS", "ASSIGNED", "SCHEDULED", "PENDING_VERIFICATION", "REOPENED"]
        query = {"status": {"$in": open_statuses}, "technician_id": {"$ne": None}}

        motor_col = TicketMongo.get_pymongo_collection()
        cursor = motor_col.find(query, {"technician_id": 1, "issue_category": 1, "dept_id": 1})
        docs = await cursor.to_list(None)

        result: Dict[str, Dict] = {}
        for doc in docs:
            tid = str(doc.get("technician_id", ""))
            if not tid:
                continue
            if tid not in result:
                result[tid] = {"active_ticket_count": 0, "categories": set()}
            result[tid]["active_ticket_count"] += 1
            cat = doc.get("issue_category") or doc.get("dept_id") or "general"
            result[tid]["categories"].add(cat)

        # Convert sets to lists
        for tid in result:
            result[tid]["categories"] = list(result[tid]["categories"])

        return result
    except Exception as e:
        logger.error(f"get_technician_load failed: {e}")
        return {}


DEPT_SEED_DATA = [
    {
        "dept_id": "roads",
        "dept_name": "Roads & Infrastructure",
        "ticket_categories": ["roads"],
        "sla_days": 7,
        "color_hex": "#854F0B",
    },
    {
        "dept_id": "water_drainage",
        "dept_name": "Water & Drainage",
        "ticket_categories": ["water", "drainage"],
        "sla_days": 3,
        "color_hex": "#185FA5",
    },
    {
        "dept_id": "electrical",
        "dept_name": "Electrical",
        "ticket_categories": ["lighting"],
        "sla_days": 2,
        "color_hex": "#534AB7",
    },
    {
        "dept_id": "sanitation",
        "dept_name": "Sanitation",
        "ticket_categories": ["waste"],
        "sla_days": 1,
        "color_hex": "#0F6E56",
    },
    {
        "dept_id": "general",
        "dept_name": "General Services",
        "ticket_categories": ["other"],
        "sla_days": 5,
        "color_hex": "#5F5E5A",
    },
]


async def seed_dept_config() -> None:
    """Seed department_config collection if empty."""
    try:
        from app.mongodb.models.dept_config import DeptConfigMongo
        count = await DeptConfigMongo.count()
        if count == 0:
            for d in DEPT_SEED_DATA:
                await DeptConfigMongo(**d).insert()
            logger.info("Seeded department_config with 5 departments.")
    except Exception as e:
        logger.error(f"seed_dept_config failed: {e}")
