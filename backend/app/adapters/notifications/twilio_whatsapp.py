from app.interfaces.notification_provider import WhatsAppProvider, WhatsAppMessage, NotificationResult


class TwilioWhatsAppAdapter(WhatsAppProvider):
    """Stub implementation of Twilio WhatsApp provider."""

    async def send_message(self, message: WhatsAppMessage) -> NotificationResult:
        """Stub implementation - returns success."""
        return NotificationResult(
            success=True,
            message_id=f"msg_{message.to_phone}",
            error=None
        )
