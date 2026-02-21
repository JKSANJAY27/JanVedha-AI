from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from fastapi import HTTPException
from datetime import datetime, timedelta

from app.models.ticket import Ticket, TicketSource, TicketStatus
from app.models.department import Department
from app.core.priority import calculate_priority_score
from app.core.ticket_codes import generate_ticket_code
from app.core.container import get_ai_provider, get_blockchain_provider, get_sms_provider, get_whatsapp_provider
from app.interfaces.notification_provider import SMSMessage, WhatsAppMessage
from app.services.audit_service import write_audit

class TicketService:
    @staticmethod
    async def create_ticket(
        db: AsyncSession, 
        description: str,
        location_text: str,
        reporter_phone: str,
        consent_given: bool,
        reporter_name: str = None,
        photo_url: str = None,
        language: str = "en",
        source: str = TicketSource.WEB_PORTAL
    ) -> Ticket:
        # 1. DPDP Compliance
        if not consent_given:
            raise HTTPException(status_code=400, detail="Consent is strictly required to process a ticket")
            
        # 2. AI Classification
        ai = get_ai_provider()
        classification = await ai.classify_complaint(description, photo_url)
        
        if classification.confidence < 0.75 or classification.needs_clarification:
            raise HTTPException(
                status_code=400, 
                detail={"message": "Please clarify your complaint", "question": classification.clarification_question}
            )

        # 3. Department SLA Look up
        dept_result = await db.execute(select(Department).where(Department.dept_id == classification.dept_id))
        dept = dept_result.scalar_one_or_none()
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
            description=description
        )

        # 5. DB Insertion
        score_val, label_val = score
        
        ticket = Ticket(
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
            sla_deadline=sla_deadline
        )
        
        db.add(ticket)
        await db.flush() # flush to get ticket ID for audit and blockchain
        
        # 6. Auditing
        await write_audit(
            db=db, 
            action="TICKET_CREATED", 
            ticket_id=ticket.id, 
            new_value={"dept_id": ticket.dept_id, "score": score}
        )

        # 7. Immutable Ledger Record
        blockchain = get_blockchain_provider()
        import hashlib
        data_hash = hashlib.sha256(f"{ticket.id}-{ticket.created_at}".encode()).hexdigest()
        await blockchain.record_hash(data_hash, "TICKET_CREATED")
        ticket.blockchain_hash = data_hash

        # 8. Trigger Notifications (Async in reality, but awaited here sequentially for stub)
        sms = get_sms_provider()
        await sms.send_message(SMSMessage(to_phone=reporter_phone, body=f"Your ticket {ticket.ticket_code} is created."))
        
        return ticket

    @staticmethod
    async def change_status(
        db: AsyncSession, 
        ticket_id: int, 
        new_status: str, 
        actor_id: int, 
        actor_role: str,
        reason: str = None
    ) -> Ticket:
        result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
        ticket = result.scalar_one_or_none()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        old_status = ticket.status
        ticket.status = new_status
        
        if new_status == TicketStatus.ASSIGNED:
            ticket.assigned_officer_id = actor_id
            ticket.assigned_at = datetime.utcnow()
        elif new_status == TicketStatus.CLOSED:
            ticket.resolved_at = datetime.utcnow()
            
        await write_audit(
            db=db, 
            action="STATUS_CHANGED", 
            ticket_id=ticket.id, 
            actor_id=actor_id,
            actor_role=actor_role,
            old_value={"status": old_status}, 
            new_value={"status": new_status, "reason": reason}
        )
        await db.flush()
        return ticket
