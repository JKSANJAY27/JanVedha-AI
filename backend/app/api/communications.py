"""
Communications API — Constituent Communication Center for Ward Councillors.

Councillors describe what they want to communicate and the AI generates:
  - Formal public notice (English + Tamil)
  - WhatsApp-friendly post (English + Tamil)
  - SMS-style short update (English + Tamil, ≤160 chars each)

Routes (all under /api/communications):
  POST   /generate
  GET    /
  GET    /{comm_id}
  POST   /{comm_id}/pdf
"""
import json
import re
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.dependencies import get_current_user
from app.mongodb.models.user import UserMongo
from app.mongodb.models.ticket import TicketMongo
from app.mongodb.models.ward_communication import WardCommunicationMongo, CommInput, CommOutputs, BilingualText
from app.enums import UserRole

router = APIRouter()


# ── Auth helper ───────────────────────────────────────────────────────────────

def _require_councillor(current_user: UserMongo = Depends(get_current_user)) -> UserMongo:
    allowed = {UserRole.COUNCILLOR, UserRole.SUPERVISOR, UserRole.SUPER_ADMIN}
    if current_user.role not in allowed:
        raise HTTPException(status_code=403, detail="Councillor access required")
    return current_user


# ── Gemini helper ─────────────────────────────────────────────────────────────

def _get_gemini(temperature: float = 0.4):
    try:
        import google.generativeai as genai
        from app.core.config import settings
        genai.configure(api_key=settings.GEMINI_API_KEY)
        return genai.GenerativeModel(
            "gemini-1.5-flash",
            generation_config={"temperature": temperature},
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Gemini unavailable: {e}")


def _strip_json_fences(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


# ── Topic type labels ─────────────────────────────────────────────────────────

_TOPIC_LABELS = {
    "work_completed": "Work/issue resolution announcement",
    "upcoming_disruption": "Service disruption notice",
    "scheme_announcement": "Government scheme/program announcement",
    "ward_event": "Ward meeting or public event announcement",
    "general_update": "General ward update",
}


# ──────────────────────────────────────────────────────────────────────────────
# 1. POST /generate — AI generates all 6 format variants
# ──────────────────────────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    ward_id: str
    councillor_id: str
    councillor_name: str
    ward_name: str
    topic_type: str
    topic_summary: str
    specific_details: Optional[str] = None
    linked_ticket_id: Optional[str] = None


@router.post("/generate")
async def generate_communication(
    body: GenerateRequest,
    current_user: UserMongo = Depends(_require_councillor),
):
    """Generate all 6 format variants (3 formats × 2 languages) for a ward communication."""
    today_date = datetime.utcnow().strftime("%d %B %Y")
    topic_type_label = _TOPIC_LABELS.get(body.topic_type, "General ward update")

    # Step 1: Fetch linked ticket if provided
    ticket_context_lines = []
    ticket_snapshot = None
    if body.linked_ticket_id:
        try:
            from bson import ObjectId
            ticket = await TicketMongo.get(ObjectId(body.linked_ticket_id))
            if ticket:
                ticket_snapshot = {
                    "title": ticket.description[:100] if ticket.description else "",
                    "category": ticket.issue_category,
                    "status": ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status),
                    "created_at": ticket.created_at.strftime("%d %B %Y") if ticket.created_at else "—",
                    "resolved_at": ticket.resolved_at.strftime("%d %B %Y") if ticket.resolved_at else None,
                    "location": ticket.location_text or "",
                }
                ticket_context_lines = [
                    "LINKED CIVIC TICKET (use these real details in the communication):",
                    f"- Issue: {ticket_snapshot['title']}",
                    f"- Category: {ticket_snapshot['category']}",
                    f"- Originally reported: {ticket_snapshot['created_at']}",
                    f"- Current status: {ticket_snapshot['status']}",
                ]
                if ticket_snapshot["resolved_at"]:
                    ticket_context_lines.append(f"- Resolved on: {ticket_snapshot['resolved_at']}")
                if ticket_snapshot["location"]:
                    ticket_context_lines.append(f"- Location: {ticket_snapshot['location']}")
        except Exception:
            pass  # Proceed without ticket context

    ticket_context_block = "\n".join(ticket_context_lines) if ticket_context_lines else ""
    details_block = body.specific_details if body.specific_details else "None provided"

    prompt = f"""You are drafting official ward communications for a Ward Councillor in Tamil Nadu, India. Generate three different format versions of the same communication, each in both English and Tamil.

COUNCILLOR DETAILS:
- Name: {body.councillor_name}
- Ward: {body.ward_name}
- Date: {today_date}

COMMUNICATION TYPE: {topic_type_label}

WHAT TO COMMUNICATE:
{body.topic_summary}

ADDITIONAL DETAILS:
{details_block}

{ticket_context_block}

Generate ALL SIX versions in this exact JSON format. Do not include placeholder text — all content must be complete and ready to use.

REQUIREMENTS PER FORMAT:

formal_notice_english:
- Full formal letter format
- Opening: "PUBLIC NOTICE" header
- Date and ward reference
- 2-3 formal paragraphs
- Closing: "Yours faithfully, {body.councillor_name}, Ward Councillor, {body.ward_name}"
- Formal, official tone, 150-250 words

formal_notice_tamil:
- Same structure, fully translated to Tamil
- Use formal written Tamil (எழுத்து வழக்கு), not spoken Tamil
- Include English proper nouns in brackets after Tamil where helpful

whatsapp_post_english:
- Conversational, warm tone
- Use line breaks for readability (NO asterisks, NO bullet dashes, plain text only)
- 80-150 words
- End with councillor name

whatsapp_post_tamil:
- Same content in Tamil, natural conversational Tamil
- Same length constraint

sms_english:
- Maximum 160 characters including spaces
- Must contain: what, where (if applicable), key date (if applicable)
- No greeting or sign-off — pure information
- Count characters carefully

sms_tamil:
- Maximum 160 characters in Tamil
- Same constraints

topic_label: A 4-6 word label summarizing this communication for history display (English only)

Respond ONLY in this JSON format:
{{
  "formal_notice": {{
    "english": "...",
    "tamil": "..."
  }},
  "whatsapp_post": {{
    "english": "...",
    "tamil": "..."
  }},
  "sms": {{
    "english": "...",
    "tamil": "..."
  }},
  "topic_label": "..."
}}"""

    # Attempt Gemini generation with one retry
    parsed = None
    for attempt in range(2):
        try:
            model = _get_gemini(temperature=0.4)
            response = model.generate_content(prompt)
            raw = _strip_json_fences(response.text)
            parsed = json.loads(raw)
            break
        except (json.JSONDecodeError, Exception):
            if attempt == 1:
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error": "draft_failed",
                        "message": "Could not generate drafts. Please try again.",
                    }
                )

    if not parsed:
        raise HTTPException(status_code=500, detail={"error": "draft_failed", "message": "Generation failed."})

    # Build outputs
    outputs = CommOutputs(
        formal_notice=BilingualText(
            english=parsed.get("formal_notice", {}).get("english", ""),
            tamil=parsed.get("formal_notice", {}).get("tamil", ""),
        ),
        whatsapp_post=BilingualText(
            english=parsed.get("whatsapp_post", {}).get("english", ""),
            tamil=parsed.get("whatsapp_post", {}).get("tamil", ""),
        ),
        sms=BilingualText(
            english=parsed.get("sms", {}).get("english", ""),
            tamil=parsed.get("sms", {}).get("tamil", ""),
        ),
    )

    comm = WardCommunicationMongo(
        ward_id=body.ward_id,
        councillor_id=body.councillor_id,
        councillor_name=body.councillor_name,
        ward_name=body.ward_name,
        input=CommInput(
            topic_type=body.topic_type,  # type: ignore[arg-type]
            topic_summary=body.topic_summary,
            specific_details=body.specific_details,
            linked_ticket_id=body.linked_ticket_id,
            linked_ticket_data=ticket_snapshot,
        ),
        outputs=outputs,
        topic_label=parsed.get("topic_label", body.topic_summary[:40]),
        created_at=datetime.utcnow(),
    )
    await comm.insert()

    return {
        "comm_id": comm.comm_id,
        "outputs": {
            "formal_notice": {"english": outputs.formal_notice.english, "tamil": outputs.formal_notice.tamil},
            "whatsapp_post": {"english": outputs.whatsapp_post.english, "tamil": outputs.whatsapp_post.tamil},
            "sms": {"english": outputs.sms.english, "tamil": outputs.sms.tamil},
        },
        "topic_label": comm.topic_label,
        "created_at": comm.created_at.isoformat(),
    }


# ──────────────────────────────────────────────────────────────────────────────
# 2. GET /suggestions — AI proactive suggestions based on recent tickets
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/suggestions")
async def get_ai_suggestions(
    ward_id: str = Query(...),
    current_user: UserMongo = Depends(_require_councillor),
):
    """Proactively suggest 3 announcements based on recently resolved/active tickets."""
    # 1. Fetch recent tickets
    recent_tickets = await (
        TicketMongo.find(TicketMongo.ward_id == ward_id)
        .sort(-TicketMongo.created_at)
        .limit(10)
        .to_list()
    )

    default_suggestions = [
        {
            "title": "Ward cleanup drive completed",
            "topic_type": "work_completed",
            "summary": "The sanitation department successfully completed a ward-wide cleanup drive across all major streets yesterday.",
            "additional_details": "Residents are requested to support by segregating waste properly.",
            "linked_ticket_id": None,
            "linked_ticket_code": None
        },
        {
            "title": "Upcoming seasonal health camp",
            "topic_type": "ward_event",
            "summary": "Join us for the seasonal health and vaccination camp next weekend.",
            "additional_details": "Time: 9 AM to 4 PM. Location: Primary Health Centre, Ward 5. Please bring Aadhar card.",
            "linked_ticket_id": None,
            "linked_ticket_code": None
        },
        {
            "title": "Feedback session on civic amenities",
            "topic_type": "general_update",
            "summary": "We are organizing a public feedback session to discuss future infrastructure projects.",
            "additional_details": "Your input is valuable for the upcoming budget planning.",
            "linked_ticket_id": None,
            "linked_ticket_code": None
        }
    ]

    if not recent_tickets:
        return {"suggestions": default_suggestions}

    ticket_context = []
    for t in recent_tickets:
        status_val = t.status.value if hasattr(t.status, "value") else str(t.status)
        desc = (t.description or "")[:80] + "..."
        tid = getattr(t, "id", None) or getattr(t, "_id", None)
        tcode = getattr(t, "ticket_code", str(tid)[-6:].upper() if tid else "")
        ticket_context.append(f"ID: {str(tid)} | Code: {tcode} | Title: {desc} | Category: {t.issue_category} | Status: {status_val}")
    
    context_str = "\n".join(ticket_context)

    prompt = f"""You are an AI assistant helping a ward councillor decide what to announce to their constituents. 
Here are the recent tickets from their ward:
{context_str}

Analyze this data and suggest exactly 3 great ideas for public announcements. 
For example, if multiple tickets about streetlights were recently resolved, suggest an announcement about "Major streetlight repair works completed".
If a major water issue is active, suggest an "Upcoming water disruption" or "Current status on water pipeline repair" update.

Respond in this EXACT JSON array format (no markdown fences, just the JSON):
[
  {{
    "title": "Short catchy title (e.g. Streetlight Repairs Completed)",
    "topic_type": "One of: work_completed, upcoming_disruption, scheme_announcement, ward_event, general_update",
    "summary": "A 1-2 sentence description of what to say. Give specific details from the tickets if possible.",
    "additional_details": "Any extra context like dates, timings, locations, or call-to-actions that would be helpful.",
    "linked_ticket_id": "The exact ID string from the context if it relates strongly to one specific ticket, otherwise null",
    "linked_ticket_code": "The Code of the exact ticket linked above, from the context. Only if linked_ticket_id is used."
  }}
]
"""
    try:
        model = _get_gemini(temperature=0.6)
        response = model.generate_content(prompt)
        raw = _strip_json_fences(response.text)
        suggestions = json.loads(raw)
        # Validate structure roughly
        if isinstance(suggestions, list) and len(suggestions) > 0 and "title" in suggestions[0]:
            return {"suggestions": suggestions[:3]}
        return {"suggestions": default_suggestions}
    except Exception:
        return {"suggestions": default_suggestions}

# ──────────────────────────────────────────────────────────────────────────────
# 3. GET / — Paginated communication history
# ──────────────────────────────────────────────────────────────────────────────

@router.get("")
async def list_communications(
    ward_id: str = Query(...),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: UserMongo = Depends(_require_councillor),
):
    """Paginated list of ward communications (summary only, no full outputs)."""
    all_items = await (
        WardCommunicationMongo.find(WardCommunicationMongo.ward_id == ward_id)
        .sort(-WardCommunicationMongo.created_at)
        .to_list()
    )
    total = len(all_items)
    start = (page - 1) * limit
    items = all_items[start: start + limit]
    return {
        "total": total,
        "page": page,
        "communications": [
            {
                "comm_id": c.comm_id,
                "topic_type": c.input.topic_type,
                "topic_label": c.topic_label,
                "linked_ticket_id": c.input.linked_ticket_id,
                "created_at": c.created_at.isoformat(),
            }
            for c in items
        ],
    }


# ──────────────────────────────────────────────────────────────────────────────
# 3. GET /{comm_id} — Full detail including all outputs
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/{comm_id}")
async def get_communication(
    comm_id: str,
    current_user: UserMongo = Depends(_require_councillor),
):
    """Return full communication document with all outputs."""
    comm = await WardCommunicationMongo.find_one(WardCommunicationMongo.comm_id == comm_id)
    if not comm:
        raise HTTPException(status_code=404, detail="Communication not found")
    return {
        "comm_id": comm.comm_id,
        "ward_id": comm.ward_id,
        "councillor_name": comm.councillor_name,
        "ward_name": comm.ward_name,
        "topic_type": comm.input.topic_type,
        "topic_summary": comm.input.topic_summary,
        "specific_details": comm.input.specific_details,
        "linked_ticket_id": comm.input.linked_ticket_id,
        "topic_label": comm.topic_label,
        "outputs": {
            "formal_notice": {
                "english": comm.outputs.formal_notice.english,
                "tamil": comm.outputs.formal_notice.tamil,
            },
            "whatsapp_post": {
                "english": comm.outputs.whatsapp_post.english,
                "tamil": comm.outputs.whatsapp_post.tamil,
            },
            "sms": {
                "english": comm.outputs.sms.english,
                "tamil": comm.outputs.sms.tamil,
            },
        },
        "created_at": comm.created_at.isoformat(),
    }


# ──────────────────────────────────────────────────────────────────────────────
# 4. POST /{comm_id}/pdf — Generate & stream PDF for formal notice
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/{comm_id}/pdf")
async def download_formal_notice_pdf(
    comm_id: str,
    language: str = Query("english", pattern="^(english|tamil)$"),
    current_user: UserMongo = Depends(_require_councillor),
):
    """Generate and return a PDF for the formal notice (English or Tamil)."""
    comm = await WardCommunicationMongo.find_one(WardCommunicationMongo.comm_id == comm_id)
    if not comm:
        raise HTTPException(status_code=404, detail="Communication not found")

    text = (
        comm.outputs.formal_notice.english
        if language == "english"
        else comm.outputs.formal_notice.tamil
    )

    try:
        from fpdf import FPDF
        import io

        pdf = FPDF()
        pdf.add_page()

        # For Tamil, try to use a Unicode font; fall back to ASCII rendering
        if language == "tamil":
            import os
            font_path = os.path.join(os.path.dirname(__file__), "..", "..", "fonts", "NotoSansTamil-Regular.ttf")
            font_path = os.path.abspath(font_path)
            if os.path.exists(font_path):
                pdf.add_font("NotoTamil", "", font_path, uni=True)
                pdf.set_font("NotoTamil", size=12)
            else:
                # Fallback: header in English, body as-is (may not render Tamil)
                pdf.set_font("Helvetica", size=12)
        else:
            pdf.set_font("Helvetica", size=14, style="B")

        # Header
        pdf.set_font("Helvetica", style="B", size=14)
        pdf.cell(0, 10, "GREATER CHENNAI CORPORATION", align="C", ln=True)
        pdf.set_font("Helvetica", style="B", size=12)
        pdf.cell(0, 8, comm.ward_name.upper(), align="C", ln=True)
        pdf.ln(2)
        pdf.set_font("Helvetica", size=11, style="B")
        pdf.cell(0, 8, "PUBLIC NOTICE", align="C", ln=True)
        pdf.set_font("Helvetica", size=10)
        pdf.cell(0, 6, f"Date: {comm.created_at.strftime('%d %B %Y')}", align="R", ln=True)
        pdf.ln(2)
        # Horizontal line
        pdf.set_draw_color(100, 100, 100)
        pdf.set_line_width(0.5)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(6)

        # Body
        if language == "tamil" and "NotoTamil" in pdf.fonts if hasattr(pdf, "fonts") else False:
            pdf.set_font("NotoTamil", size=11)
        else:
            pdf.set_font("Helvetica", size=11)

        # Render text with line breaks
        for line in text.split("\n"):
            pdf.multi_cell(0, 7, line or " ")

        # Footer
        pdf.ln(10)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(3)
        pdf.set_font("Helvetica", size=9)
        pdf.cell(0, 5, f"Ward Councillor, {comm.ward_name} | JanVedha AI", align="C", ln=True)

        pdf_bytes = bytes(pdf.output())
        buf = io.BytesIO(pdf_bytes)
        buf.seek(0)

        filename = f"PublicNotice_{comm.ward_name.replace(' ', '_')}_{comm_id}_{language}.pdf"
        return StreamingResponse(
            buf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ImportError:
        raise HTTPException(status_code=500, detail="PDF library not installed. Run: pip install fpdf2")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")
