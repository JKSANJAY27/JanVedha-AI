"""
Public API — citizen-facing endpoints.

Fully rewritten to use MongoDB (Beanie) + the full AI pipeline.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.services.ticket_service import TicketService
from app.services.stats_service import StatsService
from app.mongodb.models.ticket import TicketMongo
from app.enums import TicketSource

router = APIRouter()


class ComplaintCreateEvent(BaseModel):
    description: str
    location_text: str
    reporter_phone: str
    consent_given: bool
    reporter_name: Optional[str] = None
    photo_url: Optional[str] = None
    reporter_user_id: Optional[str] = None
    ward_id: Optional[int] = None


@router.post("/complaints")
async def create_complaint(data: ComplaintCreateEvent):
    """
    Submit a new civic complaint. Runs the full AI pipeline:
    classify → route → prioritize → suggest → memory check.
    """
    ticket = await TicketService.create_ticket(
        description=data.description,
        location_text=data.location_text,
        reporter_phone=data.reporter_phone,
        consent_given=data.consent_given,
        reporter_name=data.reporter_name,
        photo_url=data.photo_url,
        reporter_user_id=data.reporter_user_id,
        ward_id=data.ward_id,
        source=TicketSource.WEB_PORTAL,
    )
    response = {
        "ticket_code": ticket.ticket_code,
        "status": ticket.status,
        "dept_id": ticket.dept_id,
        "priority_label": ticket.priority_label,
        "priority_score": ticket.priority_score,
        "priority_source": ticket.priority_source,
        "sla_deadline": ticket.sla_deadline,
        "ai_routing_reason": ticket.ai_routing_reason,
        "suggestions": ticket.ai_suggestions,
        "language_detected": ticket.language_detected,
    }
    if ticket.seasonal_alert:
        response["seasonal_alert"] = ticket.seasonal_alert
    return response


@router.get("/track/{ticket_code}")
async def track_ticket(ticket_code: str):
    """Track a ticket by its unique code."""
    ticket = await TicketMongo.find_one(TicketMongo.ticket_code == ticket_code)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return {
        "ticket_code": ticket.ticket_code,
        "status": ticket.status,
        "description": ticket.description,
        "department": ticket.dept_id,
        "issue_category": ticket.issue_category,
        "priority_label": ticket.priority_label,
        "priority_score": ticket.priority_score,
        "created_at": ticket.created_at,
        "sla_deadline": ticket.sla_deadline,
        "suggestions": ticket.ai_suggestions,
        "seasonal_alert": ticket.seasonal_alert,
    }


@router.get("/stats")
async def get_stats():
    return await StatsService.get_city_stats()


@router.get("/wards/leaderboard")
async def get_leaderboard():
    return await StatsService.get_ward_leaderboard()


@router.get("/heatmap")
async def get_heatmap():
    return await StatsService.get_heatmap_data()


@router.get("/seasonal-alerts")
async def get_seasonal_alerts(ward_id: int, month: int):
    """
    Returns predicted recurring issues for a ward in a given month.
    Based on historical issue memory — useful for preventive planning.
    """
    if not (1 <= month <= 12):
        raise HTTPException(status_code=400, detail="month must be between 1 and 12")
    from app.services.ai.memory_agent import get_seasonal_alerts_for_ward
    alerts = await get_seasonal_alerts_for_ward(ward_id=ward_id, month=month)
    return {
        "ward_id": ward_id,
        "month": month,
        "alerts": alerts,
        "count": len(alerts),
    }


@router.get("/map/issues")
async def get_map_issues(
    priority: Optional[str] = None,
    status: Optional[str] = None,
    ward_id: Optional[int] = None,
    limit: int = 300,
):
    """
    Returns tickets with geographic coordinates for the interactive map.
    Filters by priority, status, and ward_id.
    """
    query = TicketMongo.find()

    if ward_id:
        query = TicketMongo.find(TicketMongo.ward_id == ward_id)

    tickets = await query.limit(limit).to_list()

    results = []
    for t in tickets:
        # Filter by priority (comma-separated list allowed)
        if priority:
            priorities = [p.strip().upper() for p in priority.split(",")]
            if t.priority_label not in priorities:
                continue
        # Filter by status
        if status:
            statuses = [s.strip().upper() for s in status.split(",")]
            if t.status not in statuses:
                continue

        # Extract lat/lng from location field
        lat, lng = None, None
        if t.location and isinstance(t.location, dict):
            lat = t.location.get("lat")
            lng = t.location.get("lng")

        results.append({
            "id": str(t.id),
            "ticket_code": t.ticket_code,
            "description": t.description,
            "dept_id": t.dept_id,
            "priority_label": t.priority_label,
            "priority_score": t.priority_score,
            "status": t.status,
            "lat": lat,
            "lng": lng,
            "location": t.location,
            "created_at": t.created_at,
            "ward_id": t.ward_id,
        })

    return {"issues": results, "count": len(results)}
