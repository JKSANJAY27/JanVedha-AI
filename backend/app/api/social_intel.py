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
    Return sentiment counts and score for social media posts
    in the last 7 days. Councillors see their own ward by default.
    """
    from app.services.social_intel_service import get_sentiment_overview

    # Councillors default to their own ward
    effective_ward = ward_id
    if current_user.role == UserRole.COUNCILLOR and effective_ward is None:
        effective_ward = current_user.ward_id

    return await get_sentiment_overview(ward_id=effective_ward)


@router.get("/emerging-issues")
async def emerging_issues(
    ward_id: Optional[int] = Query(None),
    hours: int = Query(24, ge=1, le=168, description="Look-back window in hours"),
    limit: int = Query(8, ge=1, le=20),
    current_user: UserMongo = Depends(_require_leader),
):
    """
    Return top issue categories that are spiking on social media.
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
    Return paginated social media posts, newest first.
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


@router.post("/trigger-scrape")
async def trigger_scrape(
    background_tasks: BackgroundTasks,
    ward_id: Optional[int] = Query(None),
    keywords: Optional[str] = Query(None, description="Comma-separated keywords to scrape"),
    current_user: UserMongo = Depends(_require_commissioner),
):
    """
    Manually trigger a social media scrape. Commissioner-only.
    Runs in the background and returns immediately.
    """
    from app.services.social_intel_service import run_social_scrape

    kw_list = [k.strip() for k in keywords.split(",")] if keywords else None

    background_tasks.add_task(run_social_scrape, kw_list, 20, ward_id)

    return {
        "status": "triggered",
        "message": "Social media scrape started in background. Check back in 30-60 seconds.",
        "ward_id": ward_id,
        "keywords": kw_list,
    }
