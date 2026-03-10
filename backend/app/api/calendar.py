"""
Calendar API — scheduling endpoints for department work planning.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.core.dependencies import get_current_user, require_ward_officer
from app.mongodb.models.user import UserMongo
from app.mongodb.models.ticket import TicketMongo
from app.mongodb.models.scheduled_event import ScheduledEventMongo
from app.services.ai.schedule_agent import suggest_schedule
from beanie import PydanticObjectId

router = APIRouter()


class CreateEventRequest(BaseModel):
    ticket_id: str
    dept_id: str
    ward_id: Optional[int] = None
    scheduled_date: datetime
    time_slot: Optional[str] = None
    notes: Optional[str] = None
    is_ai_suggested: bool = False


@router.get("/events")
async def get_calendar_events(
    dept_id: Optional[str] = Query(None),
    ward_id: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    current_user: UserMongo = Depends(get_current_user),
):
    """Return scheduled events filtered by dept/ward/month.
    For JUNIOR_ENGINEER: always scoped to their own dept_id from their profile.
    """
    from app.enums import UserRole

    query = {}

    if current_user.role == UserRole.JUNIOR_ENGINEER:
        # Hard-scope to JE's own department — cannot see other depts' calendars
        if current_user.dept_id:
            query["dept_id"] = current_user.dept_id
        if current_user.ward_id:
            query["ward_id"] = current_user.ward_id
    else:
        # All other roles: use query params if provided
        if dept_id:
            query["dept_id"] = dept_id
        if ward_id:
            query["ward_id"] = ward_id

    # Month/year filter
    if month:
        now = datetime.utcnow()
        yr = year or now.year
        start = datetime(yr, month, 1)
        if month == 12:
            end = datetime(yr + 1, 1, 1)
        else:
            end = datetime(yr, month + 1, 1)
        query["scheduled_date"] = {"$gte": start, "$lt": end}

    events = await ScheduledEventMongo.find(query).sort("scheduled_date").to_list()

    return [
        {
            "id": str(e.id),
            "ticket_id": e.ticket_id,
            "ticket_code": e.ticket_code,
            "dept_id": e.dept_id,
            "ward_id": e.ward_id,
            "scheduled_date": e.scheduled_date,
            "time_slot": e.time_slot,
            "notes": e.notes,
            "is_ai_suggested": e.is_ai_suggested,
            "event_type": e.event_type,
            "priority_label": e.priority_label,
            "issue_category": e.issue_category,
            "ticket_description": e.ticket_description,
        }
        for e in events
    ]


@router.post("/events")
async def create_calendar_event(
    data: CreateEventRequest,
    current_user: UserMongo = Depends(require_ward_officer),
):
    """Create or update a scheduled event for a ticket."""
    # Fetch ticket info
    ticket = await TicketMongo.get(PydanticObjectId(data.ticket_id))
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    event = ScheduledEventMongo(
        dept_id=data.dept_id,
        ward_id=data.ward_id,
        ticket_id=data.ticket_id,
        ticket_code=ticket.ticket_code,
        scheduled_date=data.scheduled_date,
        time_slot=data.time_slot,
        notes=data.notes,
        is_ai_suggested=data.is_ai_suggested,
        officer_id=str(current_user.id),
        priority_label=ticket.priority_label,
        issue_category=ticket.issue_category,
    )
    await event.insert()

    # Also stamp scheduled_date on the ticket itself
    ticket.scheduled_date = data.scheduled_date
    await ticket.save()

    return {"id": str(event.id), "message": "Event scheduled successfully"}


@router.delete("/events/{event_id}")
async def delete_calendar_event(
    event_id: str,
    current_user: UserMongo = Depends(require_ward_officer),
):
    """Remove a calendar event."""
    event = await ScheduledEventMongo.get(PydanticObjectId(event_id))
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    await event.delete()
    return {"message": "Event deleted"}


@router.get("/ai-suggest")
async def get_ai_schedule_suggestions(
    dept_id: str = Query(...),
    ward_id: int = Query(...),
    current_user: UserMongo = Depends(require_ward_officer),
):
    """
    AI-powered scheduling: suggest dates for all open tickets in a dept+ward.
    Based on priority score, SLA, and dept daily capacity.
    """
    suggestions = await suggest_schedule(dept_id=dept_id, ward_id=ward_id)
    return {
        "dept_id": dept_id,
        "ward_id": ward_id,
        "generated_at": datetime.utcnow(),
        "suggestions": [
            {
                "ticket_id": s["ticket_id"],
                "ticket_code": s["ticket_code"],
                "suggested_date": s["suggested_date"],
                "priority_label": s["priority_label"],
                "priority_score": s["priority_score"],
                "issue_category": s["issue_category"],
            }
            for s in suggestions
        ]
    }


@router.post("/ai-suggest/apply")
async def apply_ai_suggestions(
    dept_id: str,
    ward_id: int,
    current_user: UserMongo = Depends(require_ward_officer),
):
    """
    Accept all AI suggestions: create ScheduledEvent docs and stamp dates on tickets.
    """
    suggestions = await suggest_schedule(dept_id=dept_id, ward_id=ward_id)

    created = 0
    for s in suggestions:
        ticket = await TicketMongo.get(PydanticObjectId(s["ticket_id"]))
        if not ticket:
            continue

        # Update ticket's ai_suggested_date
        ticket.ai_suggested_date = s["suggested_date"]
        ticket.scheduled_date = s["suggested_date"]
        await ticket.save()

        # Create event doc
        event = ScheduledEventMongo(
            dept_id=dept_id,
            ward_id=ward_id,
            ticket_id=s["ticket_id"],
            ticket_code=s["ticket_code"],
            scheduled_date=s["suggested_date"],
            is_ai_suggested=True,
            officer_id=str(current_user.id),
            priority_label=s["priority_label"],
            issue_category=s["issue_category"],
        )
        await event.insert()
        created += 1

    return {"applied": created, "message": f"Applied {created} AI-suggested schedules"}
