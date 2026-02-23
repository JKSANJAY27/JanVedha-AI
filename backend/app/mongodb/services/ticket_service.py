"""
Service: MongoTicketService

MongoDB port of app/services/ticket_service.py.
Uses repositories instead of SQLAlchemy sessions.
Preserves identical business logic: DPDP compliance, AI classification,
SLA calculation, priority scoring, audit trail, blockchain hash, SMS.
"""
import hashlib
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException

from app.core.priority import calculate_priority_score
from app.core.ticket_codes import generate_ticket_code
from app.core.container import (
    get_ai_provider,
    get_blockchain_provider,
    get_sms_provider,
    get_whatsapp_provider,
)
from app.interfaces.notification_provider import SMSMessage, WhatsAppMessage
from app.models.ticket import TicketSource, TicketStatus

from app.mongodb.models.ticket import TicketMongo
from app.mongodb.repositories.ticket_repo import TicketRepo
from app.mongodb.repositories.department_repo import DepartmentRepo
from app.mongodb.repositories.audit_repo import AuditRepo


class MongoTicketService:
    """Business logic for tickets — MongoDB implementation."""

    @staticmethod
    async def create_ticket(
        description: str,
        location_text: str,
        reporter_phone: str,
        consent_given: bool,
        reporter_name: Optional[str] = None,
        photo_url: Optional[str] = None,
        language: str = "en",
        source: str = TicketSource.WEB_PORTAL,
    ) -> TicketMongo:
        """
        Create a civic complaint ticket.
        Identical workflow to the SQLAlchemy version:
          1. DPDP consent check
          2. AI classification
          3. Department SLA look-up
          4. Priority scoring
          5. DB insertion (MongoDB)
          6. Audit log
          7. Blockchain hash
          8. SMS notification
        """
        # 1. DPDP Compliance
        if not consent_given:
            raise HTTPException(
                status_code=400,
                detail="Consent is strictly required to process a ticket",
            )

        # 2. AI Classification
        ai = get_ai_provider()
        classification = await ai.classify_complaint(description, photo_url)

        if classification.confidence < 0.75 or classification.needs_clarification:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Please clarify your complaint",
                    "question": classification.clarification_question,
                },
            )

        # 3. Department SLA look-up
        dept = await DepartmentRepo.get_by_id(classification.dept_id)
        sla_days = dept.sla_days if dept else 7
        sla_deadline = datetime.utcnow() + timedelta(days=sla_days)

        # 4. Priority Score
        score, label = calculate_priority_score(
            subcategory=classification.issue_summary,
            report_count=1,
            location_type="unknown",
            days_open=0,
            hours_until_sla_breach=sla_days * 24.0,
            social_media_mentions=0,
            description=description,
        )
        score_val, label_val = score

        # 5. MongoDB Insertion
        ticket = TicketMongo(
            ticket_code=generate_ticket_code(),
            source=source,
            description=description,
            dept_id=classification.dept_id,
            photo_url=photo_url,
            reporter_phone=reporter_phone,
            reporter_name=reporter_name,
            consent_given=True,
            consent_timestamp=datetime.utcnow(),
            language_detected=classification.language_detected,
            ai_confidence=classification.confidence,
            priority_score=score_val,
            priority_label=label_val,
            status=TicketStatus.OPEN,
            requires_human_review=classification.requires_human_review,
            sla_deadline=sla_deadline,
        )
        ticket = await TicketRepo.create(ticket)

        # 6. Audit Log
        await AuditRepo.write(
            action="TICKET_CREATED",
            ticket_id=str(ticket.id),
            new_value={"dept_id": ticket.dept_id, "score": score_val},
        )

        # 7. Immutable Ledger Record
        blockchain = get_blockchain_provider()
        data_hash = hashlib.sha256(
            f"{ticket.id}-{ticket.created_at}".encode()
        ).hexdigest()
        await blockchain.record_hash(data_hash, "TICKET_CREATED")
        await TicketRepo.update_blockchain_hash(ticket, data_hash)

        # 8. SMS Notification
        sms = get_sms_provider()
        await sms.send_message(
            SMSMessage(
                to_phone=reporter_phone,
                body=f"Your ticket {ticket.ticket_code} is created.",
            )
        )

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
        """
        Change ticket status / reroute / escalate.
        Mirrors TicketService.change_status from the SQLAlchemy version.
        """
        ticket = await TicketRepo.get_by_id(ticket_id)
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        old_status = ticket.status

        if new_status == "REROUTE":
            if not new_dept_id:
                raise HTTPException(
                    status_code=400,
                    detail="new_dept_id is required for REROUTE",
                )
            old_dept = ticket.dept_id
            dept = await DepartmentRepo.get_by_id(new_dept_id)
            sla_days = dept.sla_days if dept else 7
            new_sla = datetime.utcnow() + timedelta(days=sla_days)
            ticket = await TicketRepo.update_dept(ticket, new_dept_id, new_sla)

            await AuditRepo.write(
                action="TICKET_REROUTED",
                ticket_id=str(ticket.id),
                actor_id=actor_id,
                actor_role=actor_role,
                old_value={"dept_id": old_dept},
                new_value={"dept_id": new_dept_id, "reason": reason},
            )
            return ticket

        elif new_status == "ESCALATE":
            whatsapp = get_whatsapp_provider()
            await whatsapp.send_message(
                WhatsAppMessage(
                    to_phone="ZONAL_OFFICER_PHONE",
                    body=f"Ticket {ticket.ticket_code} escalated.",
                )
            )
            await AuditRepo.write(
                action="TICKET_ESCALATED",
                ticket_id=str(ticket.id),
                actor_id=actor_id,
                actor_role=actor_role,
                old_value={"status": old_status},
                new_value={"status": old_status, "reason": reason},
            )
            return ticket

        else:
            ticket = await TicketRepo.update_status(ticket, new_status)

            if new_status == TicketStatus.ASSIGNED:
                ticket = await TicketRepo.assign_officer(ticket, actor_id)

            await AuditRepo.write(
                action="STATUS_CHANGED",
                ticket_id=str(ticket.id),
                actor_id=actor_id,
                actor_role=actor_role,
                old_value={"status": old_status},
                new_value={"status": new_status, "reason": reason},
            )
            return ticket
