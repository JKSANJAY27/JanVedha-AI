from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class VoiceComplaintData:
    """Structured data extracted from a voice call."""
    raw_transcript: str
    language_detected: str
    location_text: str
    issue_description: str
    severity_signals: list[str]  # safety keywords detected
    caller_phone: str
    call_id: str

@dataclass
class IVRCallRequest:
    to_phone: str
    ticket_code: str
    issue_summary: str
    language: str

@dataclass
class IVRResponse:
    ticket_code: str
    digit_pressed: str   # "1" fixed | "2" partial | "3" not fixed | "timeout"
    call_id: str

class VoiceProvider(ABC):

    @abstractmethod
    async def handle_inbound_call(self, call_data: dict) -> VoiceComplaintData:
        """
        Handle an inbound citizen complaint call.
        Conduct multilingual conversation, extract structured data, return it.
        """
        pass

    @abstractmethod
    async def make_ivr_verification_call(self, request: IVRCallRequest) -> str:
        """
        Make an outbound IVR call to citizen for complaint verification.
        Returns call_id. Result comes via webhook to /api/webhooks/ivr/callback.
        """
        pass
