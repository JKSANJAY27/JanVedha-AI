"""
Casework API — Constituent casework log for ward councillors.

Councillors receive complaints via phone, walk-in, WhatsApp.
This router provides voice transcription, casework logging, ticket
linking, AI follow-up drafting, and escalation detection.

Routes (all under /api/casework):
  POST   /transcribe
  POST   /log
  GET    /match-tickets
  GET    /counts
  GET    /
  GET    /constituent/{phone}
  GET    /{casework_id}
  POST   /{casework_id}/link-ticket
  POST   /{casework_id}/create-ticket
  POST   /{casework_id}/draft-followup
  POST   /{casework_id}/mark-sent
"""
import base64
import json
import os
import re
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel

from app.core.dependencies import get_current_user
from app.mongodb.models.user import UserMongo
from app.mongodb.models.ticket import TicketMongo
from app.mongodb.models.casework import (
    CaseworkMongo,
    ComplaintData,
    ConstituentData,
    VoiceNoteData,
    FollowUpData,
)
from app.enums import UserRole

router = APIRouter()

# ── Auth helpers ──────────────────────────────────────────────────────────────

def _require_councillor(current_user: UserMongo = Depends(get_current_user)) -> UserMongo:
    allowed = {UserRole.COUNCILLOR, UserRole.SUPERVISOR, UserRole.SUPER_ADMIN}
    if current_user.role not in allowed:
        raise HTTPException(status_code=403, detail="Councillor access required")
    return current_user


# ── Gemini helper ─────────────────────────────────────────────────────────────

def _get_gemini():
    """Return a configured Gemini generative model (flash)."""
    try:
        import google.generativeai as genai
        from app.core.config import settings
        genai.configure(api_key=settings.GEMINI_API_KEY)
        return genai.GenerativeModel("gemini-1.5-flash")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Gemini unavailable: {e}")


# ── Phone masking ─────────────────────────────────────────────────────────────

def _mask_phone(phone: str) -> str:
    """Mask middle digits: 9876543210 → 98XXXX3210"""
    if not phone or len(phone) < 6:
        return phone
    return phone[:2] + "X" * (len(phone) - 6) + phone[-4:]


# ── STOPWORDS for fuzzy matching ──────────────────────────────────────────────

_STOPWORDS = {"the", "a", "an", "is", "in", "on", "at", "near", "road", "street", "and", "to", "of", "for"}


def _tokenize(text: str) -> set:
    words = re.findall(r"\w+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


# ──────────────────────────────────────────────────────────────────────────────
# 1. POST /transcribe — Voice note → structured extraction
# ──────────────────────────────────────────────────────────────────────────────

SUPPORTED_AUDIO_TYPES = {
    "mp3": "audio/mpeg",
    "m4a": "audio/mp4",
    "ogg": "audio/ogg",
    "wav": "audio/wav",
    "webm": "audio/webm",
}

MAX_AUDIO_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/transcribe")
async def transcribe_voice_note(
    audio_file: UploadFile = File(...),
    ward_id: str = Form(...),
    current_user: UserMongo = Depends(_require_councillor),
):
    """Transcribe a voice note and extract structured complaint data via Gemini."""
    ext = (audio_file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in SUPPORTED_AUDIO_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Audio format not supported. Please use .mp3, .m4a, .ogg, .wav, or .webm."
        )

    content = await audio_file.read()
    if len(content) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=400, detail="Audio file too large. Maximum size is 10 MB.")

    # Save to temp path
    os.makedirs("/tmp/casework_audio", exist_ok=True)
    temp_filename = f"{uuid.uuid4().hex}.{ext}"
    temp_path = f"/tmp/casework_audio/{temp_filename}"
    with open(temp_path, "wb") as f:
        f.write(content)

    mime_type = SUPPORTED_AUDIO_TYPES[ext]
    b64_audio = base64.b64encode(content).decode("utf-8")

    prompt = """Listen to this voice note from a ward councillor describing a constituent complaint they just received.

Extract the following information and respond ONLY in this JSON format:
{
  "transcript": "verbatim transcription of the audio",
  "constituent_name": "name if mentioned, else null",
  "constituent_phone": "phone number if mentioned, else null",
  "constituent_address": "address if mentioned, else null",
  "issue_description": "clear description of the complaint in English",
  "location_description": "specific location of the issue if mentioned",
  "category": "one of: roads | water | lighting | drainage | waste | scheme_enquiry | general | other",
  "urgency": "one of: low | medium | high — infer from language used",
  "how_received": "one of: walk_in | phone_call | whatsapp | other — infer if mentioned",
  "language_detected": "english | tamil | mixed"
}

If information is not present in the audio, use null for that field.
Respond with ONLY the JSON object."""

    try:
        model = _get_gemini()
        response = model.generate_content([
            {"mime_type": mime_type, "data": b64_audio},
            prompt,
        ])
        raw = response.text.strip()
        # Strip markdown code fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        extracted = json.loads(raw)
    except json.JSONDecodeError:
        # Return whatever we got as raw transcript
        extracted = {
            "transcript": raw if "raw" in dir() else "Transcription failed",
            "constituent_name": None, "constituent_phone": None,
            "constituent_address": None, "issue_description": None,
            "location_description": None, "category": None,
            "urgency": None, "how_received": None, "language_detected": None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}")

    if not extracted.get("transcript"):
        raise HTTPException(
            status_code=400,
            detail="Could not transcribe audio. Please ensure the recording is clear and try again."
        )

    return {
        "transcript": extracted.get("transcript"),
        "extracted": {
            "constituent_name": extracted.get("constituent_name"),
            "constituent_phone": extracted.get("constituent_phone"),
            "constituent_address": extracted.get("constituent_address"),
            "issue_description": extracted.get("issue_description"),
            "location_description": extracted.get("location_description"),
            "category": extracted.get("category"),
            "urgency": extracted.get("urgency"),
            "how_received": extracted.get("how_received"),
            "language_detected": extracted.get("language_detected"),
        },
        "audio_path": temp_path,
    }


# ──────────────────────────────────────────────────────────────────────────────
# 2. POST /log — Create casework entry
# ──────────────────────────────────────────────────────────────────────────────

class LogCaseworkRequest(BaseModel):
    ward_id: int
    councillor_id: str
    councillor_name: Optional[str] = None
    constituent_name: str
    constituent_phone: str
    constituent_address: Optional[str] = None
    preferred_language: str = "both"
    complaint_description: str
    complaint_category: str = "general"
    location_description: Optional[str] = None
    urgency: str = "medium"
    how_received: str = "other"
    audio_path: Optional[str] = None
    transcript: Optional[str] = None
    notes: Optional[str] = None


@router.post("/log")
async def log_casework(
    body: LogCaseworkRequest,
    current_user: UserMongo = Depends(_require_councillor),
):
    """Create a new casework entry with optional escalation detection."""
    now = datetime.utcnow()
    thirty_days_ago = now - timedelta(days=30)

    # Escalation check
    previous_count = await CaseworkMongo.find(
        CaseworkMongo.constituent.phone == body.constituent_phone,
        CaseworkMongo.ward_id == body.ward_id,
        CaseworkMongo.created_at >= thirty_days_ago,
        CaseworkMongo.complaint.category == body.complaint_category,
    ).count()

    escalation_flag = previous_count >= 2
    escalation_reason = None
    if escalation_flag:
        escalation_reason = (
            f"This constituent has raised {previous_count + 1} "
            f"{body.complaint_category} complaints in the past 30 days. "
            "Personal intervention may be needed."
        )

    casework = CaseworkMongo(
        casework_id=uuid.uuid4().hex[:10],
        ward_id=body.ward_id,
        councillor_id=body.councillor_id,
        councillor_name=body.councillor_name,
        constituent=ConstituentData(
            name=body.constituent_name,
            phone=body.constituent_phone,
            address=body.constituent_address,
            preferred_language=body.preferred_language,  # type: ignore
        ),
        complaint=ComplaintData(
            description=body.complaint_description,
            category=body.complaint_category,
            location_description=body.location_description,
            urgency=body.urgency,  # type: ignore
            how_received=body.how_received,  # type: ignore
        ),
        voice_note=VoiceNoteData(
            file_path=body.audio_path,
            transcript=body.transcript,
        ),
        status="escalated" if escalation_flag else "logged",
        escalation_flag=escalation_flag,
        escalation_reason=escalation_reason,
        notes=body.notes,
        created_at=now,
        updated_at=now,
    )

    await casework.insert()

    return {
        "casework_id": casework.casework_id,
        "status": casework.status,
        "escalation_flag": casework.escalation_flag,
        "escalation_reason": casework.escalation_reason,
        "created_at": casework.created_at,
    }


# ──────────────────────────────────────────────────────────────────────────────
# 3. GET /match-tickets — Fuzzy ticket matching
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/match-tickets")
async def match_tickets(
    ward_id: int = Query(...),
    category: str = Query(...),
    description: str = Query(...),
    current_user: UserMongo = Depends(_require_councillor),
):
    """Find 2-3 best matching open tickets for a casework item."""
    sixty_days_ago = datetime.utcnow() - timedelta(days=60)
    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    from app.enums import TicketStatus
    from importlib import import_module
    from beanie.operators import NotIn
    candidates = await TicketMongo.find(
        TicketMongo.ward_id == ward_id,
        TicketMongo.issue_category == category,
        TicketMongo.created_at >= sixty_days_ago,
        NotIn(TicketMongo.status, ["CLOSED", "REJECTED"]),
    ).to_list()

    desc_words = _tokenize(description)
    scored = []
    for ticket in candidates:
        score = 40  # category match already filtered
        ticket_words = _tokenize(ticket.description or "")
        overlap = len(ticket_words & desc_words)
        score += min(overlap * 8, 40)
        if ticket.created_at >= seven_days_ago:
            score += 20
        scored.append((score, ticket))

    scored.sort(key=lambda x: x[0], reverse=True)
    result = []
    for score, t in scored[:3]:
        if score >= 40:
            result.append({
                "ticket_id": str(t.id),
                "title": t.description[:80] if t.description else "",
                "description": t.description,
                "category": t.issue_category,
                "status": t.status.value if hasattr(t.status, "value") else str(t.status),
                "created_at": t.created_at,
                "match_score": score,
                "assigned_technician": t.assigned_officer_id or None,
            })

    return {"candidates": result}


# ──────────────────────────────────────────────────────────────────────────────
# 4. GET /counts — Badge counts for sidebar
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/counts")
async def get_casework_counts(
    ward_id: int = Query(...),
    current_user: UserMongo = Depends(_require_councillor),
):
    """Lightweight count for inbox badge."""
    total = await CaseworkMongo.find(CaseworkMongo.ward_id == ward_id).count()
    escalated = await CaseworkMongo.find(
        CaseworkMongo.ward_id == ward_id,
        CaseworkMongo.escalation_flag == True,
    ).count()
    # Needs action: logged status with no follow-up sent
    from beanie.operators import In
    logged_items = await CaseworkMongo.find(
        CaseworkMongo.ward_id == ward_id,
        In(CaseworkMongo.status, ["logged", "ticket_created"]),
    ).to_list()
    needs_action = sum(
        1 for cw in logged_items
        if not any(f.sent for f in cw.follow_ups)
    )
    return {"total": total, "escalated": escalated, "needs_action": needs_action}


# ──────────────────────────────────────────────────────────────────────────────
# 5. GET / — List casework for a ward
# ──────────────────────────────────────────────────────────────────────────────

@router.get("")
async def list_casework(
    ward_id: int = Query(...),
    status: Optional[str] = Query(None),
    escalated_only: bool = Query(False),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: UserMongo = Depends(_require_councillor),
):
    """List casework entries for a ward with filters and pagination."""
    filters = [CaseworkMongo.ward_id == ward_id]
    if status:
        filters.append(CaseworkMongo.status == status)
    if escalated_only:
        filters.append(CaseworkMongo.escalation_flag == True)

    all_items = await CaseworkMongo.find(*filters).sort(-CaseworkMongo.created_at).to_list()

    # Search filtering (in-memory for simplicity)
    if search:
        q = search.lower()
        all_items = [
            cw for cw in all_items
            if (cw.constituent.name and q in cw.constituent.name.lower())
            or (cw.complaint.description and q in cw.complaint.description.lower())
        ]

    total = len(all_items)
    start = (page - 1) * limit
    items = all_items[start : start + limit]

    return {
        "total": total,
        "page": page,
        "casework": [
            {
                "casework_id": cw.casework_id,
                "constituent_name": cw.constituent.name,
                "constituent_phone_masked": _mask_phone(cw.constituent.phone or ""),
                "complaint_category": cw.complaint.category,
                "complaint_description": (cw.complaint.description or "")[:120],
                "status": cw.status,
                "escalation_flag": cw.escalation_flag,
                "linked_ticket_id": cw.linked_ticket_id,
                "created_at": cw.created_at,
                "how_received": cw.complaint.how_received,
            }
            for cw in items
        ],
    }


# ──────────────────────────────────────────────────────────────────────────────
# 6. GET /constituent/{phone} — History for a constituent
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/constituent/{phone}")
async def get_constituent_history(
    phone: str,
    ward_id: int = Query(...),
    current_user: UserMongo = Depends(_require_councillor),
):
    """All casework for a constituent by phone number in a ward."""
    items = await CaseworkMongo.find(
        CaseworkMongo.constituent.phone == phone,
        CaseworkMongo.ward_id == ward_id,
    ).sort(-CaseworkMongo.created_at).to_list()

    escalation_active = any(cw.escalation_flag for cw in items)

    return {
        "constituent_phone": phone,
        "total_entries": len(items),
        "escalation_active": escalation_active,
        "casework": [
            {
                "casework_id": cw.casework_id,
                "complaint_category": cw.complaint.category,
                "complaint_description": (cw.complaint.description or "")[:150],
                "status": cw.status,
                "escalation_flag": cw.escalation_flag,
                "linked_ticket_id": cw.linked_ticket_id,
                "created_at": cw.created_at,
            }
            for cw in items
        ],
    }


# ──────────────────────────────────────────────────────────────────────────────
# 7. GET /{casework_id} — Single casework detail
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/{casework_id}")
async def get_casework_detail(
    casework_id: str,
    current_user: UserMongo = Depends(_require_councillor),
):
    """Full casework document including linked ticket if any."""
    cw = await CaseworkMongo.find_one(CaseworkMongo.casework_id == casework_id)
    if not cw:
        raise HTTPException(status_code=404, detail="Casework entry not found")

    doc = cw.model_dump(mode="json")
    doc["id"] = str(cw.id)

    # Attach linked ticket
    if cw.linked_ticket_id:
        try:
            from bson import ObjectId
            ticket = await TicketMongo.get(ObjectId(cw.linked_ticket_id))
            if ticket:
                doc["linked_ticket"] = {
                    "id": str(ticket.id),
                    "ticket_code": ticket.ticket_code,
                    "description": ticket.description,
                    "issue_category": ticket.issue_category,
                    "status": ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status),
                    "priority_label": ticket.priority_label.value if ticket.priority_label else None,
                    "assigned_officer_id": ticket.assigned_officer_id,
                    "created_at": str(ticket.created_at),
                    "resolved_at": str(ticket.resolved_at) if ticket.resolved_at else None,
                }
        except Exception:
            pass

    return doc


# ──────────────────────────────────────────────────────────────────────────────
# 8. POST /{casework_id}/link-ticket
# ──────────────────────────────────────────────────────────────────────────────

class LinkTicketRequest(BaseModel):
    ticket_id: str


@router.post("/{casework_id}/link-ticket")
async def link_ticket(
    casework_id: str,
    body: LinkTicketRequest,
    current_user: UserMongo = Depends(_require_councillor),
):
    """Link this casework to an existing ticket."""
    cw = await CaseworkMongo.find_one(CaseworkMongo.casework_id == casework_id)
    if not cw:
        raise HTTPException(status_code=404, detail="Casework entry not found")

    now = datetime.utcnow()
    cw.linked_ticket_id = body.ticket_id
    cw.ticket_created = False
    cw.status = "ticket_linked"
    cw.updated_at = now
    await cw.save()

    # Add councillor note to the ticket
    try:
        from bson import ObjectId
        ticket = await TicketMongo.get(ObjectId(body.ticket_id))
        if ticket:
            if not hasattr(ticket, "councillor_notes") or ticket.councillor_notes is None:
                ticket.councillor_notes = []  # type: ignore
            ticket.councillor_notes.append({  # type: ignore
                "note": f"Linked from councillor casework. Constituent: {cw.constituent.name}",
                "added_at": now.isoformat(),
                "councillor_id": str(current_user.id),
            })
            await ticket.save()
    except Exception:
        pass  # Non-fatal

    return {"success": True, "status": "ticket_linked"}


# ──────────────────────────────────────────────────────────────────────────────
# 9. POST /{casework_id}/create-ticket
# ──────────────────────────────────────────────────────────────────────────────

class CreateTicketRequest(BaseModel):
    title: Optional[str] = None


_URGENCY_TO_PRIORITY = {"high": "HIGH", "medium": "MEDIUM", "low": "LOW"}


@router.post("/{casework_id}/create-ticket")
async def create_ticket_from_casework(
    casework_id: str,
    body: CreateTicketRequest,
    current_user: UserMongo = Depends(_require_councillor),
):
    """Create a new ticket from this casework entry."""
    cw = await CaseworkMongo.find_one(CaseworkMongo.casework_id == casework_id)
    if not cw:
        raise HTTPException(status_code=404, detail="Casework entry not found")

    title = body.title
    if not title:
        try:
            model = _get_gemini()
            r = model.generate_content(
                f"Generate a concise 8-10 word ticket title for this civic complaint: "
                f"{cw.complaint.description}. Respond with only the title, no punctuation at the end."
            )
            title = r.text.strip().rstrip(".")
        except Exception:
            title = (cw.complaint.description or "Civic complaint")[:80]

    now = datetime.utcnow()
    import uuid as _uuid
    from app.enums import TicketSource, TicketStatus, PriorityLabel

    ticket_code = f"CW-{_uuid.uuid4().hex[:6].upper()}"
    priority_str = _URGENCY_TO_PRIORITY.get(cw.complaint.urgency, "MEDIUM")

    new_ticket = TicketMongo(
        ticket_code=ticket_code,
        source=TicketSource.WEB_PORTAL,
        description=cw.complaint.description,
        dept_id=cw.complaint.category or "general",
        issue_category=cw.complaint.category,
        ward_id=cw.ward_id,
        location_text=cw.complaint.location_description,
        reporter_name=cw.constituent.name,
        reporter_phone=cw.constituent.phone,
        priority_label=PriorityLabel[priority_str],
        status=TicketStatus.OPEN,
        created_at=now,
    )
    await new_ticket.insert()

    ticket_id = str(new_ticket.id)
    cw.linked_ticket_id = ticket_id
    cw.ticket_created = True
    cw.status = "ticket_created"
    cw.updated_at = now
    await cw.save()

    return {
        "success": True,
        "ticket_id": ticket_id,
        "ticket_code": ticket_code,
        "ticket_title": title,
        "status": "ticket_created",
    }


# ──────────────────────────────────────────────────────────────────────────────
# 10. POST /{casework_id}/draft-followup
# ──────────────────────────────────────────────────────────────────────────────

class DraftFollowUpRequest(BaseModel):
    language: str = "both"


@router.post("/{casework_id}/draft-followup")
async def draft_followup(
    casework_id: str,
    body: DraftFollowUpRequest,
    current_user: UserMongo = Depends(_require_councillor),
):
    """Generate an AI-drafted follow-up message in English and/or Tamil."""
    cw = await CaseworkMongo.find_one(CaseworkMongo.casework_id == casework_id)
    if not cw:
        raise HTTPException(status_code=404, detail="Casework entry not found")

    # Build ticket context
    ticket_context = "No ticket has been created yet."
    if cw.linked_ticket_id:
        try:
            from bson import ObjectId
            ticket = await TicketMongo.get(ObjectId(cw.linked_ticket_id))
            if ticket:
                status_str = ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status)
                officer_str = ticket.assigned_officer_id or "pending assignment"
                ticket_context = (
                    f"A ticket has been filed (Code: {ticket.ticket_code}). "
                    f"Current status: {status_str}. "
                    f"Assigned to: {officer_str}. "
                    f"Category: {ticket.issue_category}. "
                    f"Filed on: {ticket.created_at.strftime('%d %b %Y')}."
                )
        except Exception:
            pass

    name = cw.constituent.name or "Constituent"
    prompt = f"""You are drafting a follow-up message from a Ward Councillor to a constituent who raised a civic complaint.

Context:
- Constituent name: {name}
- Complaint: {cw.complaint.description}
- Location mentioned: {cw.complaint.location_description or 'not specified'}
- Urgency: {cw.complaint.urgency}
- Ticket/action status: {ticket_context}
- Councillor name: {cw.councillor_name or 'Your Councillor'}

Draft TWO versions of a follow-up message:
1. An English version — warm, reassuring, specific. Should mention the specific complaint and what action has been taken or will be taken. If a ticket is filed, mention it. Keep it under 80 words. WhatsApp-friendly (no bullet points). End with the councillor's name.

2. A Tamil version — translate the same message faithfully into Tamil. Use respectful, formal Tamil (நீங்கள் form). Localize naturally — do not literal-translate English phrases that sound unnatural in Tamil.

Respond ONLY in this JSON format:
{{
  "english": "...",
  "tamil": "..."
}}

Important: The message must be grounded in the actual ticket status provided. Do not promise outcomes that haven't been confirmed. Use phrases like "will be attended to" rather than "is being fixed" if work hasn't started."""

    english_text = None
    tamil_text = None
    is_fallback = False

    try:
        import google.generativeai as genai
        from app.core.config import settings
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(
            "gemini-1.5-flash",
            generation_config={"temperature": 0.4},
        )
        response = model.generate_content(prompt)
        raw = response.text.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        parsed = json.loads(raw)
        english_text = parsed.get("english")
        tamil_text = parsed.get("tamil")
    except Exception:
        is_fallback = True
        councillor = cw.councillor_name or "Your Councillor"
        category = cw.complaint.category or "civic issue"
        english_text = (
            f"Dear {name}, Thank you for bringing this matter to my attention. "
            f"I have recorded your complaint regarding {category} and will ensure "
            f"it receives prompt attention. - {councillor}"
        )
        tamil_text = (
            f"அன்புள்ள {name}, உங்கள் பிரச்சனையை என்னிடம் தெரிவித்தமைக்கு நன்றி. "
            f"உங்கள் புகாரை பதிவு செய்துள்ளேன். விரைவில் நடவடிக்கை எடுக்கப்படும். "
            f"- {councillor}"
        )

    now = datetime.utcnow()
    follow_up_id = uuid.uuid4().hex[:8]
    follow_up = FollowUpData(
        follow_up_id=follow_up_id,
        generated_at=now,
        language=body.language,  # type: ignore
        english_text=english_text,
        tamil_text=tamil_text,
        sent=False,
    )
    cw.follow_ups.append(follow_up)
    cw.updated_at = now
    await cw.save()

    return {
        "follow_up_id": follow_up_id,
        "english": english_text,
        "tamil": tamil_text,
        "generated_at": now,
        "is_fallback": is_fallback,
    }


# ──────────────────────────────────────────────────────────────────────────────
# 11. POST /{casework_id}/mark-sent
# ──────────────────────────────────────────────────────────────────────────────

class MarkSentRequest(BaseModel):
    follow_up_id: str
    sent_via: str = "whatsapp_manual"


@router.post("/{casework_id}/mark-sent")
async def mark_followup_sent(
    casework_id: str,
    body: MarkSentRequest,
    current_user: UserMongo = Depends(_require_councillor),
):
    """Mark a follow-up message as sent to the constituent."""
    cw = await CaseworkMongo.find_one(CaseworkMongo.casework_id == casework_id)
    if not cw:
        raise HTTPException(status_code=404, detail="Casework entry not found")

    now = datetime.utcnow()
    found = False
    for fu in cw.follow_ups:
        if fu.follow_up_id == body.follow_up_id:
            fu.sent = True
            fu.sent_at = now
            fu.sent_via = body.sent_via  # type: ignore
            found = True
            break

    if not found:
        raise HTTPException(status_code=404, detail="Follow-up not found")

    cw.status = "follow_up_sent"
    cw.updated_at = now
    await cw.save()

    return {"success": True}
