from app.interfaces.notification_provider import EmailProvider, EmailMessage, NotificationResult


class SendGridAdapter(EmailProvider):
    """Stub implementation of SendGrid email provider."""

    async def send_email(self, message: EmailMessage) -> NotificationResult:
        """Stub implementation - returns success."""
        return NotificationResult(
            success=True,
            message_id=f"email_{message.to_email}",
            error=None
        )
