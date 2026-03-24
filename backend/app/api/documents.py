from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
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
