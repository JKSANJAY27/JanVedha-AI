from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from typing import Optional
from app.core.dependencies import get_current_user
from app.mongodb.models.user import UserMongo
from app.mongodb.models.ticket import TicketMongo
from app.enums import UserRole, TicketStatus
from beanie import PydanticObjectId

router = APIRouter()


@router.get("/tickets/{ticket_id}/apr")
async def generate_apr_document(
    ticket_id: str,
    current_user: UserMongo = Depends(get_current_user)
):
    """
    Generates an Action Taken Report (APR) PDF for a closed ticket.
    Uses fpdf2 (pure Python) — works on all platforms including Windows.
    """
    from app.services.apr_generator import generate_apr_pdf

    ticket = await TicketMongo.get(PydanticObjectId(ticket_id))
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket.status != TicketStatus.CLOSED:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot generate APR for a ticket that is not CLOSED (current: {ticket.status})"
        )

    allowed_roles = {UserRole.WARD_OFFICER, UserRole.SUPERVISOR, UserRole.COMMISSIONER,
                     UserRole.SUPER_ADMIN, UserRole.JUNIOR_ENGINEER}
    if current_user.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Unauthorised to generate APR reports.")

    try:
        pdf_bytes = generate_apr_pdf(
            ticket_code=ticket.ticket_code,
            priority=ticket.priority_label,
            department=ticket.dept_id,
            ward_id=ticket.ward_id or "Unassigned",
            status=ticket.status,
            reporter_name=ticket.reporter_name or "Anonymous",
            issue_category=ticket.issue_category,
            description=ticket.description,
            created_at=ticket.created_at.strftime("%d %b %Y, %H:%M"),
            officer_id=ticket.assigned_officer_id or "N/A",
            technician_id=ticket.technician_id or "N/A",
            resolved_at=ticket.resolved_at.strftime("%d %b %Y, %H:%M") if ticket.resolved_at else "N/A",
            verification_verdict="Verified" if ticket.work_verified else (
                "Failed" if ticket.work_verified is False else "Manual / Pending"
            ),
            verification_confidence=(
                f"{ticket.work_verification_confidence * 100:.1f}%"
                if ticket.work_verification_confidence is not None else "N/A"
            ),
            verification_explanation=ticket.work_verification_explanation or "No explanation available.",
            before_photo_url=ticket.before_photo_url or ticket.photo_url,
            after_photo_url=ticket.after_photo_url,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=APR_{ticket.ticket_code}.pdf"}
    )


# ─── Supervisor Ward Statistics Report ────────────────────────────────────────

@router.get("/supervisor-report")
async def generate_supervisor_report(
    ward_id: Optional[int] = Query(None),
    current_user: UserMongo = Depends(get_current_user),
):
    """
    Generates a professional Ward Statistics Report PDF for supervisors.
    Suitable for presentations to zone/commissioner offices.
    """
    from datetime import datetime
    from app.services.supervisor_report import generate_supervisor_report_pdf
    from app.enums import TicketStatus as TS

    allowed = {UserRole.SUPERVISOR, UserRole.COMMISSIONER, UserRole.SUPER_ADMIN}
    if current_user.role not in allowed:
        raise HTTPException(status_code=403, detail="Supervisor access required.")

    effective_ward = ward_id or current_user.ward_id
    if not effective_ward:
        raise HTTPException(status_code=400, detail="ward_id is required.")

    tickets = await TicketMongo.find(TicketMongo.ward_id == effective_ward).to_list()
    now = datetime.utcnow()

    closed = [t for t in tickets if t.status == TS.CLOSED]
    open_t = [t for t in tickets if t.status not in {TS.CLOSED, TS.REJECTED}]
    overdue = [t for t in open_t if t.sla_deadline and t.sla_deadline < now]
    critical = [t for t in tickets if str(getattr(t.priority_label, "value", t.priority_label)) == "CRITICAL"]

    resolution_rate = round(len(closed) / len(tickets) * 100, 1) if tickets else 0.0

    res_times = [(t.resolved_at - t.created_at).days for t in closed if t.resolved_at]
    avg_res_days = round(sum(res_times) / len(res_times), 1) if res_times else 0.0

    sat = [t.citizen_satisfaction for t in tickets if t.citizen_satisfaction]
    avg_sat = round(sum(sat) / len(sat), 1) if sat else None

    # Priority breakdown
    priority_breakdown = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for t in tickets:
        p = str(getattr(t.priority_label, "value", t.priority_label))
        if p in priority_breakdown:
            priority_breakdown[p] += 1

    # Department performance
    dept_map: dict = {}
    for t in tickets:
        d = t.dept_id or "UNKNOWN"
        if d not in dept_map:
            dept_map[d] = {"dept_id": d, "total": 0, "open": 0, "closed": 0, "overdue": 0}
        dept_map[d]["total"] += 1
        if t.status == TS.CLOSED:
            dept_map[d]["closed"] += 1
        else:
            dept_map[d]["open"] += 1
            if t.sla_deadline and t.sla_deadline < now:
                dept_map[d]["overdue"] += 1
    dept_performance = sorted(dept_map.values(), key=lambda x: x["overdue"], reverse=True)

    # Top issues
    cat_map: dict = {}
    for t in tickets:
        c = t.issue_category or "General"
        cat_map[c] = cat_map.get(c, 0) + 1
    total_count = len(tickets) or 1
    top_issues = [
        {"category": cat, "count": cnt, "percentage": round(cnt / total_count * 100, 1)}
        for cat, cnt in sorted(cat_map.items(), key=lambda x: x[1], reverse=True)[:8]
    ]

    # Overdue list
    overdue_list = [
        {
            "ticket_code": t.ticket_code,
            "issue_category": t.issue_category or "General",
            "priority_label": str(getattr(t.priority_label, "value", t.priority_label)),
            "days_overdue": (now - t.sla_deadline).days if t.sla_deadline else 0,
            "dept_id": t.dept_id or "",
        }
        for t in sorted(overdue, key=lambda x: x.sla_deadline or now)[:20]
    ]

    month_label = now.strftime("%B %Y")
    ward_label = f"Ward {effective_ward}"
    supervisor_name = current_user.name or "Supervisor"

    try:
        pdf_bytes = generate_supervisor_report_pdf(
            ward_id=effective_ward,
            ward_label=ward_label,
            supervisor_name=supervisor_name,
            report_period=month_label,
            total_tickets=len(tickets),
            open_tickets=len(open_t),
            closed_tickets=len(closed),
            overdue_tickets=len(overdue),
            critical_tickets=len(critical),
            resolution_rate=resolution_rate,
            avg_resolution_days=avg_res_days,
            avg_satisfaction=avg_sat,
            priority_breakdown=priority_breakdown,
            dept_performance=dept_performance,
            top_issues=top_issues,
            overdue_list=overdue_list,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")

    filename = f"Supervisor-Ward{effective_ward}-{now.strftime('%Y-%m')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ─── Councillor Ward Executive Report ─────────────────────────────────────────

@router.get("/councillor-report")
async def generate_councillor_report(
    ward_id: Optional[int] = Query(None),
    current_user: UserMongo = Depends(get_current_user),
):
    """
    Generates an official Ward Executive Report PDF for councillors to
    present to Zonal Commissioner / State officials.
    """
    from datetime import datetime
    from app.services.councillor_report import generate_councillor_report_pdf
    from app.enums import TicketStatus as TS
    from app.services.intelligence_service import IntelligenceService

    allowed = {UserRole.COUNCILLOR, UserRole.COMMISSIONER, UserRole.SUPER_ADMIN}
    if current_user.role not in allowed:
        raise HTTPException(status_code=403, detail="Councillor access required.")

    effective_ward = ward_id or current_user.ward_id
    if not effective_ward:
        raise HTTPException(status_code=400, detail="ward_id is required.")

    tickets = await TicketMongo.find(TicketMongo.ward_id == effective_ward).to_list()
    now = datetime.utcnow()

    closed = [t for t in tickets if t.status == TS.CLOSED]
    open_t = [t for t in tickets if t.status not in {TS.CLOSED, TS.REJECTED}]
    overdue = [t for t in open_t if t.sla_deadline and t.sla_deadline < now]

    resolution_rate = round(len(closed) / len(tickets) * 100, 1) if tickets else 0.0
    res_times = [(t.resolved_at - t.created_at).days for t in closed if t.resolved_at]
    avg_res_days = round(sum(res_times) / len(res_times), 1) if res_times else 0.0
    sat = [t.citizen_satisfaction for t in tickets if t.citizen_satisfaction]
    avg_sat = round(sum(sat) / len(sat), 1) if sat else None

    priority_breakdown = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for t in tickets:
        p = str(getattr(t.priority_label, "value", t.priority_label))
        if p in priority_breakdown:
            priority_breakdown[p] += 1

    dept_map: dict = {}
    for t in tickets:
        d = t.dept_id or "UNKNOWN"
        if d not in dept_map:
            dept_map[d] = {"dept_id": d, "total": 0, "open": 0, "closed": 0, "overdue": 0}
        dept_map[d]["total"] += 1
        if t.status == TS.CLOSED:
            dept_map[d]["closed"] += 1
        else:
            dept_map[d]["open"] += 1
            if t.sla_deadline and t.sla_deadline < now:
                dept_map[d]["overdue"] += 1
    dept_performance = sorted(dept_map.values(), key=lambda x: x["overdue"], reverse=True)

    cat_map: dict = {}
    for t in tickets:
        c = t.issue_category or "General"
        cat_map[c] = cat_map.get(c, 0) + 1
    total_count = len(tickets) or 1
    top_issues = [
        {"category": cat, "count": cnt, "percentage": round(cnt / total_count * 100, 1)}
        for cat, cnt in sorted(cat_map.items(), key=lambda x: x[1], reverse=True)[:5]
    ]

    overdue_list = [
        {
            "ticket_code": t.ticket_code,
            "issue_category": t.issue_category or "General",
            "priority_label": str(getattr(t.priority_label, "value", t.priority_label)),
            "days_overdue": (now - t.sla_deadline).days if t.sla_deadline else 0,
            "dept_id": t.dept_id or "",
        }
        for t in sorted(overdue, key=lambda x: x.sla_deadline or now)[:20]
    ]

    # Try to fetch AI briefing from cache (non-blocking)
    ai_briefing = None
    try:
        ai_briefing = await IntelligenceService.get_ward_briefing(effective_ward, refresh=False)
    except Exception:
        pass

    month_label = now.strftime("%B %Y")
    ward_label = f"Ward {effective_ward}"
    councillor_name = current_user.name or "Councillor"

    try:
        pdf_bytes = generate_councillor_report_pdf(
            ward_id=effective_ward,
            ward_label=ward_label,
            councillor_name=councillor_name,
            report_period=month_label,
            total_tickets=len(tickets),
            open_tickets=len(open_t),
            closed_tickets=len(closed),
            overdue_tickets=len(overdue),
            resolution_rate=resolution_rate,
            avg_resolution_days=avg_res_days,
            avg_satisfaction=avg_sat,
            priority_breakdown=priority_breakdown,
            dept_performance=dept_performance,
            top_issues=top_issues,
            overdue_list=overdue_list,
            ai_briefing=ai_briefing,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")

    filename = f"Councillor-Ward{effective_ward}-Report-{now.strftime('%Y-%m')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )



@router.get("/tickets/{ticket_id}/apr")
async def generate_apr_document(
    ticket_id: str,
    current_user: UserMongo = Depends(get_current_user)
):
    """
    Generates an Action Taken Report (APR) PDF for a closed ticket.
    Uses fpdf2 (pure Python) — works on all platforms including Windows.
    """
    from app.services.apr_generator import generate_apr_pdf

    ticket = await TicketMongo.get(PydanticObjectId(ticket_id))
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket.status != TicketStatus.CLOSED:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot generate APR for a ticket that is not CLOSED (current: {ticket.status})"
        )

    allowed_roles = {UserRole.WARD_OFFICER, UserRole.SUPERVISOR, UserRole.COMMISSIONER,
                     UserRole.SUPER_ADMIN, UserRole.JUNIOR_ENGINEER}
    if current_user.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Unauthorised to generate APR reports.")

    try:
        pdf_bytes = generate_apr_pdf(
            ticket_code=ticket.ticket_code,
            priority=ticket.priority_label,
            department=ticket.dept_id,
            ward_id=ticket.ward_id or "Unassigned",
            status=ticket.status,
            reporter_name=ticket.reporter_name or "Anonymous",
            issue_category=ticket.issue_category,
            description=ticket.description,
            created_at=ticket.created_at.strftime("%d %b %Y, %H:%M"),
            officer_id=ticket.assigned_officer_id or "N/A",
            technician_id=ticket.technician_id or "N/A",
            resolved_at=ticket.resolved_at.strftime("%d %b %Y, %H:%M") if ticket.resolved_at else "N/A",
            verification_verdict="Verified" if ticket.work_verified else (
                "Failed" if ticket.work_verified is False else "Manual / Pending"
            ),
            verification_confidence=(
                f"{ticket.work_verification_confidence * 100:.1f}%"
                if ticket.work_verification_confidence is not None else "N/A"
            ),
            verification_explanation=ticket.work_verification_explanation or "No explanation available.",
            before_photo_url=ticket.before_photo_url or ticket.photo_url,
            after_photo_url=ticket.after_photo_url,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=APR_{ticket.ticket_code}.pdf"}
    )
