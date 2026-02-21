from fastapi import APIRouter

router = APIRouter()

@router.get("/stats")
async def get_stats():
    # Stub. Phase 1 replaces this with real DB query.
    return {
        "total_tickets": 0,
        "resolved_pct": 0.0,
        "avg_resolution_hours": 0.0,
        "active_critical": 0,
        "active_high": 0,
        "last_updated": "2025-01-01T00:00:00Z"
    }

@router.get("/wards/leaderboard")
async def get_leaderboard():
    return []

@router.get("/heatmap")
async def get_heatmap():
    return []
