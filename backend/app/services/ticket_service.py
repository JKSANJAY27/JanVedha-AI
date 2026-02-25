"""
TicketService — MongoDB-backed civic complaint service.

Fully rewritten to use Beanie (MongoDB) instead of SQLAlchemy.
Integrates the full AI pipeline for classification, routing, priority, and suggestions.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException

from app.enums import TicketSource, TicketStatus, PriorityLabel
from app.mongodb.models.ticket import TicketMongo
from app.mongodb.models.department import DepartmentMongo
from app.core.ticket_codes import generate_ticket_code
from app.services.ai.pipeline import run_pipeline
from app.services.ai.priority_agent import train_on_closed_ticket

logger = logging.getLogger(__name__)


class TicketService:

    @staticmethod
    async def create_ticket(
        description: str,
        location_text: str,
        reporter_phone: str,
        consent_given: bool,
        reporter_name: Optional[str] = None,
        photo_url: Optional[str] = None,
        language: str = "en",
        source: TicketSource = TicketSource.WEB_PORTAL,
        reporter_user_id: Optional[str] = None,
        ward_id: Optional[int] = None,
    ) -> TicketMongo:
        # 1. DPDP Compliance
        if not consent_given:
            raise HTTPException(
                status_code=400,
                detail="Consent is strictly required to process a ticket"
            )

        # 2. Generate ticket code early (needed for memory agent)
        ticket_code = generate_ticket_code()

        # 3. Run the full AI pipeline
        pipeline_result = await run_pipeline(
            description=description,
            location_text=location_text,
            photo_url=photo_url,
            ward_id=ward_id,
            ticket_id=ticket_code,
        )

        # 4. Clarification required?
        if pipeline_result.needs_clarification or pipeline_result.ai_confidence < 0.65:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Please clarify your complaint",
                    "question": pipeline_result.clarification_question or
                                "Could you provide more details about the issue?",
                }
            )

        # 5. Department SLA
        dept = await DepartmentMongo.find_one(
            DepartmentMongo.dept_id == pipeline_result.dept_id
        )
        sla_days = dept.sla_days if dept else 7
        sla_deadline = datetime.utcnow() + timedelta(days=sla_days)

        # 6. Build and persist the ticket
        ticket = TicketMongo(
            ticket_code=ticket_code,
            source=source,
            description=description,
            dept_id=pipeline_result.dept_id,
            issue_category=pipeline_result.issue_category,
            location_text=location_text,
            photo_url=photo_url,
            reporter_phone=reporter_phone,
            reporter_name=reporter_name,
            reporter_user_id=reporter_user_id,
            ward_id=ward_id,
            consent_given=True,
            consent_timestamp=datetime.utcnow(),
            language_detected=pipeline_result.language_detected,
            ai_confidence=pipeline_result.ai_confidence,
            ai_routing_reason=pipeline_result.routing_reason,
            ai_suggestions=pipeline_result.suggestions,
            priority_score=pipeline_result.priority_score,
            priority_label=PriorityLabel(pipeline_result.priority_label),
            priority_source=pipeline_result.priority_source,
            status=TicketStatus.OPEN,
            requires_human_review=pipeline_result.requires_human_review,
            sla_deadline=sla_deadline,
            seasonal_alert=pipeline_result.seasonal_alert,
        )
        await ticket.insert()

        # 7. Blockchain hash (stub-compatible)
        data_hash = hashlib.sha256(
            f"{ticket.id}-{ticket.created_at}".encode()
        ).hexdigest()
        ticket.blockchain_hash = data_hash
        await ticket.save()

        # 8. SMS notification (non-blocking, best-effort)
        try:
            from app.core.container import get_sms_provider
            from app.interfaces.notification_provider import SMSMessage
            sms = get_sms_provider()
            await sms.send_message(SMSMessage(
                to_phone=reporter_phone,
                body=(
                    f"Your complaint has been registered. "
                    f"Ticket: {ticket.ticket_code}. "
                    f"Priority: {ticket.priority_label}. "
                    f"Assigned to: {pipeline_result.dept_name}."
                )
            ))
        except Exception as exc:
            logger.warning("SMS notification failed (non-critical): %s", exc)

        return ticket

    @staticmethod
    async def change_status(
        ticket_id: str,
        new_status: str,
        actor_id: str,
        actor_role: str,
        reason: Optional[str] = None,
        new_dept_id: Optional[str] = None,
    ) -> TicketMongo:
        from beanie import PydanticObjectId
        ticket = await TicketMongo.get(PydanticObjectId(ticket_id))
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        old_status = ticket.status

        if new_status == "REROUTE":
            if not new_dept_id:
                raise HTTPException(
                    status_code=400,
                    detail="new_dept_id is required for REROUTE"
                )
            ticket.dept_id = new_dept_id
            dept = await DepartmentMongo.find_one(DepartmentMongo.dept_id == new_dept_id)
            sla_days = dept.sla_days if dept else 7
            ticket.sla_deadline = datetime.utcnow() + timedelta(days=sla_days)

        elif new_status == "ESCALATE":
            # Notify (best-effort)
            try:
                from app.core.container import get_whatsapp_provider
                from app.interfaces.notification_provider import WhatsAppMessage
                wa = get_whatsapp_provider()
                await wa.send_message(WhatsAppMessage(
                    to_phone="ZONAL_OFFICER_PHONE",
                    body=f"Ticket {ticket.ticket_code} has been escalated. Reason: {reason}"
                ))
            except Exception as exc:
                logger.warning("WhatsApp escalation failed (non-critical): %s", exc)

        else:
            ticket.status = TicketStatus(new_status)
            if new_status == TicketStatus.ASSIGNED:
                ticket.assigned_officer_id = actor_id
                ticket.assigned_at = datetime.utcnow()
            elif new_status == TicketStatus.CLOSED:
                ticket.resolved_at = datetime.utcnow()
                # Feed closing data back to ML model for online learning
                days_open = (datetime.utcnow() - ticket.created_at).days
                hours_remaining = (
                    (ticket.sla_deadline - datetime.utcnow()).total_seconds() / 3600
                    if ticket.sla_deadline else 0
                )
                try:
                    await train_on_closed_ticket(
                        issue_category=ticket.issue_category or "default",
                        report_count=ticket.report_count,
                        days_open=days_open,
                        social_media_mentions=ticket.social_media_mentions,
                        hours_until_sla_breach=hours_remaining,
                        month=ticket.created_at.month,
                        description=ticket.description,
                        dept_id=ticket.dept_id,
                        confirmed_priority_label=ticket.priority_label.value
                        if ticket.priority_label else "MEDIUM",
                    )
                except Exception as exc:
                    logger.warning("ML training on close failed (non-critical): %s", exc)

        await ticket.save()
        return ticket
