from app.interfaces.ai_provider import AIProvider, ClassificationResult, VisionResult, DraftResult

class StubAIAdapter(AIProvider):
    async def classify_complaint(self, text, image_url=None):
        return ClassificationResult(
            dept_id="D02", dept_name="Roads/Bridges",
            issue_summary=text[:100], location_extracted="",
            language_detected="en", confidence=0.9,
            needs_clarification=False, requires_human_review=False
        )
    async def verify_work_completion(self, before_url, after_url, issue_type):
        return VisionResult(work_completed=True, is_genuine_fix=True,
                            confidence=0.9, explanation="Stub", requires_human_review=False)
    async def draft_communication(self, context, communication_type, language):
        return DraftResult(content="Draft content placeholder", language=language)
    async def generate_ward_recommendation(self, ward_stats, risk_level):
        return "Stub recommendation"
