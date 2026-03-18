"""
Public Trust API — Pillar 3 endpoints.

Feature 1: AI-Verified Work Proof
Feature 2: Proactive Communication (notification log + ward config)
Feature 3: Misinformation Response Assistant
Feature 4: Public Trust Score (Ward Report Card)
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import base64
import json
import logging

from app.core.dependencies import get_current_user, require_ward_officer
from app.mongodb.models.user import UserMongo
from app.mongodb.models.ticket import TicketMongo
from app.enums import UserRole, TicketStatus

router = APIRouter()
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE 1 — AI-Verified Work Proof
# ═══════════════════════════════════════════════════════════════════════════════

async def _call_gemini_vision(image_b64: str, issue_type: str, coords: Optional[str]) -> dict:
    """Call Gemini Vision to verify the work proof photo."""
    from app.core.config import settings
    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")

        image_data = {
            "mime_type": "image/jpeg",
            "data": image_b64,
        }

        prompt = f"""You are a civic work verification system.
The reported issue was: {issue_type} at coordinates {coords or 'unspecified location'}.
Analyze this photo and respond ONLY with a JSON object in this exact format:
{{
  "verified": true,
  "confidence": "high",
  "verification_statement": "One sentence describing what the photo shows and whether it matches the resolved issue",
  "concerns": null
}}
Use "verified": false if the photo does not confirm the issue is resolved.
Use "confidence": "high", "medium", or "low".
For "concerns": write a string describing any concerns, or null if none."""

        response = await model.generate_content_async([prompt, image_data])
        text = response.text.strip()

        # Strip optional markdown fence
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        return json.loads(text)
    except Exception as e:
        logger.error(f"Gemini vision verification failed: {e}")
        # Graceful fallback
        return {
            "verified": None,
            "confidence": "low",
            "verification_statement": "AI verification temporarily unavailable. Manual review required.",
            "concerns": str(e),
        }


@router.post("/tickets/{ticket_id}/resolve-with-proof")
async def resolve_with_proof(
    ticket_id: str,
    photo: UploadFile = File(...),
    technician_id: str = Form(...),
    current_user: UserMongo = Depends(require_ward_officer),
):
    """
    Technician marks a ticket resolved with a proof photo.
    Gemini Vision verifies the photo and auto-generates a verification statement.
    """
    from beanie import PydanticObjectId

    ticket = await TicketMongo.get(PydanticObjectId(ticket_id))
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Read and encode the photo
    photo_bytes = await photo.read()
    if len(photo_bytes) > 10 * 1024 * 1024:  # 10 MB limit
        raise HTTPException(status_code=400, detail="Photo too large. Maximum size is 10 MB.")

    image_b64 = base64.b64encode(photo_bytes).decode("utf-8")

    # Store photo as a base64 data URL (in a real deployment, upload to S3/MinIO first)
    photo_data_url = f"data:{photo.content_type or 'image/jpeg'};base64,{image_b64}"

    # Call Gemini Vision
    issue_type = ticket.issue_category or ticket.dept_id or "civic issue"
    coords = ticket.coordinates or (
        f"{ticket.location.get('coordinates', [0, 0])}" if ticket.location else None
    )
    gemini_result = await _call_gemini_vision(image_b64, issue_type, coords)

    # Update ticket
    now = datetime.utcnow()
    ticket.status = TicketStatus.CLOSED  # type: ignore
    ticket.resolved_at = now
    ticket.technician_id = technician_id
    ticket.after_photo_url = photo_data_url

    # Map to existing verification fields
    ticket.work_verified = gemini_result.get("verified") is True
    ticket.work_verification_confidence = {
        "high": 1.0, "medium": 0.65, "low": 0.3
    }.get(gemini_result.get("confidence", "low"), 0.3)
    ticket.work_verification_method = "gemini_vision"
    ticket.work_verification_explanation = gemini_result.get("verification_statement", "")
    ticket.work_verified_at = now

    ticket.status_timeline.append({
        "status": "CLOSED",
        "timestamp": now.isoformat(),
        "actor_role": current_user.role,
        "note": f"Resolved with AI-verified proof. Confidence: {gemini_result.get('confidence')}. {gemini_result.get('verification_statement', '')}",
    })
    await ticket.save()

    # Trigger citizen notification
    try:
        from app.services.notification_service import notify_citizen
        import asyncio
        asyncio.create_task(notify_citizen(
            ticket_id=ticket_id,
            event_type="issue_resolved",
            verification_statement=gemini_result.get("verification_statement"),
        ))
    except Exception as e:
        logger.warning(f"Failed to trigger resolve notification: {e}")

    return {
        "ticket_id": ticket_id,
        "ticket_code": ticket.ticket_code,
        "status": ticket.status,
        "resolved_at": now.isoformat(),
        "technician_id": technician_id,
        "gemini_verification": gemini_result,
        "photo_stored": True,
    }


@router.get("/tickets/verified-resolutions")
async def get_verified_resolutions(
    ward_id: Optional[int] = Query(None),
    limit: int = Query(50, le=200),
    current_user: UserMongo = Depends(get_current_user),
):
    """
    Councillor view: list of all AI-verified resolutions in a ward.
    Highlights low-confidence ones for review.
    """
    query_filters = [
        TicketMongo.status.in_(["CLOSED", "RESOLVED"]),
        TicketMongo.work_verified != None,
    ]
    effective_ward = ward_id or current_user.ward_id
    if effective_ward:
        query_filters.append(TicketMongo.ward_id == effective_ward)

    tickets = await TicketMongo.find(*query_filters).sort(
        -TicketMongo.work_verified_at
    ).limit(limit).to_list()

    result = []
    for t in tickets:
        confidence = "low"
        conf_val = t.work_verification_confidence or 0
        if conf_val >= 0.9:
            confidence = "high"
        elif conf_val >= 0.55:
            confidence = "medium"

        result.append({
            "id": str(t.id),
            "ticket_code": t.ticket_code,
            "issue_type": t.issue_category or t.dept_id or "General",
            "area": t.location_text or f"Ward {t.ward_id}" if t.ward_id else "Unknown",
            "ward_id": t.ward_id,
            "technician_id": t.technician_id,
            "verification_statement": t.work_verification_explanation,
            "confidence": confidence,
            "verified": t.work_verified,
            "after_photo_url": t.after_photo_url,
            "resolved_at": t.resolved_at,
            "needs_review": confidence == "low",
        })

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE 2 — Proactive Citizen Communication (Notification Log + Ward Config)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/notifications/log")
async def get_notification_log(
    ward_id: Optional[int] = Query(None),
    limit: int = Query(100, le=500),
    current_user: UserMongo = Depends(get_current_user),
):
    """Communication log for councillor: all notifications sent in this ward."""
    from app.mongodb.models.notification import NotificationMongo

    effective_ward = ward_id or current_user.ward_id
    query_filters = []
    if effective_ward:
        query_filters.append(NotificationMongo.ward_id == effective_ward)

    notifications = await NotificationMongo.find(
        *query_filters
    ).sort(-NotificationMongo.timestamp).limit(limit).to_list()

    return [
        {
            "id": str(n.id),
            "ticket_id": n.ticket_id,
            "event_type": n.event_type,
            "message_sent": n.message_sent,
            "language": n.language,
            "delivered": n.delivered,
            "timestamp": n.timestamp,
            "ward_id": n.ward_id,
        }
        for n in notifications
    ]


class WardConfigUpdate(BaseModel):
    preferred_language: Optional[str] = None       # "English" | "Tamil" | "Hindi"
    proactive_notifications_enabled: Optional[bool] = None
    ward_name: Optional[str] = None
    portal_link: Optional[str] = None


@router.get("/ward-config/{ward_id}")
async def get_ward_config(
    ward_id: int,
    current_user: UserMongo = Depends(get_current_user),
):
    """Get ward notification/language configuration."""
    from app.mongodb.models.ward_config import WardConfigMongo

    cfg = await WardConfigMongo.find_one(WardConfigMongo.ward_id == ward_id)
    if not cfg:
        return {
            "ward_id": ward_id,
            "preferred_language": "English",
            "proactive_notifications_enabled": True,
            "ward_name": f"Ward {ward_id}",
            "portal_link": "https://janvedha.gov.in",
        }
    return {
        "ward_id": cfg.ward_id,
        "preferred_language": cfg.preferred_language,
        "proactive_notifications_enabled": cfg.proactive_notifications_enabled,
        "ward_name": cfg.ward_name,
        "portal_link": cfg.portal_link,
    }


@router.patch("/ward-config/{ward_id}")
async def update_ward_config(
    ward_id: int,
    data: WardConfigUpdate,
    current_user: UserMongo = Depends(require_ward_officer),
):
    """Update ward notification preferences. Councillors and officers only."""
    from app.mongodb.models.ward_config import WardConfigMongo

    cfg = await WardConfigMongo.find_one(WardConfigMongo.ward_id == ward_id)
    if not cfg:
        from app.mongodb.models.ward_config import WardConfigMongo
        cfg = WardConfigMongo(ward_id=ward_id)

    if data.preferred_language is not None:
        if data.preferred_language not in ("English", "Tamil", "Hindi"):
            raise HTTPException(status_code=400, detail="Language must be English, Tamil, or Hindi")
        cfg.preferred_language = data.preferred_language

    if data.proactive_notifications_enabled is not None:
        cfg.proactive_notifications_enabled = data.proactive_notifications_enabled

    if data.ward_name is not None:
        cfg.ward_name = data.ward_name

    if data.portal_link is not None:
        cfg.portal_link = data.portal_link

    cfg.updated_at = datetime.utcnow()
    await cfg.save()

    return {"ward_id": ward_id, "updated": True}


# ─── Ticket notification history for citizen view ─────────────────────────────

@router.get("/notifications/ticket/{ticket_code}")
async def get_ticket_notifications(ticket_code: str):
    """Public: get notification history for a ticket (for citizen's timeline)."""
    from app.mongodb.models.ticket import TicketMongo
    from app.mongodb.models.notification import NotificationMongo

    ticket = await TicketMongo.find_one(TicketMongo.ticket_code == ticket_code)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    notifications = await NotificationMongo.find(
        NotificationMongo.ticket_id == str(ticket.id)
    ).sort(NotificationMongo.timestamp).to_list()

    EVENT_LABELS = {
        "ticket_acknowledged": "Your complaint was received",
        "technician_assigned": "Technician was assigned",
        "work_started": "Work began on your issue",
        "issue_resolved": "Issue was resolved",
    }

    return [
        {
            "event_type": n.event_type,
            "label": EVENT_LABELS.get(n.event_type, n.event_type.replace("_", " ").title()),
            "message": n.message_sent,
            "timestamp": n.timestamp,
            "delivered": n.delivered,
        }
        for n in notifications
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE 3 — Misinformation Response Assistant
# ═══════════════════════════════════════════════════════════════════════════════

def _require_councillor(current_user: UserMongo = Depends(get_current_user)) -> UserMongo:
    allowed = {UserRole.COUNCILLOR, UserRole.SUPERVISOR, UserRole.SUPER_ADMIN, UserRole.COMMISSIONER}
    if current_user.role not in allowed:
        raise HTTPException(status_code=403, detail="Councillor access required")
    return current_user


@router.get("/misinformation/flags")
async def get_misinformation_flags(
    ward_id: Optional[int] = Query(None),
    risk_level: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    current_user: UserMongo = Depends(_require_councillor),
):
    """Get flagged misinformation items for the councillor dashboard."""
    from app.mongodb.models.misinformation_flag import MisinformationFlagMongo

    effective_ward = ward_id or current_user.ward_id
    filters = []
    if effective_ward:
        filters.append(MisinformationFlagMongo.ward_id == effective_ward)
    if risk_level:
        filters.append(MisinformationFlagMongo.risk_level == risk_level)
    if status:
        filters.append(MisinformationFlagMongo.status == status)

    flags = await MisinformationFlagMongo.find(
        *filters
    ).sort(-MisinformationFlagMongo.detected_at).limit(limit).to_list()

    return [
        {
            "id": str(f.id),
            "post_text": f.post_text,
            "claim": f.claim,
            "risk_level": f.risk_level,
            "status": f.status,
            "draft_response": f.draft_response,
            "approved_response": f.approved_response,
            "detected_at": f.detected_at,
            "platform": f.platform,
            "ward_id": f.ward_id,
        }
        for f in flags
    ]


class FlagActionRequest(BaseModel):
    action: str                               # "approve" | "dismiss" | "edit"
    edited_response: Optional[str] = None    # for "edit" + "approve"


@router.patch("/misinformation/flags/{flag_id}")
async def action_misinformation_flag(
    flag_id: str,
    data: FlagActionRequest,
    current_user: UserMongo = Depends(_require_councillor),
):
    """Approve, dismiss, or edit a flagged misinformation response."""
    from app.mongodb.models.misinformation_flag import MisinformationFlagMongo
    from beanie import PydanticObjectId

    flag = await MisinformationFlagMongo.get(PydanticObjectId(flag_id))
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")

    if data.action == "dismiss":
        flag.status = "dismissed"
    elif data.action in ("approve", "edit"):
        flag.status = "approved"
        flag.approved_response = data.edited_response or flag.draft_response
    else:
        raise HTTPException(status_code=400, detail="action must be: approve | dismiss | edit")

    flag.actioned_at = datetime.utcnow()
    await flag.save()

    return {
        "id": str(flag.id),
        "status": flag.status,
        "approved_response": flag.approved_response,
    }


@router.post("/misinformation/run-check")
async def trigger_misinfo_check(
    ward_id: Optional[int] = Query(None),
    current_user: UserMongo = Depends(_require_councillor),
):
    """Manually trigger a misinformation check (normally runs every 30 min)."""
    from app.services.misinformation_detector import run_misinformation_check
    effective_ward = ward_id or current_user.ward_id
    count = await run_misinformation_check(effective_ward)
    return {"new_flags": count, "ward_id": effective_ward}


# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE 4 — Public Trust Score (Ward Report Card)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/wards/{ward_id}/trust-score")
async def get_trust_score(
    ward_id: int,
    month: Optional[str] = Query(None, description="YYYY-MM format, defaults to current month"),
):
    """
    Public endpoint: compute (or return cached) trust score for a ward.
    No auth required — this is citizen-facing.
    """
    if not month:
        now = datetime.utcnow()
        month = f"{now.year}-{now.month:02d}"

    # Validate format
    try:
        datetime.strptime(month, "%Y-%m")
    except ValueError:
        raise HTTPException(status_code=400, detail="month must be in YYYY-MM format")

    # Check for cached snapshot first
    from app.mongodb.models.trust_score import TrustScoreMongo
    cached = await TrustScoreMongo.find_one(
        TrustScoreMongo.ward_id == ward_id,
        TrustScoreMongo.month == month,
    )

    # Re-compute if no cache or if it's the current month (data may have changed)
    now = datetime.utcnow()
    current_month = f"{now.year}-{now.month:02d}"

    if cached and month != current_month:
        from app.services.trust_score_service import _build_response
        return _build_response(cached)

    from app.services.trust_score_service import compute_trust_score
    return await compute_trust_score(ward_id, month)


@router.get("/wards/{ward_id}/trust-score/history")
async def get_trust_score_history(
    ward_id: int,
    months: int = Query(6, ge=1, le=24),
):
    """Public: get last N months of trust score for sparkline chart."""
    from app.services.trust_score_service import get_trust_score_history
    return await get_trust_score_history(ward_id, months)


@router.post("/wards/{ward_id}/trust-score/insights")
async def get_trust_score_insights(
    ward_id: int,
    current_user: UserMongo = Depends(get_current_user),
):
    """Councillor: generate Gemini insight narrative for the current trust score."""
    now = datetime.utcnow()
    month = f"{now.year}-{now.month:02d}"

    from app.services.trust_score_service import compute_trust_score, generate_trust_score_insights
    score_data = await compute_trust_score(ward_id, month)
    insight = await generate_trust_score_insights(ward_id, score_data)

    return {"ward_id": ward_id, "month": month, "insight": insight, "score": score_data}

