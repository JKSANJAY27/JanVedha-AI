from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, and_, text
from datetime import datetime

from app.models.ticket import Ticket, TicketStatus
from app.services.audit_service import write_audit
from app.core.container import get_whatsapp_provider
from app.interfaces.notification_provider import WhatsAppMessage

class SLAService:
    @staticmethod
    async def process_sla_breaches(db: AsyncSession):
        """Finds open/assigned tickets past their SLA deadline." 
        Issues Whatsapp alerts and writes audit entries.
        """
        now = datetime.utcnow()
        result = await db.execute(
            select(Ticket)
            .where(
                Ticket.status.in_([TicketStatus.OPEN, TicketStatus.ASSIGNED]),
                Ticket.sla_deadline < now
            )
        )
        breached_tickets = result.scalars().all()
        
        wa = get_whatsapp_provider()
        
        for ticket in breached_tickets:
            # Check if we already flagged the breach (simple proxy: check audit logic later, or state flag)
            # For phase 1, we just do it repeatedly to simulate the rule or we'd add an `is_breached` column
            # In production, either `is_breached` col or query Audit Log
            
            # Action: Escalate SLA Breach
            await write_audit(
                db=db,
                action="SLA_BREACHED",
                ticket_id=ticket.id,
                new_value={"deadline": ticket.sla_deadline.isoformat()}
            )
            
            if ticket.status == TicketStatus.OPEN:
                ticket.status = TicketStatus.ASSIGNED # simplistic escalation in stub
                await write_audit(
                    db=db,
                    action="AUTO_ESCALATED_SLA_BREACH",
                    ticket_id=ticket.id
                )
                
            # Simulate Whatsapp message sent to Officer and Zonal
            await wa.send_message(WhatsAppMessage(
                to_phone="dummy_officer",
                body=f"URGENT: Ticket {ticket.ticket_code} breached SLA"
            ))

        await db.commit()
        return len(breached_tickets)
