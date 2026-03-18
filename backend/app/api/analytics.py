"""
Analytics API — Decision Intelligence endpoints for supervisors and councillors.

Endpoints:
    GET  /api/analytics/resource-health     — Technician load, skill gaps, AI narrative
    POST /api/analytics/scenario/analyze    — What-If Scenario Planner (AI-reasoned)
    GET  /api/analytics/benchmarks          — Cross-ward benchmarking + AI insight
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
import json
import time

from app.core.dependencies import get_current_user
from app.mongodb.models.user import UserMongo
from app.mongodb.models.ticket import TicketMongo
from app.mongodb.models.ward_benchmark import WardBenchmarkMongo
from app.enums import UserRole, TicketStatus

router = APIRouter()

# ─── Simple in-process cache for baseline stats (1-hour TTL) ─────────────────
_baseline_cache: dict = {}   # key → (timestamp, data)
_CACHE_TTL_SECONDS = 3600


def _cache_get(key: str):
    entry = _baseline_cache.get(key)
    if entry and time.time() - entry[0] < _CACHE_TTL_SECONDS:
        return entry[1]
    return None


def _cache_set(key: str, data):
    _baseline_cache[key] = (time.time(), data)


# ─── Shared guard: allow supervisors, councillors, admins ─────────────────────
def _require_decision_role(current_user: UserMongo = Depends(get_current_user)) -> UserMongo:
    allowed = {
        UserRole.SUPERVISOR, UserRole.COUNCILLOR,
        UserRole.COMMISSIONER, UserRole.SUPER_ADMIN,
    }
    if current_user.role not in allowed:
        raise HTTPException(status_code=403, detail="Supervisor or councillor access required")
    return current_user


# ─── Helper: call Gemini with a plain-text prompt ─────────────────────────────
async def _gemini_narrate(prompt: str) -> str:
    """Call Gemini flash and return the text response. Falls back gracefully."""
    try:
        from app.services.ai.gemini_client import get_llm
        llm = get_llm()
        response = await llm.ainvoke(prompt)
        return response.content.strip()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Gemini narration failed: %s", e)
        return "AI executive summary is temporarily unavailable due to a configuration issue (e.g. invalid or expired API key)."


# ─── DEPT_NAMES mapping (shared util) ─────────────────────────────────────────
DEPT_DISPLAY = {
    "roads": "Roads & Infrastructure",
    "water": "Water Supply",
    "electrical": "Electrical",
    "sanitation": "Sanitation & Waste",
    "parks": "Parks & Environment",
    "storm_drain": "Storm Drains",
    "buildings": "Buildings",
    "health": "Health",
}


# ═════════════════════════════════════════════════════════════════════════════
# Feature 4 — Resource Health & Technician Optimizer
# ═════════════════════════════════════════════════════════════════════════════

@router.get("/resource-health")
async def get_resource_health(
    ward_id: Optional[int] = Query(None),
    current_user: UserMongo = Depends(_require_decision_role),
):
    """
    Computes resource health metrics for the ward, then asks Gemini to narrate.

    Returns:
        - technician_loads: list of {technician_id, name, open_tickets, is_overloaded}
        - dept_metrics: avg resolution days + skill gap flag per dept (30-day window)
        - ai_summary: 3-sentence executive summary from Gemini
    """
    effective_ward = ward_id or current_user.ward_id

    now = datetime.utcnow()
    window_30d = now - timedelta(days=30)
    window_7d  = now - timedelta(days=7)

    # ── Fetch all tickets in the ward within the past 30 days ─────────────────
    ward_filter = [TicketMongo.ward_id == effective_ward] if effective_ward else []
    all_tickets_30d = await TicketMongo.find(
        *ward_filter,
        TicketMongo.created_at >= window_30d,
    ).to_list()

    open_statuses = {TicketStatus.OPEN, TicketStatus.ASSIGNED, TicketStatus.SCHEDULED, TicketStatus.IN_PROGRESS}

    # ── Per-dept metrics ───────────────────────────────────────────────────────
    dept_data: dict = {}
    for t in all_tickets_30d:
        d = t.dept_id
        if d not in dept_data:
            dept_data[d] = {"open": 0, "resolved": 0, "resolution_times": [], "open_7d": 0, "resolved_7d": 0}

        is_open = t.status in open_statuses
        if is_open:
            dept_data[d]["open"] += 1
        else:
            dept_data[d]["resolved"] += 1
            if t.resolved_at and t.assigned_at:
                delta = (t.resolved_at - t.assigned_at).total_seconds() / 86400
                dept_data[d]["resolution_times"].append(max(0, delta))

        # 7-day window for skill gap
        if t.created_at >= window_7d:
            if is_open:
                dept_data[d]["open_7d"] += 1
            else:
                dept_data[d]["resolved_7d"] += 1

    dept_metrics = []
    for d, stats in dept_data.items():
        times = stats["resolution_times"]
        avg_days = round(sum(times) / len(times), 1) if times else None
        skill_gap = stats["open_7d"] > stats["resolved_7d"]
        dept_metrics.append({
            "dept_id": d,
            "dept_name": DEPT_DISPLAY.get(d, d),
            "avg_resolution_days": avg_days,
            "open_tickets": stats["open"],
            "resolved_tickets": stats["resolved"],
            "skill_gap": skill_gap,
            "open_7d": stats["open_7d"],
            "resolved_7d": stats["resolved_7d"],
        })

    # ── Per-technician load ────────────────────────────────────────────────────
    # Get all field staff for the ward
    staff_query = [UserMongo.role == UserRole.FIELD_STAFF]
    if effective_ward:
        staff_query.append(UserMongo.ward_id == effective_ward)
    field_staff = await UserMongo.find(*staff_query).to_list()

    tech_loads = []
    total_open_across_techs = 0
    for tech in field_staff:
        tech_id = str(tech.id)
        open_count = sum(
            1 for t in all_tickets_30d
            if t.technician_id == tech_id and t.status in open_statuses
        )
        tech_loads.append({"technician_id": tech_id, "name": tech.name, "dept_id": tech.dept_id, "open_tickets": open_count})
        total_open_across_techs += open_count

    # Flag overloaded technicians (> 1.5× ward average)
    avg_load = total_open_across_techs / len(tech_loads) if tech_loads else 0
    overload_threshold = avg_load * 1.5
    for t in tech_loads:
        t["is_overloaded"] = t["open_tickets"] > overload_threshold and avg_load > 0
    tech_loads.sort(key=lambda x: x["open_tickets"], reverse=True)

    # ── Build resource data JSON for Gemini ───────────────────────────────────
    resource_data = {
        "ward_id": effective_ward,
        "analysis_window_days": 30,
        "technician_count": len(field_staff),
        "avg_technician_load": round(avg_load, 1),
        "overloaded_technicians": [t for t in tech_loads if t["is_overloaded"]],
        "dept_metrics": dept_metrics,
        "skill_gap_depts": [d["dept_name"] for d in dept_metrics if d["skill_gap"]],
    }

    prompt = f"""You are an analyst for a municipal supervisor dashboard.
Given this resource health data for the past 30 days:
{json.dumps(resource_data, indent=2)}

Write a 3-sentence executive summary that:
1. Names the most overloaded department or technician and the evidence (use specific numbers)
2. Identifies the skill gap that is causing the slowest resolution
3. Gives one concrete reallocation recommendation

Be specific with numbers. Do not use generic language. Do not use markdown formatting."""

    ai_summary = await _gemini_narrate(prompt)

    return {
        "ward_id": effective_ward,
        "technician_loads": tech_loads,
        "dept_metrics": dept_metrics,
        "avg_load": round(avg_load, 1),
        "overload_threshold": round(overload_threshold, 1),
        "ai_summary": ai_summary,
    }


# ═════════════════════════════════════════════════════════════════════════════
# Feature 5 — "What If" Scenario Planner
# ═════════════════════════════════════════════════════════════════════════════

class ScenarioRequest(BaseModel):
    scenario_type: str   # "move_technicians" | "add_technicians" | "deprioritize_dept"
    dept_to: Optional[str] = None
    dept_from: Optional[str] = None
    n_technicians: int = 1
    duration_weeks: int = 2
    ward_id: Optional[int] = None


@router.post("/scenario/analyze")
async def analyze_scenario(
    req: ScenarioRequest,
    current_user: UserMongo = Depends(_require_decision_role),
):
    """
    AI-reasoned what-if analysis. Computes real baseline stats, then asks Gemini
    to reason about the scenario impact. Gemini does NOT calculate — it reasons
    over the computed numbers.
    """
    effective_ward = req.ward_id or current_user.ward_id

    # ── Baseline stats (cached 1 hr) ──────────────────────────────────────────
    cache_key = f"baseline_ward_{effective_ward}"
    baseline = _cache_get(cache_key)

    if baseline is None:
        now = datetime.utcnow()
        window_30d = now - timedelta(days=30)
        ward_filter = [TicketMongo.ward_id == effective_ward] if effective_ward else []
        tickets_30d = await TicketMongo.find(
            *ward_filter,
            TicketMongo.created_at >= window_30d,
        ).to_list()

        open_statuses = {TicketStatus.OPEN, TicketStatus.ASSIGNED, TicketStatus.SCHEDULED, TicketStatus.IN_PROGRESS}

        dept_baseline: dict = {}
        for t in tickets_30d:
            d = t.dept_id
            if d not in dept_baseline:
                dept_baseline[d] = {
                    "open": 0, "closed": 0,
                    "resolution_times": [], "technician_ids": set()
                }
            if t.status in open_statuses:
                dept_baseline[d]["open"] += 1
            else:
                dept_baseline[d]["closed"] += 1
                if t.resolved_at and t.assigned_at:
                    delta = (t.resolved_at - t.assigned_at).total_seconds() / 86400
                    dept_baseline[d]["resolution_times"].append(max(0, delta))
            if t.technician_id:
                dept_baseline[d]["technician_ids"].add(t.technician_id)

        # Arrival rate: total tickets / 30 days × 7 = weekly rate
        baseline = {}
        for d, stats in dept_baseline.items():
            times = stats["resolution_times"]
            total = stats["open"] + stats["closed"]
            baseline[d] = {
                "dept_id": d,
                "dept_name": DEPT_DISPLAY.get(d, d),
                "avg_resolution_days": round(sum(times) / len(times), 1) if times else None,
                "open_tickets": stats["open"],
                "closed_tickets": stats["closed"],
                "technician_count": len(stats["technician_ids"]),
                "weekly_arrival_rate": round((total / 30) * 7, 1),
            }
        _cache_set(cache_key, baseline)

    # ── Build the scenario description ────────────────────────────────────────
    dept_to_name = DEPT_DISPLAY.get(req.dept_to or "", req.dept_to or "target department")
    dept_from_name = DEPT_DISPLAY.get(req.dept_from or "", req.dept_from or "source department")

    if req.scenario_type == "move_technicians":
        scenario_desc = (
            f"Move {req.n_technicians} technician(s) from {dept_from_name} to {dept_to_name} "
            f"for {req.duration_weeks} week(s)."
        )
    elif req.scenario_type == "add_technicians":
        scenario_desc = (
            f"Add {req.n_technicians} new technician(s) to {dept_to_name} "
            f"for {req.duration_weeks} week(s)."
        )
    elif req.scenario_type == "deprioritize_dept":
        scenario_desc = (
            f"Deprioritize {dept_to_name} for {req.duration_weeks} week(s), "
            f"redirecting attention to other departments."
        )
    else:
        scenario_desc = req.scenario_type

    # Format baseline for prompt (only relevant depts)
    relevant_depts = [d for d in baseline.values()
                      if d["dept_id"] in [req.dept_to, req.dept_from] or not req.dept_from]
    if not relevant_depts:
        relevant_depts = list(baseline.values())[:4]

    baseline_text = "\n".join([
        f"- {d['dept_name']}: avg {d['avg_resolution_days'] or 'N/A'} days to resolve, "
        f"{d['open_tickets']} open tickets, {d['technician_count']} active technicians, "
        f"~{d['weekly_arrival_rate']} new tickets/week"
        for d in relevant_depts
    ])

    prompt = f"""You are a civic resource planning advisor for a municipal ward in Chennai, India.

Current baseline data (last 30 days):
{baseline_text}

Councillor scenario: "{scenario_desc}"

Reason through the following:
1. How would {dept_to_name} resolution time likely change? Use arrival rate vs capacity logic.
2. What backlog impact would {dept_from_name} see during those {req.duration_weeks} week(s)? (if applicable)
3. What is the net citizen impact — is this a good tradeoff?

Give a direct recommendation with your reasoning. Be specific with numbers where you can.
Format as 3 short paragraphs (no bullet points, no markdown headers)."""

    ai_analysis = await _gemini_narrate(prompt)

    return {
        "scenario": {
            "type": req.scenario_type,
            "description": scenario_desc,
            "n_technicians": req.n_technicians,
            "duration_weeks": req.duration_weeks,
            "dept_to": req.dept_to,
            "dept_to_name": dept_to_name,
            "dept_from": req.dept_from,
            "dept_from_name": dept_from_name,
        },
        "baseline": relevant_depts,
        "ai_analysis": ai_analysis,
    }


# ═════════════════════════════════════════════════════════════════════════════
# Feature 6 — Cross-Ward Benchmarking
# ═════════════════════════════════════════════════════════════════════════════

@router.get("/benchmarks")
async def get_benchmarks(
    ward_id: Optional[int] = Query(None),
    current_user: UserMongo = Depends(_require_decision_role),
):
    """
    Compares the current ward's performance against seeded peer ward benchmarks.
    Calls Gemini to identify the best practice peer and give a recommendation.
    """
    effective_ward = ward_id or current_user.ward_id

    # ── Compute current ward metrics ──────────────────────────────────────────
    now = datetime.utcnow()
    window_30d = now - timedelta(days=30)
    ward_filter = [TicketMongo.ward_id == effective_ward] if effective_ward else []
    tickets = await TicketMongo.find(
        *ward_filter,
        TicketMongo.created_at >= window_30d,
    ).to_list()

    dept_res_times: dict = {}
    for t in tickets:
        d = t.dept_id
        if d not in dept_res_times:
            dept_res_times[d] = []
        if t.resolved_at and t.assigned_at and t.status == TicketStatus.CLOSED:
            delta = (t.resolved_at - t.assigned_at).total_seconds() / 86400
            dept_res_times[d].append(max(0, delta))

    current_avg_by_dept = {
        d: round(sum(times) / len(times), 1) if times else None
        for d, times in dept_res_times.items()
    }
    overall_avg = None
    all_times = [t for times in dept_res_times.values() for t in times]
    if all_times:
        overall_avg = round(sum(all_times) / len(all_times), 1)

    open_count = sum(1 for t in tickets if t.status not in {TicketStatus.CLOSED, TicketStatus.REJECTED})
    closed_count = len(tickets) - open_count
    resolution_rate = round((closed_count / len(tickets)) * 100, 1) if tickets else 0

    current_ward = {
        "ward_id": effective_ward,
        "ward_name": f"Ward {effective_ward}" if effective_ward else "Your Ward",
        "avg_resolution_days_by_dept": {DEPT_DISPLAY.get(k, k): v for k, v in current_avg_by_dept.items() if v is not None},
        "overall_avg_resolution_days": overall_avg,
        "ticket_volume": len(tickets),
        "resolution_rate_pct": resolution_rate,
    }

    # ── Fetch peer ward benchmarks ────────────────────────────────────────────
    peer_wards = await WardBenchmarkMongo.find_all().to_list()

    if not peer_wards:
        return {
            "current_ward": current_ward,
            "peer_wards": [],
            "ai_insight": "No peer ward benchmark data available. Run the seed script to populate benchmark data.",
        }

    peer_data = [
        {
            "ward_name": pw.ward_name,
            "ward_id": pw.ward_id,
            "avg_resolution_days_by_dept": pw.avg_resolution_days_by_dept,
            "overall_avg_resolution_days": (
                round(sum(pw.avg_resolution_days_by_dept.values()) / len(pw.avg_resolution_days_by_dept), 1)
                if pw.avg_resolution_days_by_dept else None
            ),
            "ticket_volume": pw.ticket_volume,
            "resolution_rate_pct": pw.resolution_rate_pct,
            "top_practice": pw.top_practice,
        }
        for pw in peer_wards
    ]

    current_json = json.dumps(current_ward, indent=2)
    peers_json = json.dumps(peer_data, indent=2)

    prompt = f"""Compare this ward's performance against peer wards and identify ONE practice worth replicating.

Current ward metrics:
{current_json}

Peer ward data:
{peers_json}

Respond in exactly these 3 bullet points (start each with a dash):
- Best performing peer ward for [specific metric]: [ward name] — [their metric value vs our value]
- Their practice: [what they do differently, inferred from the data]
- Recommended action: [one concrete step the councillor can take this month]

Be specific with numbers. Do not use markdown formatting beyond the dashes."""

    ai_insight = await _gemini_narrate(prompt)

    return {
        "current_ward": current_ward,
        "peer_wards": peer_data,
        "ai_insight": ai_insight,
    }
