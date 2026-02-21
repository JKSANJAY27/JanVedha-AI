from app.interfaces.voice_provider import VoiceProvider, VoiceComplaintData, IVRCallRequest

class StubVoiceAdapter(VoiceProvider):
    async def handle_inbound_call(self, call_data):
        return VoiceComplaintData(
            raw_transcript="Stub transcript",
            language_detected="en",
            location_text="",
            issue_description="Stub complaint from voice call",
            severity_signals=[],
            caller_phone=call_data.get("From", ""),
            call_id=call_data.get("CallSid", "")
        )
    async def make_ivr_verification_call(self, request):
        return "stub_call_id"
