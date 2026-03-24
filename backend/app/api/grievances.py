"""
Grievance API endpoints — JanVedha AI

Provides endpoints for:
- Manual scrape triggers
- Listing/viewing ingested grievances
- Manual ticket creation from grievances
- Dismissing non-actionable grievances
- Aggregated stats for dashboard
"""
from __future__ import annotations

import logging
from typing import Optional

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.dependencies import get_current_user
from app.mongodb.models.user import UserMongo
from app.mongodb.models.grievance import GrievanceMongo

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Request models ──────────────────────────────────────────────────────────

class ManualScrapeRequest(BaseModel):
    keywords: Optional[list[str]] = None
    ward_id: Optional[int] = None
    max_results: int = 25


class CreateTicketFromGrievance(BaseModel):
    ward_id: Optional[int] = None


class DismissGrievanceRequest(BaseModel):
    reason: Optional[str] = None


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/scrape")
async def trigger_grievance_scrape(
    data: ManualScrapeRequest,
    current_user: UserMongo = Depends(get_current_user),
):
    """
    Manually trigger a grievance scrape across all configured platforms.
    Returns stats about what was scraped, structured, and auto-ticketed.
    """
    if current_user.role not in ("COMMISSIONER", "COUNCILLOR", "SUPER_ADMIN"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    from app.services.grievance_ingestion_service import run_grievance_ingestion
    stats = await run_grievance_ingestion(
        ward_id=data.ward_id,
        keywords=data.keywords,
        max_results=data.max_results,
    )
    return {"status": "completed", **stats}


@router.get("/")
async def list_grievances(
    current_user: UserMongo = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    severity: Optional[str] = None,
    platform: Optional[str] = None,
    ward_id: Optional[int] = None,
):
    """List ingested grievances with pagination and filtering."""
    if current_user.role not in (
        "COMMISSIONER", "COUNCILLOR", "SUPER_ADMIN",
        "ZONAL_OFFICER", "WARD_OFFICER",
    ):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    query = []
    if status:
        query.append(GrievanceMongo.status == status)
    if severity:
        query.append(GrievanceMongo.severity == severity)
    if platform:
        query.append(GrievanceMongo.source_platform == platform)
    if ward_id is not None:
        query.append(GrievanceMongo.ward_id == ward_id)

    total = await GrievanceMongo.find(*query).count()
    offset = (page - 1) * page_size

    grievances = (
        await GrievanceMongo.find(*query)
        .sort(-GrievanceMongo.ingested_at)
        .skip(offset)
        .limit(page_size)
        .to_list()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "results": [_grievance_to_dict(g) for g in grievances],
    }


@router.get("/stats")
async def grievance_stats(
    current_user: UserMongo = Depends(get_current_user),
    ward_id: Optional[int] = None,
):
    """Aggregated grievance stats for the dashboard."""
    if current_user.role not in (
        "COMMISSIONER", "COUNCILLOR", "SUPER_ADMIN",
    ):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    from app.services.grievance_ingestion_service import get_grievance_stats
    return await get_grievance_stats(ward_id=ward_id)


@router.get("/{grievance_id}")
async def get_grievance(
    grievance_id: str,
    current_user: UserMongo = Depends(get_current_user),
):
    """Get a single grievance by ID."""
    try:
        grievance = await GrievanceMongo.get(PydanticObjectId(grievance_id))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid grievance ID")

    if not grievance:
        raise HTTPException(status_code=404, detail="Grievance not found")

    return _grievance_to_dict(grievance)


@router.post("/{grievance_id}/create-ticket")
async def create_ticket_from_grievance(
    grievance_id: str,
    data: CreateTicketFromGrievance,
    current_user: UserMongo = Depends(get_current_user),
):
    """Manually convert a grievance into a formal ticket."""
    if current_user.role not in (
        "COMMISSIONER", "COUNCILLOR", "SUPER_ADMIN",
    ):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    try:
        grievance = await GrievanceMongo.get(PydanticObjectId(grievance_id))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid grievance ID")

    if not grievance:
        raise HTTPException(status_code=404, detail="Grievance not found")

    if grievance.auto_ticket_generated:
        raise HTTPException(
            status_code=400,
            detail=f"Ticket already created: {grievance.ticket_code}"
        )

    # Override ward_id if provided
    if data.ward_id:
        grievance.ward_id = data.ward_id

    from app.services.grievance_ingestion_service import _create_ticket_from_grievance
    ticket = await _create_ticket_from_grievance(grievance)
    if not ticket:
        raise HTTPException(status_code=500, detail="Failed to create ticket")

    grievance.auto_ticket_generated = True
    grievance.ticket_id = str(ticket.id)
    grievance.ticket_code = ticket.ticket_code
    grievance.status = "ticket_created"
    grievance.reviewed_by = str(current_user.id)
    await grievance.save()

    return {
        "grievance_id": str(grievance.id),
        "ticket_code": ticket.ticket_code,
        "ticket_id": str(ticket.id),
        "status": "ticket_created",
    }


@router.post("/{grievance_id}/dismiss")
async def dismiss_grievance(
    grievance_id: str,
    data: DismissGrievanceRequest,
    current_user: UserMongo = Depends(get_current_user),
):
    """Mark a grievance as not actionable."""
    if current_user.role not in (
        "COMMISSIONER", "COUNCILLOR", "SUPER_ADMIN",
    ):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    try:
        grievance = await GrievanceMongo.get(PydanticObjectId(grievance_id))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid grievance ID")

    if not grievance:
        raise HTTPException(status_code=404, detail="Grievance not found")

    grievance.status = "dismissed"
    grievance.reviewed_by = str(current_user.id)
    grievance.metadata = {
        **grievance.metadata,
        "dismiss_reason": data.reason or "Not actionable",
    }
    await grievance.save()

    return {"grievance_id": str(grievance.id), "status": "dismissed"}


@router.get("/scraper-status/all")
async def get_scraper_status(
    current_user: UserMongo = Depends(get_current_user),
):
    """Return the status of all configured scrapers for the dashboard."""
    from app.core.config import settings

    scrapers = [
        {
            "name": "Twitter/X",
            "platform": "twitter",
            "icon": "🐦",
            "configured": bool(settings.APIFY_API_TOKEN),
            "method": "Apify Actor" if settings.APIFY_API_TOKEN else "Disabled",
        },
        {
            "name": "India Civic Portals",
            "platform": "civic",
            "icon": "🏛️",
            "configured": True,
            "method": "Crawl4AI + BS4 Fallback",
        },
        {
            "name": "CPGRAMS",
            "platform": "cpgrams",
            "icon": "📋",
            "configured": True,
            "method": "Mock Data (Demo)",
        },
        {
            "name": "NewsAPI",
            "platform": "news",
            "icon": "📰",
            "configured": bool(settings.NEWS_API_KEY),
            "method": "NewsAPI.org" if settings.NEWS_API_KEY else "Disabled",
        },
        {
            "name": "Reddit",
            "platform": "reddit",
            "icon": "🤖",
            "configured": bool(settings.APIFY_API_TOKEN or settings.REDDIT_CLIENT_ID),
            "method": (
                "Apify Actor" if settings.APIFY_API_TOKEN
                else ("PRAW" if settings.REDDIT_CLIENT_ID else "Disabled")
            ),
        },
    ]

    # Fetch last scrape time per platform
    for scraper in scrapers:
        last = await GrievanceMongo.find(
            GrievanceMongo.source_platform == scraper["platform"]
        ).sort(-GrievanceMongo.ingested_at).first_or_none()

        scraper["last_scraped_at"] = (
            last.ingested_at.isoformat() if last else None
        )
        count = await GrievanceMongo.find(
            GrievanceMongo.source_platform == scraper["platform"]
        ).count()
        scraper["total_records"] = count

    return {"scrapers": scrapers}


# ── Helpers ─────────────────────────────────────────────────────────────────

def _grievance_to_dict(g: GrievanceMongo) -> dict:
    return {
        "id": str(g.id),
        "source_platform": g.source_platform,
        "source_url": g.source_url,
        "raw_content": g.raw_content[:500] if g.raw_content else "",
        "author": g.author,
        "structured_summary": g.structured_summary,
        "category": g.category,
        "subcategory": g.subcategory,
        "dept_id": g.dept_id,
        "location_text": g.location_text,
        "ward_id": g.ward_id,
        "severity": g.severity,
        "severity_score": g.severity_score,
        "severity_reasoning": g.severity_reasoning,
        "sentiment": g.sentiment,
        "affected_population": g.affected_population,
        "auto_ticket_generated": g.auto_ticket_generated,
        "ticket_id": g.ticket_id,
        "ticket_code": g.ticket_code,
        "status": g.status,
        "original_timestamp": (
            g.original_timestamp.isoformat() if g.original_timestamp else None
        ),
        "ingested_at": g.ingested_at.isoformat() if g.ingested_at else None,
        "processed_at": g.processed_at.isoformat() if g.processed_at else None,
        "keywords": g.keywords,
    }
