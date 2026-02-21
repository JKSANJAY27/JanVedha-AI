from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, text
from datetime import datetime

from app.models.ticket import Ticket, TicketStatus

class StatsService:
    @staticmethod
    async def get_city_stats(db: AsyncSession):
        """Aggregate stats for the hero section of the public dash."""
        
        # Total tickets
        result = await db.execute(select(func.count(Ticket.id)))
        total_tickets = result.scalar() or 0
        
        # Resolved
        result_resolved = await db.execute(select(func.count(Ticket.id)).where(Ticket.status == TicketStatus.CLOSED))
        resolved = result_resolved.scalar() or 0
        
        resolved_pct = (resolved / total_tickets * 100) if total_tickets > 0 else 0.0
        
        # Active Critical
        result_critical = await db.execute(
            select(func.count(Ticket.id))
            .where(
                Ticket.status.in_([TicketStatus.OPEN, TicketStatus.ASSIGNED]),
                Ticket.priority_label == "CRITICAL"
            )
        )
        active_critical = result_critical.scalar() or 0
        
        # Active High
        result_high = await db.execute(
            select(func.count(Ticket.id))
            .where(
                Ticket.status.in_([TicketStatus.OPEN, TicketStatus.ASSIGNED]),
                Ticket.priority_label == "HIGH"
            )
        )
        active_high = result_high.scalar() or 0

        # Note: Avg Resolution Time needs a delta calculation which can be complex in pure ORM, 
        # doing simple stub computation here based on raw SQL if needed, but 0.0 for Phase 1 MVP is fine 
        # unless full SQL computation is implemented later.
        
        return {
            "total_tickets": total_tickets,
            "resolved_pct": round(resolved_pct, 1),
            "avg_resolution_hours": 0.0, # Placeholder
            "active_critical": active_critical,
            "active_high": active_high,
            "last_updated": datetime.utcnow().isoformat()
        }

    @staticmethod
    async def get_heatmap_data(db: AsyncSession):
        # We don't have lat/lng in models yet (using generic `location_text` and `ward_id`). 
        # Phase 1 heat map can return tickets aggregated by ward for now, or empty placeholder
        return []

    @staticmethod
    async def get_ward_leaderboard(db: AsyncSession):
        # We don't have the explicit ward_predictions logic in Phase 1 DB, 
        # just returns empty placeholder for MVP integration.
        return []
