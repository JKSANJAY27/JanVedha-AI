"""
Social Intelligence API — JanVedha AI
Endpoints for social media scraping intelligence for Councillor/Commissioner dashboards.
"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from typing import Optional

from app.core.dependencies import get_current_user
from app.mongodb.models.user import UserMongo
from app.enums import UserRole

router = APIRouter()


def _require_leader(current_user: UserMongo = Depends(get_current_user)) -> UserMongo:
    allowed = {UserRole.COUNCILLOR, UserRole.WARD_OFFICER, UserRole.COMMISSIONER, UserRole.SUPER_ADMIN}
    if current_user.role not in allowed:
        raise HTTPException(status_code=403, detail="Access denied")
    return current_user


def _require_commissioner(current_user: UserMongo = Depends(get_current_user)) -> UserMongo:
    allowed = {UserRole.COMMISSIONER, UserRole.SUPER_ADMIN}
    if current_user.role not in allowed:
        raise HTTPException(status_code=403, detail="Commissioner access required")
    return current_user


@router.get("/sentiment-overview")
async def sentiment_overview(
    ward_id: Optional[int] = Query(None, description="Filter by ward (omit for city-wide)"),
    current_user: UserMongo = Depends(_require_leader),
):
    """
    Return AI-powered ward sentiment analysis (last 7 days).
    Councillors see their own ward by default.
    Response includes: score, label, narrative, top_concerns, ai_powered flag.
    """
    from app.services.social_intel_service import get_sentiment_overview

    effective_ward = ward_id
    if current_user.role == UserRole.COUNCILLOR and effective_ward is None:
        effective_ward = current_user.ward_id

    return await get_sentiment_overview(ward_id=effective_ward)


@router.get("/emerging-issues")
async def emerging_issues(
    ward_id: Optional[int] = Query(None),
    hours: int = Query(72, ge=1, le=168, description="Look-back window in hours"),
    limit: int = Query(6, ge=1, le=20),
    current_user: UserMongo = Depends(_require_leader),
):
    """
    Return top emerging civic issue clusters from AI analysis.
    Each issue includes: category, urgency, headline, count, insight, recommended_action, source_urls.
    """
    from app.services.social_intel_service import get_emerging_issues

    effective_ward = ward_id
    if current_user.role == UserRole.COUNCILLOR and effective_ward is None:
        effective_ward = current_user.ward_id

    return await get_emerging_issues(ward_id=effective_ward, hours=hours, limit=limit)


@router.get("/social-posts")
async def social_posts(
    ward_id: Optional[int] = Query(None),
    platform: Optional[str] = Query(None, description="Filter by platform"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: UserMongo = Depends(_require_leader),
):
    """
    Return paginated social posts (news + Gemini AI), newest first.
    Each post includes source_url for linking, ai_generated flag, and gemini_insight.
    """
    from app.services.social_intel_service import get_social_posts

    effective_ward = ward_id
    if current_user.role == UserRole.COUNCILLOR and effective_ward is None:
        effective_ward = current_user.ward_id

    return await get_social_posts(
        ward_id=effective_ward,
        platform=platform,
        page=page,
        page_size=page_size,
    )


@router.get("/platform-stats")
async def platform_stats(
    ward_id: Optional[int] = Query(None),
    current_user: UserMongo = Depends(_require_leader),
):
    """Return count of posts per platform."""
    from app.services.social_intel_service import get_platform_stats

    effective_ward = ward_id
    if current_user.role == UserRole.COUNCILLOR and effective_ward is None:
        effective_ward = current_user.ward_id

    return await get_platform_stats(ward_id=effective_ward)


@router.get("/status")
async def scrape_status(
    ward_id: Optional[int] = Query(None),
    current_user: UserMongo = Depends(_require_leader),
):
    """
    Return last scrape timestamp and total post count for the ward.
    Used by the frontend 'Refresh Data' button to show last updated time.
    """
    from app.services.social_intel_service import get_scrape_status

    effective_ward = ward_id
    if current_user.role == UserRole.COUNCILLOR and effective_ward is None:
        effective_ward = current_user.ward_id

    return await get_scrape_status(ward_id=effective_ward)


@router.post("/trigger-scrape")
async def trigger_scrape(
    background_tasks: BackgroundTasks,
    ward_id: Optional[int] = Query(None),
    keywords: Optional[str] = Query(None, description="Comma-separated keywords to scrape"),
    current_user: UserMongo = Depends(_require_leader),
):
    """
    Manually trigger a civic intelligence scrape (NewsAPI + Gemini AI).
    Runs in background. Check status or refresh data after ~40 seconds.
    """
    from app.services.social_intel_service import run_social_scrape

    effective_ward = ward_id
    if current_user.role in {UserRole.COUNCILLOR, UserRole.SUPERVISOR}:
        effective_ward = current_user.ward_id

    kw_list = [k.strip() for k in keywords.split(",")] if keywords else None
    background_tasks.add_task(run_social_scrape, kw_list, 25, effective_ward)

    return {
        "status": "triggered",
        "message": "Civic intelligence pipeline started (NewsAPI + Gemini AI). Refresh data in ~40 seconds.",
        "ward_id": effective_ward,
    }


@router.post("/trigger-ward-scrape")
async def trigger_ward_scrape(
    background_tasks: BackgroundTasks,
    ward_id: Optional[int] = Query(None),
    keywords: Optional[str] = Query(None),
    current_user: UserMongo = Depends(_require_leader),
):
    """
    Trigger a ward-level civic intelligence scrape.
    Councillors are scoped to their own ward automatically.
    """
    from app.services.social_intel_service import run_social_scrape

    effective_ward = ward_id
    if current_user.role == UserRole.COUNCILLOR:
        effective_ward = current_user.ward_id

    kw_list = [k.strip() for k in keywords.split(",")] if keywords else None
    background_tasks.add_task(run_social_scrape, kw_list, 20, effective_ward)

    return {
        "status": "triggered",
        "message": "Ward civic intelligence pipeline started. NewsAPI + Gemini AI running. Refresh in ~40 seconds.",
        "ward_id": effective_ward,
    }
