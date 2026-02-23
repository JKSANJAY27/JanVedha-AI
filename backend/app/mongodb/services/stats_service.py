"""
Service: MongoStatsService

MongoDB port of app/services/stats_service.py.
Uses Beanie repository counts and Motor aggregation pipelines
for the same stats exposed by the existing StatsService.
"""
from datetime import datetime
from typing import List, Dict, Any

from app.models.ticket import TicketStatus, PriorityLabel
from app.mongodb.repositories.ticket_repo import TicketRepo
from app.mongodb.models.ticket import TicketMongo
from app.mongodb.models.ward_prediction import WardPredictionMongo


class MongoStatsService:
    """Aggregate stats using MongoDB — mirrors StatsService."""

    @staticmethod
    async def get_city_stats() -> Dict[str, Any]:
        """
        Aggregate stats for the hero section of the public dashboard.
        Mirrors StatsService.get_city_stats().
        """
        total_tickets = await TicketRepo.count_total()
        resolved = await TicketRepo.count_by_status(TicketStatus.CLOSED)
        resolved_pct = (resolved / total_tickets * 100) if total_tickets > 0 else 0.0
        active_critical = await TicketRepo.count_active_by_priority(PriorityLabel.CRITICAL)
        active_high = await TicketRepo.count_active_by_priority(PriorityLabel.HIGH)

        return {
            "total_tickets": total_tickets,
            "resolved_pct": round(resolved_pct, 1),
            "avg_resolution_hours": 0.0,  # Placeholder — see Phase 2 aggregation below
            "active_critical": active_critical,
            "active_high": active_high,
            "last_updated": datetime.utcnow().isoformat(),
        }

    @staticmethod
    async def get_avg_resolution_hours() -> float:
        """
        MongoDB aggregation pipeline to compute average resolution time.
        Only includes tickets that have both created_at and resolved_at set.
        """
        pipeline = [
            {"$match": {"status": "CLOSED", "resolved_at": {"$ne": None}}},
            {
                "$project": {
                    "duration_ms": {
                        "$subtract": ["$resolved_at", "$created_at"]
                    }
                }
            },
            {
                "$group": {
                    "_id": None,
                    "avg_ms": {"$avg": "$duration_ms"}
                }
            },
        ]
        collection = TicketMongo.get_motor_collection()
        result = await collection.aggregate(pipeline).to_list(length=1)
        if not result:
            return 0.0
        avg_ms = result[0].get("avg_ms", 0.0) or 0.0
        return round(avg_ms / 3_600_000, 2)  # ms → hours

    @staticmethod
    async def get_heatmap_data() -> List[Dict[str, Any]]:
        """
        Return ticket counts aggregated by ward_id for heat-map rendering.
        Mirrors StatsService.get_heatmap_data() (was [] placeholder in SQLite version).
        """
        pipeline = [
            {"$match": {"ward_id": {"$ne": None}}},
            {"$group": {"_id": "$ward_id", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        collection = TicketMongo.get_motor_collection()
        rows = await collection.aggregate(pipeline).to_list(length=200)
        return [{"ward_id": r["_id"], "count": r["count"]} for r in rows]

    @staticmethod
    async def get_ward_leaderboard() -> List[Dict[str, Any]]:
        """
        Return the latest WardPrediction for each ward, sorted by risk.
        Mirrors StatsService.get_ward_leaderboard() (was [] placeholder).
        """
        predictions = (
            await WardPredictionMongo.find_all()
            .sort(-WardPredictionMongo.current_score)
            .to_list()
        )
        return [
            {
                "ward_id": p.ward_id,
                "current_score": p.current_score,
                "predicted_next_month_score": p.predicted_next_month_score,
                "risk_level": p.risk_level,
                "ai_recommendation": p.ai_recommendation,
                "computed_at": p.computed_at.isoformat() if p.computed_at else None,
            }
            for p in predictions
        ]
