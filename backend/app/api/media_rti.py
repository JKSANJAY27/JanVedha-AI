"""
Media & RTI Response Assistant API

Helps councillors respond to media queries and RTI applications using
real ticket data from the ward. Gemini identifies what data is needed,
queries MongoDB, and drafts a grounded formal response.

Routes (all under /api/media-rti):
  POST   /analyze-query
  POST   /generate
  POST   /{response_id}/generate-pdf
  GET    /
  GET    /{response_id}
  POST   /extract-query-from-image
"""
import base64
import json
import re
import uuid
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.dependencies import get_current_user
from app.mongodb.models.user import UserMongo
from app.mongodb.models.ticket import TicketMongo
from app.mongodb.models.media_rti_response import (
    MediaRtiResponseMongo,
    QueryInput,
    DataAnalysis,
    DataPoint,
    ResponseOutput,
    MediaOutputContent,
    RtiOutputContent,
    RtiDocument,
    RtiDocumentHeader,
    RtiInfoItem,
    RtiNotAvailableItem,
    RtiSignatureBlock,
)
from app.enums import UserRole

router = APIRouter()


# ── Auth helper ───────────────────────────────────────────────────────────────

def _require_councillor(current_user: UserMongo = Depends(get_current_user)) -> UserMongo:
    allowed = {UserRole.COUNCILLOR, UserRole.SUPERVISOR, UserRole.SUPER_ADMIN}
    if current_user.role not in allowed:
        raise HTTPException(status_code=403, detail="Councillor access required")
    return current_user


# ── Gemini helper ─────────────────────────────────────────────────────────────

def _get_gemini(temperature: float = 0.3):
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


# ── Data query engine ─────────────────────────────────────────────────────────

async def get_ticket_stats(
    ward_id: str,
    category: Optional[str] = None,
    status_filter: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> dict:
    """
    Aggregate ticket statistics for a ward with optional filters.
    Returns counts, resolution rate, avg resolution days, etc.
    """
    filters = []

    # Ward filter — handle both int and str ward_id
    try:
        ward_int = int(ward_id)
        filters.append(TicketMongo.ward_id == ward_int)
    except (ValueError, TypeError):
        filters.append(TicketMongo.ward_id == ward_id)

    if category and category not in ("all", "null"):
        filters.append(TicketMongo.issue_category == category)

    if date_from:
        filters.append(TicketMongo.created_at >= date_from)
    if date_to:
        filters.append(TicketMongo.created_at <= date_to)

    tickets = await TicketMongo.find(*filters).to_list()

    total = len(tickets)
    resolved_tickets = [t for t in tickets if hasattr(t.status, "value") and t.status.value in ("RESOLVED", "CLOSED") or str(t.status) in ("RESOLVED", "CLOSED")]
    open_tickets = [t for t in tickets if hasattr(t.status, "value") and t.status.value == "OPEN" or str(t.status) == "OPEN"]
    in_progress = [t for t in tickets if hasattr(t.status, "value") and t.status.value == "IN_PROGRESS" or str(t.status) == "IN_PROGRESS"]

    # Apply status filter after fetching (since status filter is broad)
    if status_filter and status_filter not in ("all", "null"):
        if status_filter == "resolved":
            tickets_for_count = resolved_tickets
        elif status_filter == "open":
            tickets_for_count = open_tickets
        elif status_filter == "in_progress":
            tickets_for_count = in_progress
        else:
            tickets_for_count = tickets
    else:
        tickets_for_count = tickets

    # Resolution time for resolved tickets
    resolution_times = []
    for t in resolved_tickets:
        if t.resolved_at and t.created_at:
            days = (t.resolved_at - t.created_at).days
            if days >= 0:
                resolution_times.append(days)

    resolved_within_30 = sum(1 for d in resolution_times if d <= 30)

    # Category breakdown
    by_category: dict = {}
    for t in tickets:
        cat = t.issue_category or "other"
        by_category[cat] = by_category.get(cat, 0) + 1

    # Oldest open ticket
    now = datetime.utcnow()
    open_days = []
    for t in open_tickets:
        if t.created_at:
            open_days.append((now - t.created_at).days)

    avg_res = round(sum(resolution_times) / len(resolution_times), 1) if resolution_times else None
    res_rate = round((len(resolved_tickets) / total * 100), 1) if total > 0 else 0.0

    date_range = {}
    if date_from:
        date_range["from"] = date_from.strftime("%d %b %Y")
    if date_to:
        date_range["to"] = date_to.strftime("%d %b %Y")

    return {
        "total_count": len(tickets_for_count) if status_filter and status_filter not in ("all", "null") else total,
        "resolved_count": len(resolved_tickets),
        "open_count": len(open_tickets),
        "in_progress_count": len(in_progress),
        "resolution_rate_pct": res_rate,
        "avg_resolution_days": avg_res,
        "resolved_within_30_days": resolved_within_30,
        "by_category": by_category,
        "oldest_open_ticket_days": max(open_days) if open_days else None,
        "date_range": date_range,
    }


def _time_period_to_dates(time_period: Optional[str]):
    now = datetime.utcnow()
    mapping = {
        "last_30_days": now - timedelta(days=30),
        "last_6_months": now - timedelta(days=180),
        "last_year": now - timedelta(days=365),
    }
    return mapping.get(time_period or "", None)


# ──────────────────────────────────────────────────────────────────────────────
# 1. POST /analyze-query — Parse query and retrieve real data
# ──────────────────────────────────────────────────────────────────────────────

class AnalyzeQueryRequest(BaseModel):
    ward_id: str
    query_text: str
    type: str  # "media" | "rti"


@router.post("/analyze-query")
async def analyze_query(
    body: AnalyzeQueryRequest,
    current_user: UserMongo = Depends(_require_councillor),
):
    """Parse query intent and retrieve real ward data to ground the response."""
    prompt = f"""A ward councillor has received the following {body.type} query:

"{body.query_text}"

Your task is to identify what factual data from the municipal ticket system would be needed to answer this query accurately.

The ticket system contains:
- Civic complaint tickets with categories: roads, water, lighting, drainage, waste, other
- Each ticket has: status (open/in_progress/resolved), created_at date, resolved_at date (if resolved), resolution time in days
- Data spans the current ward only

Extract the data requirements and respond in this JSON format:
{{
  "query_intent": "One sentence describing what is being asked",
  "is_answerable_from_ticket_data": true,
  "data_requests": [
    {{
      "description": "Human readable description of what data is needed",
      "category": "roads | water | lighting | drainage | waste | other | all | null",
      "status_filter": "resolved | open | in_progress | all",
      "time_period": "last_30_days | last_6_months | last_year | all_time | null",
      "metric": "count | resolution_rate | avg_resolution_time | oldest_open"
    }}
  ],
  "outside_scope": [
    "List of things being asked that cannot be answered from ticket data (budget, staff, procurement, etc.)"
  ],
  "sensitivity_flag": false,
  "sensitivity_note": null
}}

Respond with ONLY the JSON."""

    try:
        model = _get_gemini()
        response = model.generate_content(prompt)
        raw = _strip_json_fences(response.text)
        analysis_raw = json.loads(raw)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Could not analyze query. Try simplifying the question or check it contains a clear information request. Error: {e}"
        )

    # Fetch real data for each data request
    data_points = []
    for req in analysis_raw.get("data_requests", []):
        date_from = _time_period_to_dates(req.get("time_period"))
        category = req.get("category")
        if category in ("all", "null", None):
            category = None
        status_filter = req.get("status_filter", "all")
        try:
            stats = await get_ticket_stats(
                ward_id=body.ward_id,
                category=category,
                status_filter=status_filter,
                date_from=date_from,
            )
            data_points.append({
                "description": req.get("description", ""),
                "data": stats,
            })
        except Exception:
            data_points.append({
                "description": req.get("description", ""),
                "data": {"error": "Could not retrieve data"},
            })

    return {
        "query_intent": analysis_raw.get("query_intent", ""),
        "is_answerable": analysis_raw.get("is_answerable_from_ticket_data", True),
        "data_points": data_points,
        "outside_scope": analysis_raw.get("outside_scope", []),
        "sensitivity_flag": analysis_raw.get("sensitivity_flag", False),
        "sensitivity_note": analysis_raw.get("sensitivity_note"),
    }


# ──────────────────────────────────────────────────────────────────────────────
# 2. POST /generate — Generate full drafted response
# ──────────────────────────────────────────────────────────────────────────────

class GenerateResponseRequest(BaseModel):
    ward_id: str
    councillor_id: str
    councillor_name: str
    ward_name: str
    type: str  # "media" | "rti"
    query_text: str
    query_source: Optional[str] = None
    date_received: Optional[str] = None  # ISO date string
    rti_application_number: Optional[str] = None
    tone_preference: Optional[str] = None  # data_forward | empathetic | firm
    data_analysis: Optional[dict] = None


@router.post("/generate")
async def generate_response(
    body: GenerateResponseRequest,
    current_user: UserMongo = Depends(_require_councillor),
):
    """Generate full drafted response for a media or RTI query."""
    today_date = datetime.utcnow().strftime("%d %B %Y")

    # If no data_analysis provided, compute it
    if not body.data_analysis:
        try:
            analysis_req = AnalyzeQueryRequest(
                ward_id=body.ward_id,
                query_text=body.query_text,
                type=body.type,
            )
            body.data_analysis = await analyze_query(analysis_req, current_user)
        except Exception:
            body.data_analysis = {
                "query_intent": "",
                "is_answerable": False,
                "data_points": [],
                "outside_scope": [],
                "sensitivity_flag": False,
                "sensitivity_note": None,
            }

    da = body.data_analysis
    data_points_json = json.dumps(da.get("data_points", []), indent=2, default=str)
    outside_scope = da.get("outside_scope", [])
    sensitivity_flag = da.get("sensitivity_flag", False)
    sensitivity_note = da.get("sensitivity_note")

    parsed = None

    # ── MEDIA response ─────────────────────────────────────────────────────
    if body.type == "media":
        tone_map = {
            "data_forward": "Lead with statistics. Let the numbers make the case. Minimal editorializing.",
            "empathetic": "Acknowledge any genuine concern, then show what action has been taken. Constructive tone.",
            "firm": "Directly address and correct any inaccurate premise in the query using the data. Professional but assertive.",
        }
        tone_instruction = tone_map.get(body.tone_preference or "data_forward", tone_map["data_forward"])
        sensitivity_block = ""
        if sensitivity_flag:
            sensitivity_block = f"""SENSITIVITY NOTE: {sensitivity_note}
Handle this carefully — acknowledge the concern without admitting wrongdoing unless the data clearly shows a failure."""

        source_str = f"From: {body.query_source}" if body.query_source else ""
        prompt = f"""You are helping Ward Councillor {body.councillor_name} ({body.ward_name}) respond to a media query.

MEDIA QUERY RECEIVED:
"{body.query_text}"
{source_str}

REAL DATA FROM THE WARD TICKET SYSTEM:
{data_points_json}

DATA OUTSIDE SYSTEM SCOPE (acknowledge but do not fabricate):
{json.dumps(outside_scope)}

{sensitivity_block}

TONE: {tone_instruction}

Generate a media response with these four parts:

1. quotable_statement: A 1-2 sentence direct quote the councillor can give to the journalist. Specific, factual, quotable. Must reference actual numbers from the data provided.

2. supporting_data_points: 3-4 bullet points of key statistics from the data. Format as plain strings, no markdown.

3. full_response_letter: Complete formal response letter addressed to the journalist/outlet.
- Date: {today_date}
- "Dear {body.query_source or 'Media Representative'},"
- 2-3 paragraphs: acknowledge the query, provide factual response with data, close constructively
- Sign-off: "{body.councillor_name}, Ward Councillor, {body.ward_name}"
- 200-300 words

4. data_gaps_note: If any part cannot be answered from available data, a brief honest note. Null if everything is covered.

Respond in this JSON format:
{{
  "quotable_statement": "...",
  "supporting_data_points": ["...", "...", "..."],
  "full_response_letter": "...",
  "data_gaps_note": "..." 
}}

Use ONLY the data provided. Do not fabricate statistics."""

        try:
            model = _get_gemini(temperature=0.3)
            response = model.generate_content(prompt)
            raw = _strip_json_fences(response.text)
            parsed = json.loads(raw)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to generate media response: {e}")

        output = ResponseOutput(
            media_response=MediaOutputContent(
                quotable_statement=parsed.get("quotable_statement"),
                supporting_data_points=parsed.get("supporting_data_points", []),
                full_response_letter=parsed.get("full_response_letter"),
                data_gaps_note=parsed.get("data_gaps_note"),
            )
        )

    # ── RTI response ───────────────────────────────────────────────────────
    else:
        date_received_str = body.date_received or "Not specified"
        app_num = body.rti_application_number or "To be assigned"
        applicant = body.query_source or "RTI Applicant"

        # Calculate deadline
        deadline_str = "Within 30 days of receipt"
        if body.date_received:
            try:
                dr = datetime.fromisoformat(body.date_received)
                deadline_str = (dr + timedelta(days=30)).strftime("%d %B %Y")
            except Exception:
                pass

        prompt = f"""You are helping Ward Councillor {body.councillor_name} draft a formal RTI (Right to Information Act 2005) response.

COUNCILLOR: {body.councillor_name}
WARD: {body.ward_name}
DATE RESPONSE DRAFTED: {today_date}
DATE APPLICATION RECEIVED: {date_received_str}
RTI APPLICATION NUMBER: {app_num}
RESPONSE DEADLINE: {deadline_str}

RTI APPLICATION TEXT:
"{body.query_text}"

APPLICANT: {applicant}

REAL DATA AVAILABLE FROM WARD TICKET SYSTEM:
{data_points_json}

INFORMATION NOT AVAILABLE IN SYSTEM:
{json.dumps(outside_scope)}

Draft a complete RTI response document following RTI Act 2005 format conventions used in Tamil Nadu municipal corporations.

Generate in this JSON format:
{{
  "rti_response_document": {{
    "header": {{
      "office_name": "Office of the Ward Councillor, {body.ward_name}",
      "application_number": "{app_num}",
      "date_of_receipt": "{date_received_str}",
      "date_of_response": "{today_date}",
      "response_deadline": "{deadline_str}"
    }},
    "applicant_reference": "Dear {applicant},",
    "acknowledgment_paragraph": "One formal sentence acknowledging receipt of the RTI application.",
    "information_provided": [
      {{
        "query_item": "What was requested (quote from application)",
        "response": "The factual answer using ONLY the data provided above. Include specific numbers.",
        "data_basis": "Municipal complaint ticket records"
      }}
    ],
    "information_not_held": [
      {{
        "query_item": "What was requested",
        "reason": "This information is not held by the ward office / falls outside scope of ward-level records."
      }}
    ],
    "closing_paragraph": "Standard RTI closing with right to appeal, first appellate authority reference.",
    "signature_block": {{
      "name": "{body.councillor_name}",
      "designation": "Ward Councillor & Public Information Officer",
      "ward": "{body.ward_name}",
      "date": "{today_date}"
    }}
  }},
  "internal_note": "Brief note for councillor only — anything to verify before signing."
}}

CRITICAL:
- Do not include individual citizen names or personal information (RTI is a public document).
- Do not fabricate statistics. State unavailability clearly in information_not_held if data is insufficient.
- Use formal government document language throughout."""

        try:
            model = _get_gemini(temperature=0.2)
            response = model.generate_content(prompt)
            raw = _strip_json_fences(response.text)
            parsed = json.loads(raw)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to generate RTI response: {e}")

        rti_doc_raw = parsed.get("rti_response_document", {})
        header_raw = rti_doc_raw.get("header", {})
        sig_raw = rti_doc_raw.get("signature_block", {})

        output = ResponseOutput(
            rti_response=RtiOutputContent(
                rti_response_document=RtiDocument(
                    header=RtiDocumentHeader(
                        office_name=header_raw.get("office_name", ""),
                        application_number=header_raw.get("application_number", app_num),
                        date_of_receipt=header_raw.get("date_of_receipt", date_received_str),
                        date_of_response=header_raw.get("date_of_response", today_date),
                        response_deadline=header_raw.get("response_deadline", deadline_str),
                    ),
                    applicant_reference=rti_doc_raw.get("applicant_reference", f"Dear {applicant},"),
                    acknowledgment_paragraph=rti_doc_raw.get("acknowledgment_paragraph", ""),
                    information_provided=[
                        RtiInfoItem(
                            query_item=item.get("query_item", ""),
                            response=item.get("response", ""),
                            data_basis=item.get("data_basis"),
                        )
                        for item in rti_doc_raw.get("information_provided", [])
                    ],
                    information_not_held=[
                        RtiNotAvailableItem(
                            query_item=item.get("query_item", ""),
                            reason=item.get("reason", ""),
                        )
                        for item in rti_doc_raw.get("information_not_held", [])
                    ],
                    closing_paragraph=rti_doc_raw.get("closing_paragraph", ""),
                    signature_block=RtiSignatureBlock(
                        name=sig_raw.get("name", body.councillor_name),
                        designation=sig_raw.get("designation", "Ward Councillor & Public Information Officer"),
                        ward=sig_raw.get("ward", body.ward_name),
                        date=sig_raw.get("date", today_date),
                    ),
                ),
                internal_note=parsed.get("internal_note"),
            )
        )

    # Save to MongoDB
    data_points_objs = [
        DataPoint(description=dp.get("description", ""), data=dp.get("data", {}))
        for dp in da.get("data_points", [])
    ]

    record = MediaRtiResponseMongo(
        ward_id=body.ward_id,
        councillor_id=body.councillor_id,
        councillor_name=body.councillor_name,
        ward_name=body.ward_name,
        type=body.type,  # type: ignore[arg-type]
        input=QueryInput(
            query_text=body.query_text,
            query_source=body.query_source,
            rti_application_number=body.rti_application_number,
            tone_preference=body.tone_preference,  # type: ignore[arg-type]
        ),
        data_analysis=DataAnalysis(
            query_intent=da.get("query_intent"),
            is_answerable=da.get("is_answerable", True),
            data_points=data_points_objs,
            outside_scope=outside_scope,
            sensitivity_flag=sensitivity_flag,
            sensitivity_note=sensitivity_note,
        ),
        output=output,
        created_at=datetime.utcnow(),
    )
    await record.insert()

    return {
        "response_id": record.response_id,
        "type": body.type,
        "output": _serialize_output(output, body.type),
        "created_at": record.created_at.isoformat(),
    }


def _serialize_output(output: ResponseOutput, rtype: str) -> dict:
    if rtype == "media" and output.media_response:
        m = output.media_response
        return {
            "quotable_statement": m.quotable_statement,
            "supporting_data_points": m.supporting_data_points,
            "full_response_letter": m.full_response_letter,
            "data_gaps_note": m.data_gaps_note,
        }
    elif rtype == "rti" and output.rti_response:
        r = output.rti_response
        doc = r.rti_response_document
        if not doc:
            return {}
        return {
            "rti_response_document": {
                "header": doc.header.model_dump(),
                "applicant_reference": doc.applicant_reference,
                "acknowledgment_paragraph": doc.acknowledgment_paragraph,
                "information_provided": [i.model_dump() for i in doc.information_provided],
                "information_not_held": [i.model_dump() for i in doc.information_not_held],
                "closing_paragraph": doc.closing_paragraph,
                "signature_block": doc.signature_block.model_dump(),
            },
            "internal_note": r.internal_note,
        }
    return {}


# ──────────────────────────────────────────────────────────────────────────────
# 3. POST /{response_id}/generate-pdf — PDF for RTI response
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/{response_id}/generate-pdf")
async def generate_rti_pdf(
    response_id: str,
    current_user: UserMongo = Depends(_require_councillor),
):
    """Generate and stream a properly formatted RTI PDF document."""
    record = await MediaRtiResponseMongo.find_one(
        MediaRtiResponseMongo.response_id == response_id
    )
    if not record:
        raise HTTPException(status_code=404, detail="Response not found")
    if record.type != "rti" or not record.output.rti_response:
        raise HTTPException(status_code=400, detail="This endpoint is for RTI responses only")

    try:
        from fpdf import FPDF
        import io

        doc = record.output.rti_response.rti_response_document
        if not doc:
            raise HTTPException(status_code=500, detail="RTI document data not found")

        pdf = FPDF()
        pdf.add_page()
        pdf.set_margins(15, 15, 15)

        # ── LETTERHEAD ─────────────────────────────────────────────────
        # Logo placeholder (simple rectangle)
        pdf.set_fill_color(30, 100, 60)
        pdf.rect(15, 15, 20, 12, "F")
        pdf.set_font("Helvetica", style="B", size=8)
        pdf.set_text_color(255, 255, 255)
        pdf.set_xy(15, 17)
        pdf.cell(20, 8, "GCC", align="C")
        pdf.set_text_color(0, 0, 0)

        pdf.set_xy(40, 15)
        pdf.set_font("Helvetica", style="B", size=13)
        pdf.cell(0, 6, "OFFICE OF THE WARD COUNCILLOR", ln=True)
        pdf.set_xy(40, 22)
        pdf.set_font("Helvetica", style="B", size=11)
        pdf.cell(0, 6, record.ward_name.upper(), ln=True)

        pdf.set_y(30)
        pdf.set_line_width(0.5)
        pdf.set_draw_color(100, 100, 100)
        pdf.line(15, pdf.get_y(), 195, pdf.get_y())
        pdf.ln(5)

        # ── REFERENCE / DATES TABLE ────────────────────────────────────
        pdf.set_font("Helvetica", size=9)
        labels = [
            ("Application No:", doc.header.application_number),
            ("Date Received:", doc.header.date_of_receipt),
            ("Date of Response:", doc.header.date_of_response),
            ("Response Deadline:", doc.header.response_deadline),
        ]
        for lbl, val in labels:
            pdf.set_font("Helvetica", style="B", size=9)
            pdf.cell(55, 5, lbl)
            pdf.set_font("Helvetica", size=9)
            pdf.cell(0, 5, val, ln=True)
        pdf.ln(4)

        # ── HEADING ────────────────────────────────────────────────────
        pdf.set_line_width(0.3)
        pdf.line(15, pdf.get_y(), 195, pdf.get_y())
        pdf.ln(4)
        pdf.set_font("Helvetica", style="B", size=11)
        pdf.multi_cell(0, 7, "RESPONSE TO APPLICATION UNDER RIGHT TO INFORMATION ACT, 2005", align="C")
        pdf.line(15, pdf.get_y(), 195, pdf.get_y())
        pdf.ln(6)

        # ── BODY ───────────────────────────────────────────────────────
        pdf.set_font("Helvetica", size=10)
        pdf.multi_cell(0, 6, doc.applicant_reference)
        pdf.ln(2)
        pdf.multi_cell(0, 6, doc.acknowledgment_paragraph)
        pdf.ln(4)

        if doc.information_provided:
            pdf.set_font("Helvetica", style="B", size=10)
            pdf.cell(0, 7, "INFORMATION PROVIDED:", ln=True)
            pdf.ln(1)
            for idx, item in enumerate(doc.information_provided, 1):
                pdf.set_font("Helvetica", style="B", size=9)
                pdf.multi_cell(0, 6, f"{idx}. {item.query_item}")
                pdf.set_font("Helvetica", size=9)
                pdf.set_x(20)
                pdf.multi_cell(175, 6, item.response)
                if item.data_basis:
                    pdf.set_x(20)
                    pdf.set_font("Helvetica", style="I", size=8)
                    pdf.set_text_color(100, 100, 100)
                    pdf.multi_cell(175, 5, f"Source: {item.data_basis}")
                    pdf.set_text_color(0, 0, 0)
                pdf.ln(3)

        if doc.information_not_held:
            pdf.set_font("Helvetica", style="B", size=10)
            pdf.cell(0, 7, "INFORMATION NOT AVAILABLE:", ln=True)
            pdf.ln(1)
            for idx, item in enumerate(doc.information_not_held, 1):
                pdf.set_font("Helvetica", style="B", size=9)
                pdf.multi_cell(0, 6, f"{idx}. {item.query_item}")
                pdf.set_font("Helvetica", size=9)
                pdf.set_x(20)
                pdf.multi_cell(175, 6, item.reason)
                pdf.ln(2)

        pdf.ln(2)
        pdf.set_font("Helvetica", size=10)
        pdf.multi_cell(0, 6, doc.closing_paragraph)
        pdf.ln(6)

        # ── SIGNATURE ──────────────────────────────────────────────────
        sig = doc.signature_block
        pdf.set_font("Helvetica", style="B", size=10)
        pdf.cell(0, 6, sig.name, ln=True)
        pdf.set_font("Helvetica", size=9)
        pdf.cell(0, 5, sig.designation, ln=True)
        pdf.cell(0, 5, sig.ward, ln=True)
        pdf.cell(0, 5, sig.date, ln=True)

        # ── FOOTER ─────────────────────────────────────────────────────
        pdf.set_y(-20)
        pdf.set_line_width(0.3)
        pdf.line(15, pdf.get_y(), 195, pdf.get_y())
        pdf.ln(2)
        pdf.set_font("Helvetica", style="I", size=7)
        pdf.set_text_color(130, 130, 130)
        pdf.cell(0, 5, "Draft prepared with JanVedha AI assistance | Verify before signing", align="C", ln=True)

        pdf_bytes = bytes(pdf.output())
        buf = io.BytesIO(pdf_bytes)
        buf.seek(0)

        filename = f"RTI_Response_{record.ward_name.replace(' ', '_')}_{response_id}.pdf"
        return StreamingResponse(
            buf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except ImportError:
        raise HTTPException(status_code=500, detail="PDF library not installed. Run: pip install fpdf2")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# 4. GET / — Paginated history
# ──────────────────────────────────────────────────────────────────────────────

@router.get("")
async def list_responses(
    ward_id: str = Query(...),
    type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: UserMongo = Depends(_require_councillor),
):
    """Paginated history of media/RTI responses for a ward."""
    filters = [MediaRtiResponseMongo.ward_id == ward_id]
    if type and type in ("media", "rti"):
        filters.append(MediaRtiResponseMongo.type == type)

    all_items = await (
        MediaRtiResponseMongo.find(*filters)
        .sort(-MediaRtiResponseMongo.created_at)
        .to_list()
    )
    total = len(all_items)
    start = (page - 1) * limit
    items = all_items[start: start + limit]

    return {
        "total": total,
        "page": page,
        "responses": [
            {
                "response_id": r.response_id,
                "type": r.type,
                "query_text": r.input.query_text[:100],
                "query_source": r.input.query_source,
                "created_at": r.created_at.isoformat(),
            }
            for r in items
        ],
    }


# ──────────────────────────────────────────────────────────────────────────────
# 5. GET /{response_id} — Single response detail
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/{response_id}")
async def get_response(
    response_id: str,
    current_user: UserMongo = Depends(_require_councillor),
):
    """Full response document."""
    record = await MediaRtiResponseMongo.find_one(
        MediaRtiResponseMongo.response_id == response_id
    )
    if not record:
        raise HTTPException(status_code=404, detail="Response not found")

    return {
        "response_id": record.response_id,
        "type": record.type,
        "query_text": record.input.query_text,
        "query_source": record.input.query_source,
        "tone_preference": record.input.tone_preference,
        "rti_application_number": record.input.rti_application_number,
        "data_analysis": {
            "query_intent": record.data_analysis.query_intent,
            "is_answerable": record.data_analysis.is_answerable,
            "data_points": [
                {"description": dp.description, "data": dp.data}
                for dp in record.data_analysis.data_points
            ],
            "outside_scope": record.data_analysis.outside_scope,
            "sensitivity_flag": record.data_analysis.sensitivity_flag,
            "sensitivity_note": record.data_analysis.sensitivity_note,
        },
        "output": _serialize_output(record.output, record.type),
        "created_at": record.created_at.isoformat(),
    }


# ──────────────────────────────────────────────────────────────────────────────
# 6. POST /extract-query-from-image — Vision OCR for RTI documents
# ──────────────────────────────────────────────────────────────────────────────

MAX_FILE_BYTES = 5 * 1024 * 1024  # 5MB

@router.post("/extract-query-from-image")
async def extract_query_from_image(
    file: UploadFile = File(...),
    current_user: UserMongo = Depends(_require_councillor),
):
    """Extract text from an uploaded RTI application document via Gemini vision."""
    content = await file.read()
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 5 MB.")

    mime_type = file.content_type or "image/jpeg"
    b64_data = base64.b64encode(content).decode("utf-8")

    prompt = "Extract all text from this RTI application document. Return only the extracted text, nothing else."

    try:
        import google.generativeai as genai
        from app.core.config import settings
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content([
            {"mime_type": mime_type, "data": b64_data},
            prompt,
        ])
        extracted_text = response.text.strip()
        if not extracted_text:
            raise ValueError("No text extracted")
        return {"extracted_text": extracted_text}
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail="Could not read the document clearly. Please type the application text manually."
        )
