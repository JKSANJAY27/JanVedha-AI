from app.interfaces.notification_provider import SMSProvider, SMSMessage, NotificationResult


class MSG91Adapter(SMSProvider):
    """Stub implementation of MSG91 SMS provider."""

    async def send_message(self, message: SMSMessage) -> NotificationResult:
        """Stub implementation - returns success."""
        return NotificationResult(
            success=True,
            message_id=f"msg_{message.to_phone}",
            error=None
        )
