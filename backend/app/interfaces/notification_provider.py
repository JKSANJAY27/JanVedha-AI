from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class WhatsAppMessage:
    to_phone: str          # with country code: +919876543210
    body: str
    template_name: str | None = None
    template_params: list | None = None

@dataclass
class SMSMessage:
    to_phone: str
    body: str

@dataclass
class EmailMessage:
    to_email: str
    subject: str
    html_body: str
    attachment_url: str | None = None
    attachment_name: str | None = None

@dataclass
class NotificationResult:
    success: bool
    message_id: str | None = None
    error: str | None = None

class WhatsAppProvider(ABC):
    @abstractmethod
    async def send_message(self, message: WhatsAppMessage) -> NotificationResult:
        pass

class SMSProvider(ABC):
    @abstractmethod
    async def send_message(self, message: SMSMessage) -> NotificationResult:
        pass

class EmailProvider(ABC):
    @abstractmethod
    async def send_email(self, message: EmailMessage) -> NotificationResult:
        pass
