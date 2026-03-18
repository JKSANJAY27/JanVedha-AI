"""
Proactive Citizen Communication Engine — Feature 2.

Sends AI-generated Telegram notifications at each key ticket lifecycle moment.
Triggers: open → assigned → in_progress → resolved
"""
import logging
from datetime import datetime
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# ─── Gemini message generation ────────────────────────────────────────────────

async def generate_citizen_message(
    event_type: str,
    issue_type: str,
    location_name: str,
    ticket_id: str,
    ward_name: str,
    language: str = "English",
    extra_context: str = "",
    portal_link: str = "https://janvedha.gov.in",
    verification_statement: Optional[str] = None,
) -> str:
    """Call Gemini to generate a warm, local-language citizen notification."""
    if not settings.GEMINI_API_KEY:
        return _fallback_message(event_type, issue_type, ticket_id, portal_link)

    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")

        resolved_extra = ""
        if event_type == "issue_resolved" and verification_statement:
            resolved_extra = f"\nVerification: {verification_statement}"

        prompt = f"""You are a helpful civic assistant for {ward_name} Municipal Corporation.
Write a SHORT (2-3 sentence) citizen notification message for this event:
Event: {event_type}
Issue: {issue_type} reported at {location_name}
Ticket ID: {ticket_id}{resolved_extra}
Additional context: {extra_context}
Rules:
- Warm, respectful tone
- Write in {language}
- End with the ticket tracking link: {portal_link}/track/{ticket_id}
- Do NOT use corporate jargon
- Keep it under 200 characters per sentence"""

        response = await model.generate_content_async(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini notification generation failed: {e}")
        return _fallback_message(event_type, issue_type, ticket_id, portal_link)


def _fallback_message(event_type: str, issue_type: str, ticket_id: str, portal_link: str) -> str:
    messages = {
        "ticket_acknowledged": f"✅ Your complaint about '{issue_type}' has been registered (ID: {ticket_id}). Our team will review it shortly. Track at: {portal_link}/track/{ticket_id}",
        "technician_assigned": f"👷 Good news! A technician has been assigned to your '{issue_type}' complaint (ID: {ticket_id}). Work will begin soon. Track at: {portal_link}/track/{ticket_id}",
        "work_started": f"🔧 Work has started on your '{issue_type}' complaint (ID: {ticket_id}). We'll notify you once it's resolved. Track at: {portal_link}/track/{ticket_id}",
        "issue_resolved": f"🎉 Your '{issue_type}' complaint (ID: {ticket_id}) has been resolved. Thank you for helping us improve our city! Track at: {portal_link}/track/{ticket_id}",
    }
    return messages.get(event_type, f"Update on your complaint (ID: {ticket_id}). Track at: {portal_link}/track/{ticket_id}")


# ─── Telegram delivery ────────────────────────────────────────────────────────

async def send_telegram_message(chat_id: str, message: str) -> bool:
    """Send a message via Telegram Bot API. Returns True on success."""
    if not settings.TELEGRAM_BOT_TOKEN or not chat_id:
        logger.warning("Telegram not configured or no chat_id — skipping notification")
        return False

    try:
        import httpx
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML",
            })
            resp.raise_for_status()
            return True
    except Exception as e:
        logger.error(f"Telegram send failed for chat_id {chat_id}: {e}")
        return False


# ─── Main notification trigger ────────────────────────────────────────────────

async def notify_citizen(
    ticket_id: str,
    event_type: str,
    verification_statement: Optional[str] = None,
) -> None:
    """
    Called at ticket status transitions. Generates an AI message and sends
    it via Telegram. Logs to the notifications collection.
    """
    from app.mongodb.models.ticket import TicketMongo
    from app.mongodb.models.notification import NotificationMongo
    from app.mongodb.models.ward_config import WardConfigMongo
    from app.mongodb.models.user import UserMongo
    from beanie import PydanticObjectId

    try:
        ticket = await TicketMongo.get(PydanticObjectId(ticket_id))
        if not ticket:
            return

        # Get ward config for language preference
        ward_cfg = None
        if ticket.ward_id:
            ward_cfg = await WardConfigMongo.find_one(WardConfigMongo.ward_id == ticket.ward_id)

        language = ward_cfg.preferred_language if ward_cfg else "English"
        notifications_enabled = ward_cfg.proactive_notifications_enabled if ward_cfg else True
        portal_link = ward_cfg.portal_link if ward_cfg else "https://janvedha.gov.in"
        ward_name = (ward_cfg.ward_name if ward_cfg and ward_cfg.ward_name else f"Ward {ticket.ward_id}") if ticket.ward_id else "Municipal"

        if not notifications_enabled:
            return

        issue_type = ticket.issue_category or ticket.dept_id or "civic issue"
        location_name = ticket.location_text or ticket.coordinates or "your area"

        # Extra context per event
        extra_context = ""
        if event_type == "technician_assigned" and ticket.technician_id:
            tech = await UserMongo.get(PydanticObjectId(ticket.technician_id))
            if tech:
                extra_context = f"Assigned technician: {tech.name}"
        elif event_type == "work_started" and ticket.scheduled_date:
            extra_context = f"Scheduled for: {ticket.scheduled_date.strftime('%d %b %Y')}"

        message = await generate_citizen_message(
            event_type=event_type,
            issue_type=issue_type,
            location_name=location_name,
            ticket_id=ticket.ticket_code,
            ward_name=ward_name,
            language=language,
            extra_context=extra_context,
            portal_link=portal_link,
            verification_statement=verification_statement,
        )

        delivered = False
        citizen_id = ticket.reporter_user_id

        # Get telegram_chat_id from user record (stored in phone field as fallback)
        telegram_chat_id = None
        if citizen_id:
            try:
                citizen = await UserMongo.get(PydanticObjectId(citizen_id))
                if citizen and citizen.phone:
                    # Convention: if phone starts with "tg:", it's a Telegram chat ID
                    if citizen.phone.startswith("tg:"):
                        telegram_chat_id = citizen.phone[3:]
            except Exception:
                pass

        if telegram_chat_id:
            delivered = await send_telegram_message(telegram_chat_id, message)

        # Log notification regardless of delivery
        notification = NotificationMongo(
            ticket_id=ticket_id,
            citizen_id=citizen_id,
            telegram_chat_id=telegram_chat_id,
            event_type=event_type,
            message_sent=message,
            language=language,
            ward_id=ticket.ward_id,
            delivered=delivered,
        )
        await notification.insert()
        logger.info(f"Notification logged for ticket {ticket.ticket_code} event={event_type} delivered={delivered}")

    except Exception as e:
        logger.error(f"notify_citizen failed for ticket_id={ticket_id} event={event_type}: {e}")

