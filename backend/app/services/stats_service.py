"""
StatsService — MongoDB-backed city statistics.
"""
from __future__ import annotations

from datetime import datetime

from app.enums import TicketStatus, PriorityLabel
from app.mongodb.models.ticket import TicketMongo


class StatsService:

    @staticmethod
    async def get_city_stats() -> dict:
        """Aggregate stats for the public dashboard hero section."""
        total = await TicketMongo.count()
        resolved = await TicketMongo.find(
            TicketMongo.status == TicketStatus.CLOSED
        ).count()

        resolved_pct = (resolved / total * 100) if total > 0 else 0.0

        active_statuses = [TicketStatus.OPEN, TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS]

        from beanie.operators import In
        active_critical = await TicketMongo.find(
            In(TicketMongo.status, active_statuses),
            TicketMongo.priority_label == PriorityLabel.CRITICAL,
        ).count()

        active_high = await TicketMongo.find(
            In(TicketMongo.status, active_statuses),
            TicketMongo.priority_label == PriorityLabel.HIGH,
        ).count()

        return {
            "total_tickets": total,
            "resolved_pct": round(resolved_pct, 1),
            "avg_resolution_hours": 0.0,  # TODO: aggregate from resolved_at - created_at
            "active_critical": active_critical,
            "active_high": active_high,
            "last_updated": datetime.utcnow().isoformat(),
        }

    @staticmethod
    async def get_heatmap_data() -> list:
        """Return tickets with GeoJSON coordinates for map visualization."""
        tickets = await TicketMongo.find(
            TicketMongo.location != None
        ).limit(500).to_list()
        return [
            {
                "ticket_code": t.ticket_code,
                "location": t.location,
                "priority_label": t.priority_label,
                "status": t.status,
            }
            for t in tickets
        ]

    @staticmethod
    async def get_ward_leaderboard() -> list:
        """Return per-ward ticket counts sorted by resolution rate."""
        pipeline = [
            {"$group": {
                "_id": "$ward_id",
                "total": {"$sum": 1},
                "resolved": {"$sum": {"$cond": [{"$eq": ["$status", "CLOSED"]}, 1, 0]}},
            }},
            {"$addFields": {
                "resolution_rate": {
                    "$cond": [
                        {"$gt": ["$total", 0]},
                        {"$multiply": [{"$divide": ["$resolved", "$total"]}, 100]},
                        0,
                    ]
                }
            }},
            {"$sort": {"resolution_rate": -1}},
            {"$limit": 20},
        ]
        from app.mongodb.database import get_motor_client
        from app.core.config import settings
        client = get_motor_client()
        db_name = settings.MONGODB_URI.rsplit("/", 1)[-1].split("?")[0] or "civicai"
        result = await client[db_name]["tickets"].aggregate(pipeline).to_list(length=20)
        return [
            {
                "ward_id": r["_id"],
                "total_tickets": r["total"],
                "resolved_tickets": r["resolved"],
                "resolution_rate": round(r["resolution_rate"], 1),
            }
            for r in result if r["_id"] is not None
        ]
