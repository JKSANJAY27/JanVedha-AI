"""
SLAService — MongoDB-backed SLA breach detection and escalation.
Rewritten to use TicketMongo (Beanie) instead of SQLAlchemy.
"""
from datetime import datetime
from typing import Optional
import logging

from app.mongodb.models.ticket import TicketMongo
from app.enums import TicketStatus
from app.services.audit_service import write_audit
from app.core.container import get_whatsapp_provider
from app.interfaces.notification_provider import WhatsAppMessage

logger = logging.getLogger(__name__)


class SLAService:
    @staticmethod
    async def process_sla_breaches() -> int:
        """
        Finds open/assigned tickets past their SLA deadline.
        Issues WhatsApp alerts and writes audit entries.
        Returns count of breached tickets processed.
        """
        now = datetime.utcnow()

        breached_tickets = await TicketMongo.find(
            TicketMongo.status.in_([TicketStatus.OPEN, TicketStatus.ASSIGNED]),
            TicketMongo.sla_deadline < now,
        ).to_list()

        wa = get_whatsapp_provider()

        for ticket in breached_tickets:
            ticket_id_str = str(ticket.id)

            await write_audit(
                action="SLA_BREACHED",
                ticket_id=ticket_id_str,
                new_value={"deadline": ticket.sla_deadline.isoformat() if ticket.sla_deadline else None},
            )

            if ticket.status == TicketStatus.OPEN:
                ticket.status = TicketStatus.ASSIGNED
                await ticket.save()
                await write_audit(
                    action="AUTO_ESCALATED_SLA_BREACH",
                    ticket_id=ticket_id_str,
                )

            try:
                await wa.send_message(WhatsAppMessage(
                    to_phone="dummy_officer",
                    body=f"URGENT: Ticket {ticket.ticket_code} breached SLA deadline. Immediate action required.",
                ))
            except Exception as exc:
                logger.warning("WhatsApp SLA alert failed (non-critical): %s", exc)

        return len(breached_tickets)
