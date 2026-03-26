"""
Commissioner API — Department health, intelligence alerts, escalations, and weekly digest.
All endpoints require commissioner or super_admin role.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, HTTPException, Body
from pydantic import BaseModel

from app.core.dependencies import get_current_user
from app.mongodb.models.user import UserMongo
from app.enums import UserRole

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory cache for dept health (30 min TTL)
_dept_health_cache: dict = {"data": None, "ts": None}
CACHE_TTL = 1800


def _require_commissioner(current_user: UserMongo = Depends(get_current_user)) -> UserMongo:
    if current_user.role not in {UserRole.COMMISSIONER, UserRole.SUPER_ADMIN, UserRole.SUPERVISOR}:
        raise HTTPException(status_code=403, detail="Commissioner/Supervisor access required")
    return current_user


def _health_score(metrics: dict, sla_days: int, overloaded: int):
    score = 100
    rate = metrics.get("resolution_rate_pct") or 0
    avg = metrics.get("avg_resolution_days") or 0
    overdue = metrics.get("overdue_count") or 0
    if rate < 60: score -= 30
    elif rate < 80: score -= 15
    if avg > sla_days * 2: score -= 25
    elif avg > sla_days: score -= 12
    if overdue > 10: score -= 20
    elif overdue > 5: score -= 10
    if metrics.get("trend_direction") == "worsening": score -= 10
    if overloaded > 0: score -= 5
    score = max(0, score)
    label = "Healthy" if score >= 80 else ("Needs attention" if score >= 60 else ("At risk" if score >= 40 else "Critical"))
    return score, label


# ─── FEATURE 1: Department Command Center ───────────────────────────────────

@router.get("/department-health")
async def get_department_health(current_user: UserMongo = Depends(_require_commissioner)):
    global _dept_health_cache
    now = datetime.utcnow()
    if _dept_health_cache["data"] and _dept_health_cache["ts"]:
        if (now - _dept_health_cache["ts"]).total_seconds() < CACHE_TTL:
            return _dept_health_cache["data"]

    from app.mongodb.models.dept_config import DeptConfigMongo
    from app.mongodb.models.ticket import TicketMongo
    from app.utils.metrics import compute_ticket_metrics, get_technician_load
    from app.core.config import settings
    import google.generativeai as genai

    depts = await DeptConfigMongo.find_all().to_list()
    motor_col = TicketMongo.get_pymongo_collection()
    tech_load = await get_technician_load()

    dept_results = []
    all_summary = {}

    for dept in depts:
        cats = dept.ticket_categories
        curr_cut = now - timedelta(days=30)
        prev_s = now - timedelta(days=60)
        prev_e = now - timedelta(days=30)

        cur_tickets = await motor_col.find({"issue_category": {"$in": cats}, "created_at": {"$gte": curr_cut}}).to_list(None)
        prev_tickets = await motor_col.find({"issue_category": {"$in": cats}, "created_at": {"$gte": prev_s, "$lt": prev_e}}).to_list(None)

        metrics = compute_ticket_metrics(cur_tickets, dept.sla_days, prev_tickets)

        active_techs = sum(1 for i in tech_load.values() if i["active_ticket_count"] > 0)
        overloaded = sum(1 for i in tech_load.values() if i["active_ticket_count"] > 6)
        total_techs = len(tech_load) or 1
        utilization = round(active_techs / total_techs * 100, 1)

        score, label = _health_score(metrics, dept.sla_days, overloaded)

        all_summary[dept.dept_id] = {
            "dept_name": dept.dept_name, "health_score": score, "health_label": label,
            "sla_days": dept.sla_days, **metrics,
            "technicians": {"total": total_techs, "active": active_techs, "overloaded": overloaded, "utilization_rate": utilization},
        }
        dept_results.append({
            "dept_id": dept.dept_id, "dept_name": dept.dept_name, "color_hex": dept.color_hex,
            "sla_days": dept.sla_days, "health_score": score, "health_label": label,
            "metrics": metrics,
            "technicians": {"total": total_techs, "active": active_techs, "overloaded": overloaded, "utilization_rate": utilization},
            "ai_verdict": "Analysis unavailable",
        })

    overall_verdict = None
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")
        dept_keys = list(all_summary.keys())
        prompt = f"""You are an analyst for a municipal commissioner dashboard.
Performance data for departments (past 30 days vs previous 30):
{json.dumps(all_summary, indent=2)}

For EACH department, write ONE sentence (max 20 words): state the key performance fact. If trend changed, mention it. If at risk/critical, end with an action.
Also write ONE overall verdict sentence (max 25 words).

Respond ONLY as JSON:
{{"department_verdicts": {{{", ".join(f'"{k}": "..."' for k in dept_keys)}}}, "overall_verdict": "..."}}"""

        resp = await model.generate_content_async(prompt, generation_config={"temperature": 0.3})
        text = resp.text.strip()
        if "```" in text:
            text = text.split("```")[1].lstrip("json\n")
        parsed = json.loads(text)
        verdicts = parsed.get("department_verdicts", {})
        overall_verdict = parsed.get("overall_verdict")
        for d in dept_results:
            d["ai_verdict"] = verdicts.get(d["dept_id"], "Analysis unavailable")
    except Exception as e:
        logger.error(f"Gemini dept verdict failed: {e}")

    result = {"generated_at": now.isoformat(), "overall_verdict": overall_verdict, "departments": dept_results}
    _dept_health_cache = {"data": result, "ts": now}
    return result


@router.get("/department/{dept_id}/detail")
async def get_department_detail(
    dept_id: str,
    days: int = Query(30, ge=7, le=180),
    current_user: UserMongo = Depends(_require_commissioner),
):
    from app.mongodb.models.dept_config import DeptConfigMongo
    from app.mongodb.models.ticket import TicketMongo
    from app.utils.metrics import compute_ticket_metrics

    dept = await DeptConfigMongo.find_one(DeptConfigMongo.dept_id == dept_id)
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")

    now = datetime.utcnow()
    cutoff = now - timedelta(days=days)
    motor_col = TicketMongo.get_pymongo_collection()
    tickets = await motor_col.find(
        {"issue_category": {"$in": dept.ticket_categories}, "created_at": {"$gte": cutoff}}
    ).to_list(None)

    # Ward breakdown
    ward_map: dict = {}
    for t in tickets:
        w = str(t.get("ward_id") or "unknown")
        ward_map.setdefault(w, []).append(t)
    ward_breakdown = []
    for w, wt in ward_map.items():
        m = compute_ticket_metrics(wt, dept.sla_days)
        ward_breakdown.append({"ward_id": w, "total": m["total_count"], "resolved": m["resolved_count"],
            "resolution_rate_pct": m["resolution_rate_pct"], "avg_resolution_days": m["avg_resolution_days"],
            "overdue_count": m["overdue_count"]})
    ward_breakdown.sort(key=lambda x: x["resolution_rate_pct"])

    # Technician breakdown
    tech_map: dict = {}
    for t in tickets:
        tid = str(t.get("technician_id") or "unassigned")
        tech_map.setdefault(tid, []).append(t)
    tech_breakdown = []
    for tid, tt in tech_map.items():
        m = compute_ticket_metrics(tt, dept.sla_days)
        active = sum(1 for t in tt if t.get("status") in ("OPEN", "IN_PROGRESS", "ASSIGNED"))
        tech_breakdown.append({"technician_id": tid, "assigned_count": m["total_count"],
            "resolved_count": m["resolved_count"], "avg_resolution_days": m["avg_resolution_days"],
            "active_ticket_count": active})

    # Overdue tickets
    sla_cutoff = now - timedelta(days=dept.sla_days)
    overdue = []
    for t in tickets:
        if t.get("status") in ("OPEN", "IN_PROGRESS", "ASSIGNED") and t.get("created_at") and t["created_at"] < sla_cutoff:
            days_od = (now - t["created_at"]).days - dept.sla_days
            overdue.append({"ticket_id": str(t["_id"]), "title": (t.get("description") or "")[:80],
                "ward_id": str(t.get("ward_id") or ""), "created_at": t["created_at"].isoformat(),
                "days_overdue": days_od, "assigned_technician_id": str(t.get("technician_id") or "")})
    overdue.sort(key=lambda x: x["days_overdue"], reverse=True)

    # Weekly trend (6 weeks)
    weekly_trend = []
    for i in range(5, -1, -1):
        ws = now - timedelta(days=7 * (i + 1))
        we = now - timedelta(days=7 * i)
        created = sum(1 for t in tickets if t.get("created_at") and ws <= t["created_at"] < we)
        resolved = sum(1 for t in tickets if t.get("resolved_at") and ws <= t["resolved_at"] < we)
        weekly_trend.append({"week_label": "This week" if i == 0 else f"Wk {6-i}", "created": created, "resolved": resolved})

    return {"dept_id": dept_id, "dept_name": dept.dept_name, "sla_days": dept.sla_days,
        "color_hex": dept.color_hex, "ward_breakdown": ward_breakdown,
        "technician_breakdown": tech_breakdown, "overdue_tickets": overdue[:20],
        "weekly_trend": weekly_trend}


@router.get("/staff-performance")
async def get_staff_performance(current_user: UserMongo = Depends(_require_commissioner)):
    from app.mongodb.models.ticket import TicketMongo
    from app.utils.metrics import compute_ticket_metrics
    from collections import Counter

    now = datetime.utcnow()
    cutoff = now - timedelta(days=30)
    motor_col = TicketMongo.get_pymongo_collection()

    jes = await UserMongo.find(UserMongo.role == UserRole.JUNIOR_ENGINEER).to_list()
    je_results = []
    for je in jes:
        je_id = str(je.id)
        jt = await motor_col.find({"assigned_officer_id": je_id, "created_at": {"$gte": cutoff}}).to_list(None)
        m = compute_ticket_metrics(jt, 7)
        assign_times = [(t["assigned_at"] - t["created_at"]).days for t in jt if t.get("assigned_at") and t.get("created_at")]
        avg_assign = round(sum(assign_times) / len(assign_times), 1) if assign_times else None
        overdue = m["overdue_count"]
        status = "Needs review" if (overdue > 5 or (avg_assign and avg_assign > 2)) else ("Monitor" if overdue > 2 else "On track")
        je_results.append({"id": je_id, "name": je.name, "queue_size": m["open_count"] + m["in_progress_count"],
            "avg_assign_days": avg_assign, "resolved_this_month": m["resolved_count"],
            "overdue_count": overdue, "status": status})
    je_results.sort(key=lambda x: x["overdue_count"], reverse=True)

    tech_ids = await motor_col.distinct("technician_id", {"technician_id": {"$ne": None}, "created_at": {"$gte": cutoff}})
    tech_results = []
    for tid in tech_ids:
        if not tid: continue
        tt = await motor_col.find({"technician_id": tid, "created_at": {"$gte": cutoff}}).to_list(None)
        m = compute_ticket_metrics(tt, 7)
        active = sum(1 for t in tt if t.get("status") in ("OPEN", "IN_PROGRESS", "ASSIGNED"))
        cats = [t.get("issue_category") or "other" for t in tt if t.get("status") == "CLOSED"]
        top_cat = Counter(cats).most_common(1)[0][0] if cats else None
        tech_results.append({"technician_id": str(tid), "tickets_completed": m["resolved_count"],
            "avg_resolution_days": m["avg_resolution_days"], "active_count": active,
            "overload_flag": active > 6, "top_category": top_cat})

    return {"junior_engineers": je_results, "technicians": tech_results}


# ─── FEATURE 2: Systemic Issue Detector ─────────────────────────────────────

@router.get("/intelligence-alerts")
async def get_intelligence_alerts(
    status: str = Query("new,acknowledged"),
    pattern_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: UserMongo = Depends(_require_commissioner),
):
    from app.mongodb.models.intelligence_alert import IntelligenceAlertMongo

    now = datetime.utcnow()
    status_list = [s.strip() for s in status.split(",")]

    query_filter = {
        "status": {"$in": status_list},
        "$or": [{"expires_at": {"$gt": now}}, {"expires_at": None}],
    }
    if pattern_type:
        query_filter["pattern_type"] = pattern_type

    severity_order = {"high": 0, "medium": 1, "low": 2}
    motor_col = IntelligenceAlertMongo.get_pymongo_collection()
    docs = await motor_col.find(query_filter).sort([("created_at", -1)]).to_list(None)

    docs.sort(key=lambda d: (severity_order.get(d.get("severity", "low"), 2), -d.get("created_at", datetime.min).timestamp()))

    total = len(docs)
    paginated = docs[(page - 1) * limit: page * limit]

    results = []
    for d in paginated:
        d["_id"] = str(d["_id"])
        if d.get("created_at"): d["created_at"] = d["created_at"].isoformat()
        if d.get("expires_at"): d["expires_at"] = d["expires_at"].isoformat()
        if d.get("acknowledged_at"): d["acknowledged_at"] = d["acknowledged_at"].isoformat()
        results.append(d)

    return {"total": total, "page": page, "limit": limit, "alerts": results}


@router.get("/intelligence-alerts/counts")
async def get_intelligence_alert_counts(current_user: UserMongo = Depends(_require_commissioner)):
    from app.mongodb.models.intelligence_alert import IntelligenceAlertMongo

    now = datetime.utcnow()
    motor_col = IntelligenceAlertMongo.get_pymongo_collection()
    base = {"$or": [{"expires_at": {"$gt": now}}, {"expires_at": None}]}

    new_count = await motor_col.count_documents({**base, "status": "new"})
    ack_count = await motor_col.count_documents({**base, "status": "acknowledged"})
    high_count = await motor_col.count_documents({**base, "status": {"$in": ["new", "acknowledged"]}, "severity": "high"})

    # Last run time
    from app.mongodb.database import get_motor_client
    from app.core.config import settings as cfg
    db_name = cfg.MONGODB_URI.rsplit("/", 1)[-1].split("?")[0] or "civicai"
    client = get_motor_client()
    setting_doc = await client[db_name]["app_settings"].find_one({"key": "intelligence_last_run"})
    last_run = setting_doc["value"] if setting_doc else None

    return {"new": new_count, "acknowledged": ack_count, "high_severity": high_count, "last_run": last_run}


class AcknowledgeBody(BaseModel):
    commissioner_id: str
    commissioner_name: str
    note: Optional[str] = None
    action: str = "acknowledge"  # "acknowledge" | "actioned" | "resolved"


@router.post("/intelligence-alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    body: AcknowledgeBody,
    current_user: UserMongo = Depends(_require_commissioner),
):
    from app.mongodb.models.intelligence_alert import IntelligenceAlertMongo

    alert = await IntelligenceAlertMongo.find_one(IntelligenceAlertMongo.alert_id == alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    status_map = {"acknowledge": "acknowledged", "actioned": "actioned", "resolved": "resolved"}
    new_status = status_map.get(body.action, "acknowledged")

    alert.status = new_status
    alert.acknowledged_by_id = body.commissioner_id
    alert.acknowledged_by_name = body.commissioner_name
    alert.acknowledged_at = datetime.utcnow()
    if body.note:
        alert.commissioner_note = body.note
    await alert.save()
    return {"success": True, "status": new_status}


@router.post("/intelligence-alerts/run-detection")
async def run_detection(current_user: UserMongo = Depends(_require_commissioner)):
    from app.utils.pattern_detector import run_all_detections
    result = await run_all_detections()
    return result


# ─── FEATURE 3: Councillor Escalation Manager ───────────────────────────────

class EscalationSubmitBody(BaseModel):
    ward_id: str
    ward_name: str
    from_councillor_id: str
    from_councillor_name: str
    escalation_type: str = "constituent_complaint"
    subject: str
    description: str
    urgency: str = "normal"
    linked_casework_id: Optional[str] = None
    linked_ticket_id: Optional[str] = None


@router.post("/escalations/submit")
async def submit_escalation(body: EscalationSubmitBody, current_user: UserMongo = Depends(get_current_user)):
    from app.mongodb.models.escalation import EscalationMongo, TimelineEvent
    from app.mongodb.database import get_motor_client
    from app.core.config import settings as cfg

    sla_map = {"high": 48, "medium": 120, "normal": 240}
    sla_hours = sla_map.get(body.urgency, 240)
    now = datetime.utcnow()
    deadline = now + timedelta(hours=sla_hours)

    esc = EscalationMongo(
        ward_id=body.ward_id, ward_name=body.ward_name,
        from_councillor_id=body.from_councillor_id, from_councillor_name=body.from_councillor_name,
        escalation_type=body.escalation_type, subject=body.subject, description=body.description,
        urgency=body.urgency, linked_casework_id=body.linked_casework_id,
        linked_ticket_id=body.linked_ticket_id, status="received",
        sla_hours=sla_hours, sla_deadline=deadline,
        timeline=[TimelineEvent(event="Escalation submitted", actor=body.from_councillor_name)]
    )
    await esc.insert()

    # Notify commissioners
    try:
        commissioners = await UserMongo.find(UserMongo.role.in_([UserRole.COMMISSIONER, UserRole.SUPER_ADMIN])).to_list()
        db_name = cfg.MONGODB_URI.rsplit("/", 1)[-1].split("?")[0] or "civicai"
        client = get_motor_client()
        col = client[db_name]["supervisor_notifications"]
        for comm in commissioners:
            await col.insert_one({"user_id": str(comm.id), "type": "escalation_received",
                "title": f"[{body.urgency.upper()}] Escalation from {body.from_councillor_name}",
                "body": body.subject, "reference_id": esc.escalation_id, "read": False, "created_at": now})
    except Exception as e:
        logger.error(f"Escalation notification failed (non-fatal): {e}")

    # Update linked casework if provided
    if body.linked_casework_id:
        try:
            from app.mongodb.models.casework import CaseworkMongo
            cw = await CaseworkMongo.find_one(CaseworkMongo.casework_id == body.linked_casework_id)
            if cw:
                cw.status = "escalated"
                cw.escalation_flag = True
                await cw.save()
        except Exception as e:
            logger.error(f"Casework update failed: {e}")

    return {"escalation_id": esc.escalation_id, "sla_deadline": deadline.isoformat()}


@router.get("/escalations")
async def list_escalations(
    status: Optional[str] = None,
    urgency: Optional[str] = None,
    ward_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: UserMongo = Depends(_require_commissioner),
):
    from app.mongodb.models.escalation import EscalationMongo

    now = datetime.utcnow()
    motor_col = EscalationMongo.get_pymongo_collection()
    query: dict = {}
    if status:
        query["status"] = {"$in": status.split(",")}
    else:
        query["status"] = {"$nin": ["closed"]}
    if urgency:
        query["urgency"] = urgency
    if ward_id:
        query["ward_id"] = ward_id

    docs = await motor_col.find(query).to_list(None)

    urgency_order = {"high": 0, "medium": 1, "normal": 2}
    for d in docs:
        deadline = d.get("sla_deadline")
        if deadline:
            hrs = (deadline - now).total_seconds() / 3600
            d["hours_remaining"] = round(hrs, 1)
            d["sla_breached"] = hrs < 0 and d.get("status") not in ["responded", "closed"]
        else:
            d["hours_remaining"] = None
            d["sla_breached"] = False

    docs.sort(key=lambda d: (
        not d.get("sla_breached", False),
        urgency_order.get(d.get("urgency", "normal"), 2),
        d.get("created_at", datetime.min)
    ))

    total = len(docs)
    paginated = docs[(page - 1) * limit: page * limit]

    def serialize(d):
        d["_id"] = str(d["_id"])
        for fld in ["sla_deadline", "created_at", "updated_at"]:
            if d.get(fld): d[fld] = d[fld].isoformat()
        cr = d.get("commissioner_response", {})
        if cr and cr.get("responded_at"):
            cr["responded_at"] = cr["responded_at"].isoformat()
        return d

    return {"total": total, "page": page, "limit": limit, "escalations": [serialize(d) for d in paginated]}


@router.get("/escalations/counts")
async def get_escalation_counts(current_user: UserMongo = Depends(_require_commissioner)):
    from app.mongodb.models.escalation import EscalationMongo

    now = datetime.utcnow()
    motor_col = EscalationMongo.get_pymongo_collection()
    open_statuses = ["received", "acknowledged", "in_progress", "responded"]
    total_open = await motor_col.count_documents({"status": {"$in": open_statuses}})
    high_urgency = await motor_col.count_documents({"status": {"$in": open_statuses}, "urgency": "high"})
    all_open = await motor_col.find({"status": {"$in": open_statuses}}).to_list(None)
    sla_breached = sum(1 for d in all_open if d.get("sla_deadline") and d["sla_deadline"] < now)
    awaiting = await motor_col.count_documents({"status": {"$in": ["received", "acknowledged"]}})
    return {"total_open": total_open, "high_urgency": high_urgency, "sla_breached": sla_breached, "awaiting_response": awaiting}


@router.get("/escalations/{escalation_id}")
async def get_escalation(escalation_id: str, current_user: UserMongo = Depends(_require_commissioner)):
    from app.mongodb.models.escalation import EscalationMongo

    esc = await EscalationMongo.find_one(EscalationMongo.escalation_id == escalation_id)
    if not esc:
        raise HTTPException(status_code=404, detail="Escalation not found")

    result = esc.model_dump()
    result["_id"] = str(esc.id)
    for fld in ["sla_deadline", "created_at", "updated_at"]:
        if result.get(fld) and hasattr(result[fld], "isoformat"):
            result[fld] = result[fld].isoformat()
    now = datetime.utcnow()
    if esc.sla_deadline:
        result["hours_remaining"] = round((esc.sla_deadline - now).total_seconds() / 3600, 1)
        result["sla_breached"] = esc.sla_deadline < now and esc.status not in ["responded", "closed"]
    else:
        result["hours_remaining"] = None
        result["sla_breached"] = False

    # Attach linked docs
    if esc.linked_casework_id:
        try:
            from app.mongodb.models.casework import CaseworkMongo
            cw = await CaseworkMongo.find_one(CaseworkMongo.casework_id == esc.linked_casework_id)
            result["linked_casework"] = cw.model_dump() if cw else None
        except: result["linked_casework"] = None
    if esc.linked_ticket_id:
        try:
            from app.mongodb.models.ticket import TicketMongo
            from beanie import PydanticObjectId
            tk = await TicketMongo.get(PydanticObjectId(esc.linked_ticket_id))
            result["linked_ticket"] = {"id": str(tk.id), "title": tk.description[:80], "status": tk.status} if tk else None
        except: result["linked_ticket"] = None

    return result


class RespondBody(BaseModel):
    commissioner_id: str
    commissioner_name: str
    action_type: str
    response_text: str
    assigned_dept_id: Optional[str] = None


@router.post("/escalations/{escalation_id}/respond")
async def respond_escalation(
    escalation_id: str, body: RespondBody,
    current_user: UserMongo = Depends(_require_commissioner),
):
    from app.mongodb.models.escalation import EscalationMongo, TimelineEvent, CommissionerResponse
    from app.mongodb.models.dept_config import DeptConfigMongo
    from app.mongodb.database import get_motor_client
    from app.core.config import settings as cfg

    esc = await EscalationMongo.find_one(EscalationMongo.escalation_id == escalation_id)
    if not esc:
        raise HTTPException(status_code=404, detail="Escalation not found")
    if esc.status == "closed":
        raise HTTPException(status_code=400, detail="Escalation already closed")

    now = datetime.utcnow()
    dept_name = None
    if body.assigned_dept_id:
        dept = await DeptConfigMongo.find_one(DeptConfigMongo.dept_id == body.assigned_dept_id)
        dept_name = dept.dept_name if dept else body.assigned_dept_id

    esc.commissioner_response = CommissionerResponse(
        action_type=body.action_type, response_text=body.response_text,
        assigned_dept_id=body.assigned_dept_id, assigned_dept_name=dept_name,
        responding_commissioner_id=body.commissioner_id,
        responding_commissioner_name=body.commissioner_name, responded_at=now
    )
    status_map = {"direct_resolution": "responded", "dept_assignment": "in_progress",
                  "response_sent": "responded", "escalated_further": "responded"}
    esc.status = status_map.get(body.action_type, "responded")
    esc.updated_at = now
    esc.timeline.append(TimelineEvent(event="Commissioner responded", actor=body.commissioner_name,
        note=f"Action: {body.action_type}"))
    await esc.save()

    # Notify councillor
    try:
        db_name = cfg.MONGODB_URI.rsplit("/", 1)[-1].split("?")[0] or "civicai"
        client = get_motor_client()
        await client[db_name]["supervisor_notifications"].insert_one({
            "user_id": esc.from_councillor_id, "type": "escalation_responded",
            "title": "Response received for your escalation",
            "body": f"{esc.subject} — {body.response_text[:100]}",
            "read": False, "created_at": now
        })
    except Exception as e:
        logger.error(f"Councillor notification failed: {e}")

    return {"success": True, "status": esc.status}


@router.post("/escalations/{escalation_id}/close")
async def close_escalation(
    escalation_id: str,
    commissioner_id: str = Body(...),
    note: Optional[str] = Body(None),
    current_user: UserMongo = Depends(_require_commissioner),
):
    from app.mongodb.models.escalation import EscalationMongo, TimelineEvent
    from app.mongodb.database import get_motor_client
    from app.core.config import settings as cfg

    esc = await EscalationMongo.find_one(EscalationMongo.escalation_id == escalation_id)
    if not esc:
        raise HTTPException(status_code=404, detail="Escalation not found")

    now = datetime.utcnow()
    esc.status = "closed"
    esc.updated_at = now
    esc.timeline.append(TimelineEvent(event="Escalation closed", actor=commissioner_id, note=note))
    await esc.save()

    try:
        db_name = cfg.MONGODB_URI.rsplit("/", 1)[-1].split("?")[0] or "civicai"
        client = get_motor_client()
        await client[db_name]["supervisor_notifications"].insert_one({
            "user_id": esc.from_councillor_id, "type": "escalation_closed",
            "title": "Escalation closed", "body": esc.subject, "read": False, "created_at": now
        })
    except Exception as e:
        logger.error(f"Close notification failed: {e}")

    return {"success": True}


# ─── FEATURE 4: Weekly Commissioner Digest ──────────────────────────────────

async def generate_weekly_digest(triggered_by: str = "scheduler", user_id: Optional[str] = None) -> dict:
    from app.mongodb.models.commissioner_digest import CommissionerDigestMongo
    from app.mongodb.models.ticket import TicketMongo
    from app.mongodb.models.dept_config import DeptConfigMongo
    from app.mongodb.models.escalation import EscalationMongo
    from app.mongodb.models.intelligence_alert import IntelligenceAlertMongo
    from app.mongodb.models.cctv_alert import CCTVAlert
    from app.utils.metrics import compute_ticket_metrics
    from app.core.config import settings as cfg
    import google.generativeai as genai
    import uuid

    now = datetime.utcnow()
    week_start = now - timedelta(days=7)
    prev_start = now - timedelta(days=14)
    prev_end = now - timedelta(days=7)
    week_label = f"Week of {week_start.strftime('%d %b %Y')}"

    # Idempotency check
    existing = await CommissionerDigestMongo.find_one(CommissionerDigestMongo.week_label == week_label)
    if existing and triggered_by == "scheduler":
        return {"digest_id": existing.digest_id, "week_label": week_label, "digest": existing.digest}
    if existing and triggered_by == "manual":
        await existing.delete()

    motor_col = TicketMongo.get_pymongo_collection()

    # Overall ticket metrics
    cur_tickets = await motor_col.find({"created_at": {"$gte": week_start}}).to_list(None)
    prev_tickets = await motor_col.find({"created_at": {"$gte": prev_start, "$lt": prev_end}}).to_list(None)
    overall_metrics = compute_ticket_metrics(cur_tickets, 7, prev_tickets)

    # Per-dept metrics
    depts = await DeptConfigMongo.find_all().to_list()
    dept_metrics = []
    for d in depts:
        dt = [t for t in cur_tickets if t.get("issue_category") in d.ticket_categories]
        m = compute_ticket_metrics(dt, d.sla_days)
        dept_metrics.append({"dept_name": d.dept_name, **{k: v for k, v in m.items() if k in ["total_count", "resolved_count", "resolution_rate_pct", "avg_resolution_days"]}})
    dept_metrics.sort(key=lambda x: x.get("resolution_rate_pct") or 100)

    # Ward rankings
    ward_groups: dict = {}
    for t in cur_tickets:
        w = str(t.get("ward_id") or "unknown")
        ward_groups.setdefault(w, []).append(t)
    ward_perf = []
    for w, wt in ward_groups.items():
        m = compute_ticket_metrics(wt, 7)
        ward_perf.append({"ward_id": w, "resolution_rate_pct": m["resolution_rate_pct"],
            "avg_resolution_days": m["avg_resolution_days"], "overdue_count": m["overdue_count"]})
    ward_perf.sort(key=lambda x: x.get("resolution_rate_pct") or 0)
    worst_wards = ward_perf[:3]
    best_wards = ward_perf[-3:]

    # Escalations
    esc_col = EscalationMongo.get_pymongo_collection()
    esc_week = await esc_col.find({"created_at": {"$gte": week_start}}).to_list(None)
    esc_responded = sum(1 for e in esc_week if e.get("status") in ["responded", "closed"])
    esc_breached = sum(1 for e in esc_week if e.get("sla_breached"))
    esc_high = sum(1 for e in esc_week if e.get("urgency") == "high")

    # Intelligence alerts
    alert_col = IntelligenceAlertMongo.get_pymongo_collection()
    alerts_week = await alert_col.find({"created_at": {"$gte": week_start}}).to_list(None)
    alert_summaries = [a.get("summary", "") for a in alerts_week[:5]]

    # CCTV
    try:
        cctv_col = CCTVAlert.get_pymongo_collection()
        cctv_week = await cctv_col.find({"created_at": {"$gte": week_start}}).to_list(None)
        cctv_total = len(cctv_week)
        cctv_tickets = sum(1 for a in cctv_week if a.get("ticket_id"))
        cctv_pending = sum(1 for a in cctv_week if a.get("status") == "pending")
    except: cctv_total = cctv_tickets = cctv_pending = 0

    raw_data = {
        "week_label": week_label,
        "overall_metrics": overall_metrics,
        "department_metrics": dept_metrics,
        "worst_wards": worst_wards,
        "best_wards": best_wards,
        "escalations": {"total_received": len(esc_week), "total_responded": esc_responded,
            "sla_breached_count": esc_breached, "high_urgency_count": esc_high},
        "intelligence_alerts": {"new_alerts_count": len(alerts_week),
            "high_severity_count": sum(1 for a in alerts_week if a.get("severity") == "high"),
            "alert_summaries": alert_summaries},
        "cctv": {"total_detected": cctv_total, "tickets_raised": cctv_tickets, "pending_count": cctv_pending},
    }

    # Gemini narrative
    digest_content = {}
    gen_status = "success"
    try:
        genai.configure(api_key=cfg.GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")
        prompt = f"""You are writing the weekly performance digest for a Municipal Commissioner in Tamil Nadu, India.
WEEK: {week_label}
DATA:
{json.dumps(raw_data, indent=2)}

Write a digest with flowing prose (no bullet points). Be specific with numbers. Tone: senior analyst briefing a senior official.

Respond in this exact JSON format:
{{
  "executive_summary": "2-3 sentences. Overall picture. What is the single most important thing?",
  "top_concern": "1-2 sentences. The one issue needing the commissioner's personal attention this week.",
  "ward_performance_narrative": "Which wards stood out (best and worst) and why? Name specific wards.",
  "department_health_narrative": "Which departments performing well vs struggling? Mention specific metrics.",
  "escalations_narrative": "How many escalations? Were SLAs met? Any high-urgency cases?",
  "intelligence_alerts_narrative": "What systemic patterns detected? If none, note no anomalies.",
  "cctv_narrative": "How many civic issues detected and actioned? 1-2 sentences only.",
  "recommended_priority_action": "The single most important action for the coming week. 1-2 sentences.",
  "positive_highlight": "One genuine positive or null if nothing truly positive."
}}"""

        resp = await model.generate_content_async(prompt, generation_config={"temperature": 0.4, "max_output_tokens": 1500})
        text = resp.text.strip()
        if "```" in text:
            text = text.split("```")[1].lstrip("json\n")
        digest_content = json.loads(text)
    except Exception as e:
        logger.error(f"Digest Gemini failed: {e}")
        gen_status = "generation_failed"
        digest_content = {}

    if gen_status == "generation_failed" and not digest_content:
        digest_doc = CommissionerDigestMongo(
            week_label=week_label, week_start=week_start, week_end=now,
            generated_by=triggered_by, triggered_by_id=user_id,
            generation_status="generation_failed", raw_data=raw_data, digest={}
        )
        await digest_doc.insert()
        return {"digest_id": digest_doc.digest_id, "week_label": week_label, "generation_status": "generation_failed", "raw_data": raw_data}

    # Generate PDF
    pdf_path = None
    try:
        pdf_path = await _generate_digest_pdf(digest_content, raw_data, week_label, now)
    except Exception as e:
        logger.error(f"PDF generation failed: {e}")

    digest_doc = CommissionerDigestMongo(
        week_label=week_label, week_start=week_start, week_end=now,
        generated_by=triggered_by, triggered_by_id=user_id,
        generation_status=gen_status, raw_data=raw_data, digest=digest_content,
        pdf_path=pdf_path, is_current_week=True
    )
    await digest_doc.insert()

    # Mark older digests as not current
    await CommissionerDigestMongo.find(
        CommissionerDigestMongo.week_label != week_label
    ).update({"$set": {"is_current_week": False}})

    # Notify commissioners
    try:
        from app.mongodb.database import get_motor_client
        commissioners = await UserMongo.find(UserMongo.role.in_([UserRole.COMMISSIONER, UserRole.SUPER_ADMIN])).to_list()
        db_name = cfg.MONGODB_URI.rsplit("/", 1)[-1].split("?")[0] or "civicai"
        client = get_motor_client()
        col = client[db_name]["supervisor_notifications"]
        summary_text = (digest_content.get("executive_summary") or "")[:150]
        for comm in commissioners:
            await col.insert_one({"user_id": str(comm.id), "type": "weekly_digest_ready",
                "title": f"Weekly digest ready — {week_label}",
                "body": summary_text, "read": False, "created_at": now})
    except Exception as e:
        logger.error(f"Digest notification failed: {e}")

    return {"digest_id": digest_doc.digest_id, "week_label": week_label, "digest": digest_content}


async def _generate_digest_pdf(digest: dict, raw_data: dict, week_label: str, generated_at: datetime) -> Optional[str]:
    import os
    try:
        from fpdf import FPDF
    except ImportError:
        return None

    os.makedirs("/tmp/digests", exist_ok=True)
    from uuid import uuid4
    digest_id = uuid4().hex[:8]
    pdf_path = f"/tmp/digests/{digest_id}.pdf"

    pdf = FPDF()
    pdf.set_margins(20, 20, 20)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 10, "MUNICIPAL CORPORATION — WEEKLY COMMISSIONER DIGEST", ln=True, align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, f"{week_label}  |  Generated: {generated_at.strftime('%d %b %Y %H:%M UTC')}", ln=True, align="C")
    pdf.ln(4)
    pdf.set_draw_color(0, 51, 102)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(6)

    def write_section(title: str, body: str, color=(0, 51, 102)):
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(*color)
        pdf.cell(0, 8, title, ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(40, 40, 40)
        pdf.multi_cell(0, 6, body or "No data available.")
        pdf.ln(4)

    if digest.get("executive_summary"):
        write_section("EXECUTIVE SUMMARY", digest["executive_summary"])

    if digest.get("top_concern"):
        pdf.set_fill_color(255, 240, 240)
        pdf.set_draw_color(200, 0, 0)
        pdf.set_line_width(1)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(180, 0, 0)
        pdf.cell(0, 8, "PRIORITY CONCERN:", ln=True, fill=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(80, 0, 0)
        pdf.multi_cell(0, 6, digest["top_concern"], fill=True)
        pdf.set_line_width(0.2)
        pdf.ln(6)

    pdf.add_page()
    sections = [
        ("Ward Performance", "ward_performance_narrative"),
        ("Department Health", "department_health_narrative"),
        ("Escalations", "escalations_narrative"),
        ("Intelligence Alerts", "intelligence_alerts_narrative"),
        ("CCTV Monitoring", "cctv_narrative"),
        ("Recommended Priority Action", "recommended_priority_action"),
    ]
    for title, key in sections:
        write_section(title.upper(), digest.get(key, ""))

    if digest.get("positive_highlight"):
        write_section("THIS WEEK'S HIGHLIGHT ✓", digest["positive_highlight"], color=(0, 100, 50))

    # Metrics table
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 8, "METRICS SUMMARY", ln=True)
    om = raw_data.get("overall_metrics", {})
    esc = raw_data.get("escalations", {})
    ia = raw_data.get("intelligence_alerts", {})
    cv = raw_data.get("cctv", {})
    rows = [
        ("Tickets created this week", om.get("total_count", 0)),
        ("Tickets resolved", om.get("resolved_count", 0)),
        ("Resolution rate", f"{om.get('resolution_rate_pct', 0)}%"),
        ("Avg resolution days", om.get("avg_resolution_days", "N/A")),
        ("Escalations received", esc.get("total_received", 0)),
        ("SLA breached (escalations)", esc.get("sla_breached_count", 0)),
        ("Intelligence alerts", ia.get("new_alerts_count", 0)),
        ("CCTV tickets raised", cv.get("tickets_raised", 0)),
    ]
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(40, 40, 40)
    for label, val in rows:
        pdf.cell(100, 7, label)
        pdf.cell(0, 7, str(val), ln=True)
        pdf.set_draw_color(220, 220, 220)
        pdf.line(20, pdf.get_y(), 190, pdf.get_y())

    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(150, 150, 150)
    pdf.ln(10)
    pdf.cell(0, 5, f"JanVedha AI — Weekly Commissioner Digest  |  {week_label}  |  Confidential", align="C")

    pdf.output(pdf_path)
    return pdf_path


@router.get("/digest/latest")
async def get_latest_digest(current_user: UserMongo = Depends(_require_commissioner)):
    from app.mongodb.models.commissioner_digest import CommissionerDigestMongo
    import os

    digest = await CommissionerDigestMongo.find().sort(-CommissionerDigestMongo.generated_at).first_or_none()
    if not digest:
        return None

    result = digest.model_dump()
    result["_id"] = str(digest.id)
    result["pdf_available"] = bool(digest.pdf_path and os.path.exists(digest.pdf_path))
    for fld in ["week_start", "week_end", "generated_at"]:
        if result.get(fld) and hasattr(result[fld], "isoformat"):
            result[fld] = result[fld].isoformat()
    return result


@router.get("/digest/history")
async def get_digest_history(
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=52),
    current_user: UserMongo = Depends(_require_commissioner),
):
    from app.mongodb.models.commissioner_digest import CommissionerDigestMongo

    all_digests = await CommissionerDigestMongo.find().sort(-CommissionerDigestMongo.week_start).to_list(None)
    total = len(all_digests)
    paginated = all_digests[(page - 1) * limit: page * limit]

    results = []
    for d in paginated:
        results.append({
            "digest_id": d.digest_id, "week_label": d.week_label,
            "generated_at": d.generated_at.isoformat() if d.generated_at else None,
            "generated_by": d.generated_by, "generation_status": d.generation_status,
        })
    return {"total": total, "page": page, "limit": limit, "digests": results}


@router.get("/digest/{digest_id}")
async def get_digest(digest_id: str, current_user: UserMongo = Depends(_require_commissioner)):
    from app.mongodb.models.commissioner_digest import CommissionerDigestMongo
    import os

    digest = await CommissionerDigestMongo.find_one(CommissionerDigestMongo.digest_id == digest_id)
    if not digest:
        raise HTTPException(status_code=404, detail="Digest not found")

    result = digest.model_dump()
    result["_id"] = str(digest.id)
    result["pdf_available"] = bool(digest.pdf_path and os.path.exists(digest.pdf_path))
    for fld in ["week_start", "week_end", "generated_at"]:
        if result.get(fld) and hasattr(result[fld], "isoformat"):
            result[fld] = result[fld].isoformat()
    return result


from fastapi.responses import FileResponse

@router.get("/digest/{digest_id}/pdf")
async def get_digest_pdf(digest_id: str, current_user: UserMongo = Depends(_require_commissioner)):
    from app.mongodb.models.commissioner_digest import CommissionerDigestMongo
    import os

    digest = await CommissionerDigestMongo.find_one(CommissionerDigestMongo.digest_id == digest_id)
    if not digest:
        raise HTTPException(status_code=404, detail="Digest not found")

    if not digest.pdf_path or not os.path.exists(digest.pdf_path):
        # Regenerate PDF from stored data
        try:
            pdf_path = await _generate_digest_pdf(
                digest.digest, digest.raw_data,
                digest.week_label, digest.generated_at or datetime.utcnow()
            )
            if pdf_path:
                digest.pdf_path = pdf_path
                await digest.save()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")

    if not digest.pdf_path or not os.path.exists(digest.pdf_path):
        raise HTTPException(status_code=404, detail="PDF not available")

    return FileResponse(digest.pdf_path, media_type="application/pdf",
        filename=f"commissioner-digest-{digest.week_label.replace(' ', '-')}.pdf")


class GenerateDigestBody(BaseModel):
    user_id: Optional[str] = None

@router.post("/digest/generate")
async def trigger_digest_generation(
    body: GenerateDigestBody,
    current_user: UserMongo = Depends(_require_commissioner),
):
    import asyncio
    asyncio.create_task(generate_weekly_digest(triggered_by="manual", user_id=body.user_id or str(current_user.id)))
    return {"message": "Digest generation started", "check_url": "/api/commissioner/digest/latest"}


# ─── Keep original endpoints for backward compat ────────────────────────────

@router.get("/city-summary")
async def get_city_summary(current_user: UserMongo = Depends(_require_commissioner)):
    from app.mongodb.models.ticket import TicketMongo
    from app.enums import TicketStatus, PriorityLabel

    all_tickets = await TicketMongo.find_all().to_list()
    if not all_tickets:
        return {"total_tickets": 0, "open": 0, "closed": 0, "overdue": 0, "resolution_rate": 0,
            "avg_resolution_days": 0, "avg_satisfaction": None, "total_estimated_budget": 0, "total_spent_budget": 0}

    now = datetime.utcnow()
    closed = [t for t in all_tickets if t.status == TicketStatus.CLOSED]
    open_t = [t for t in all_tickets if t.status not in {TicketStatus.CLOSED, TicketStatus.REJECTED}]
    overdue = [t for t in open_t if t.sla_deadline and t.sla_deadline < now]
    res_times = [(t.resolved_at - t.created_at).days for t in closed if t.resolved_at]
    avg_res = round(sum(res_times) / len(res_times), 1) if res_times else 0
    sat = [t.citizen_satisfaction for t in all_tickets if t.citizen_satisfaction]
    avg_sat = round(sum(sat) / len(sat), 1) if sat else None
    return {"total_tickets": len(all_tickets), "open": len(open_t), "closed": len(closed),
        "overdue": len(overdue), "resolution_rate": round(len(closed) / len(all_tickets) * 100, 1),
        "avg_resolution_days": avg_res, "avg_satisfaction": avg_sat,
        "total_estimated_budget": sum(t.estimated_cost or 0 for t in all_tickets),
        "total_spent_budget": sum(t.estimated_cost or 0 for t in closed)}


@router.get("/ward-performance")
async def get_ward_performance(current_user: UserMongo = Depends(_require_commissioner)):
    from app.mongodb.models.ticket import TicketMongo
    from app.enums import TicketStatus

    tickets = await TicketMongo.find_all().to_list()
    now = datetime.utcnow()
    ward_map: dict = {}
    for t in tickets:
        w = t.ward_id or 0
        if w not in ward_map:
            ward_map[w] = {"ward_id": w, "total": 0, "open": 0, "closed": 0, "overdue": 0, "budget_spent": 0}
        ward_map[w]["total"] += 1
        if t.status == TicketStatus.CLOSED:
            ward_map[w]["closed"] += 1
            ward_map[w]["budget_spent"] += t.estimated_cost or 0
        else:
            ward_map[w]["open"] += 1
            if t.sla_deadline and t.sla_deadline < now:
                ward_map[w]["overdue"] += 1
    result = list(ward_map.values())
    result.sort(key=lambda x: x["overdue"], reverse=True)
    return result


@router.get("/budget-burn-rate")
async def get_budget_burn_rate(
    weeks: int = Query(12, ge=4, le=52),
    current_user: UserMongo = Depends(_require_commissioner)
):
    from app.mongodb.models.ticket import TicketMongo
    from app.enums import TicketStatus

    now = datetime.utcnow()
    weekly_data = []
    for i in range(weeks - 1, -1, -1):
        ws = now - timedelta(weeks=i + 1)
        we = now - timedelta(weeks=i)
        tickets = await TicketMongo.find(TicketMongo.status == TicketStatus.CLOSED,
            TicketMongo.resolved_at >= ws, TicketMongo.resolved_at < we).to_list()
        weekly_data.append({"week_label": we.strftime("W%W %b"), "week_start": ws,
            "budget_spent": sum(t.estimated_cost or 0 for t in tickets), "resolved_tickets": len(tickets)})
    return weekly_data


@router.get("/critical-open-tickets")
async def get_critical_open_tickets(
    limit: int = Query(20, ge=1, le=50),
    current_user: UserMongo = Depends(_require_commissioner)
):
    from app.mongodb.models.ticket import TicketMongo
    from app.enums import TicketStatus, PriorityLabel

    open_statuses = [TicketStatus.OPEN, TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS,
        TicketStatus.PENDING_VERIFICATION]
    tickets = await TicketMongo.find(
        TicketMongo.status.in_(open_statuses),
        TicketMongo.priority_label == PriorityLabel.CRITICAL
    ).sort(-TicketMongo.priority_score).limit(limit).to_list()
    now = datetime.utcnow()
    return [{"id": str(t.id), "ticket_code": t.ticket_code, "ward_id": t.ward_id,
        "dept_id": t.dept_id, "issue_category": t.issue_category or "General",
        "priority_score": t.priority_score, "sla_deadline": t.sla_deadline,
        "days_overdue": (now - t.sla_deadline).days if t.sla_deadline and t.sla_deadline < now else 0,
        "estimated_cost": t.estimated_cost} for t in tickets]
