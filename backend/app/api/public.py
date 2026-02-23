from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel, Field
from typing import Optional, List

from app.core.database import get_db
from app.services.ticket_service import TicketService
from app.models.ticket import Ticket

router = APIRouter()

class ComplaintCreateEvent(BaseModel):
    description: str
    location_text: str
    reporter_phone: str
    consent_given: bool
    reporter_name: Optional[str] = None
    photo_url: Optional[str] = None
    reporter_user_id: Optional[int] = None

@router.post("/complaints")
async def create_complaint(data: ComplaintCreateEvent, db: AsyncSession = Depends(get_db)):
    ticket = await TicketService.create_ticket(
        db=db,
        description=data.description,
        location_text=data.location_text,
        reporter_phone=data.reporter_phone,
        consent_given=data.consent_given,
        reporter_name=data.reporter_name,
        photo_url=data.photo_url,
        reporter_user_id=data.reporter_user_id
    )
    await db.commit()
    await db.refresh(ticket)
    return {"ticket_code": ticket.ticket_code, "status": ticket.status, "sla_deadline": ticket.sla_deadline}

@router.get("/track/{ticket_code}")
async def track_ticket(ticket_code: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Ticket).where(Ticket.ticket_code == ticket_code))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
        
    return {
        "ticket_code": ticket.ticket_code,
        "status": ticket.status,
        "description": ticket.description,
        "department": ticket.dept_id,
        "priority_label": ticket.priority_label,
        "created_at": ticket.created_at,
        "sla_deadline": ticket.sla_deadline
    }

from app.services.stats_service import StatsService

@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    return await StatsService.get_city_stats(db)

@router.get("/wards/leaderboard")
async def get_leaderboard(db: AsyncSession = Depends(get_db)):
    return await StatsService.get_ward_leaderboard(db)

@router.get("/heatmap")
async def get_heatmap(db: AsyncSession = Depends(get_db)):
    return await StatsService.get_heatmap_data(db)
