from app.interfaces.voice_provider import VoiceProvider, VoiceComplaintData, IVRCallRequest, IVRResponse


class VomyraAdapter(VoiceProvider):
    """Stub implementation of Vomyra voice provider."""

    async def handle_inbound_call(self, call_data: dict) -> VoiceComplaintData:
        """Stub implementation - returns default voice complaint data."""
        return VoiceComplaintData(
            raw_transcript="Sample voice complaint transcript",
            language_detected="en",
            location_text="Unknown Location",
            issue_description="Issue reported via voice call",
            severity_signals=[],
            caller_phone=call_data.get("from_phone", ""),
            call_id=call_data.get("call_id", "unknown")
        )

    async def make_ivr_verification_call(self, request: IVRCallRequest) -> str:
        """Stub implementation - returns a mock call ID."""
        return f"call_{request.to_phone}_{request.ticket_code}"
