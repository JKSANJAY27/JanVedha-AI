"""
Public API — citizen-facing endpoints.

Fully rewritten to use MongoDB (Beanie) + the full AI pipeline.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.core.dependencies import get_current_user
from app.mongodb.models.user import UserMongo
from app.services.ticket_service import TicketService
from app.services.stats_service import StatsService
from app.mongodb.models.ticket import TicketMongo
from app.enums import TicketSource

router = APIRouter()



def get_public_status(ticket: TicketMongo) -> str:
    """Helper to dynamically determine public ticket status based on logic."""
    if ticket.status == "REJECTED":
        return "REJECTED"
    if ticket.status == "CLOSED" or ticket.after_photo_url is not None:
        return "CLOSED"
    
    if ticket.scheduled_date:
        now = datetime.utcnow()
        if ticket.scheduled_date <= now:
            return "IN_PROGRESS"
        else:
            return "SCHEDULED"
            
    if ticket.technician_id or ticket.assigned_officer_id:
        return "ASSIGNED"
        
    return "OPEN"

@router.get("/my-tickets")
async def get_my_tickets(
    current_user: UserMongo = Depends(get_current_user),
    limit: int = 100,
):
    """Return all tickets submitted by the currently logged-in public user."""
    user_id_str = str(current_user.id)
    tickets = (
        await TicketMongo.find(TicketMongo.reporter_user_id == user_id_str)
        .sort(-TicketMongo.created_at)
        .limit(limit)
        .to_list()
    )
    return [
        {
            "id": str(t.id),
            "ticket_code": t.ticket_code,
            "status": get_public_status(t),
            "description": t.description,
            "dept_id": t.dept_id,
            "issue_category": t.issue_category,
            "priority_label": t.priority_label,
            "priority_score": t.priority_score,
            "location_text": t.location_text,
            "created_at": t.created_at,
            "sla_deadline": t.sla_deadline,
        }
        for t in tickets
    ]


class ComplaintCreateEvent(BaseModel):
    description: str
    location_text: str
    reporter_phone: str
    consent_given: bool
    reporter_name: Optional[str] = None
    photo_url: Optional[str] = None
    reporter_user_id: Optional[str] = None
    ward_id: Optional[int] = None
    # GPS coordinates sent directly from the browser (avoids geocoding delay)
    lat: Optional[float] = None
    lng: Optional[float] = None


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
        lat=data.lat,
        lng=data.lng,
    )
    response = {
        "ticket_code": ticket.ticket_code,
        "status": get_public_status(ticket),
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
        "status": get_public_status(ticket),
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


@router.get("/track/{ticket_code}/apr")
async def public_download_apr(ticket_code: str):
    """
    Publicly accessible endpoint to download the Action Taken Report (APR)
    for a given ticket. Allowed only if the ticket status is CLOSED.
    """
    ticket = await TicketMongo.find_one(TicketMongo.ticket_code == ticket_code)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if get_public_status(ticket) != "CLOSED":
        raise HTTPException(
            status_code=400, 
            detail="Final report is only available for closed tickets."
        )

    try:
        from weasyprint import HTML
        from jinja2 import Environment, FileSystemLoader
        import hashlib
        import os
        from datetime import datetime
    except ImportError:
        raise HTTPException(status_code=500, detail="PDF generation libraries are not installed.")

    # Prepare template context
    template_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
    if not os.path.exists(template_dir):
        raise HTTPException(status_code=500, detail="Templates directory not found")
        
    env = Environment(loader=FileSystemLoader(template_dir))
    
    try:
        template = env.get_template("apr_template.html")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load template: {str(e)}")

    doc_hash = hashlib.sha256(f"{ticket.id}-{datetime.utcnow().isoformat()}".encode('utf-8')).hexdigest()[:12].upper()
    
    context = {
        "ticket_code": ticket.ticket_code,
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "priority": ticket.priority_label,
        "department": ticket.dept_id,
        "ward_id": ticket.ward_id or "Unassigned",
        "status": ticket.status,
        "reporter_name": ticket.reporter_name or "Anonymous",
        "issue_category": ticket.issue_category,
        "description": ticket.description,
        "created_at": ticket.created_at.strftime("%Y-%m-%d %H:%M"),
        "officer_id": ticket.assigned_officer_id or "N/A",
        "technician_id": ticket.technician_id or "N/A",
        "resolved_at": ticket.resolved_at.strftime("%Y-%m-%d %H:%M") if ticket.resolved_at else "N/A",
        "verification_verdict": "Verified" if ticket.work_verified else ("Failed" if ticket.work_verified is False else "Manual / Pending"),
        "verification_confidence": f"{ticket.work_verification_confidence*100:.1f}%" if ticket.work_verification_confidence is not None else "N/A",
        "verification_explanation": ticket.work_verification_explanation or "No explanation available.",
        "before_photo_url": ticket.before_photo_url or ticket.photo_url,
        "after_photo_url": ticket.after_photo_url,
        "doc_hash": doc_hash
    }

    try:
        rendered_html = template.render(context)
        pdf_bytes = HTML(string=rendered_html).write_pdf()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to render PDF: {str(e)}")

    from fastapi.responses import Response
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=APR_{ticket.ticket_code}.pdf"
        }
    )

@router.get("/stats")
async def get_stats():
    return await StatsService.get_city_stats()


@router.get("/wards/leaderboard")
async def get_leaderboard():
    return await StatsService.get_ward_leaderboard()


@router.get("/heatmap")
async def get_heatmap(dept_id: Optional[str] = None):
    return {"data": await StatsService.get_heatmap_data(dept_id)}


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
