from app.interfaces.ai_provider import AIProvider, ClassificationResult, VisionResult, DraftResult


class OpenAIAdapter(AIProvider):
    """Stub implementation of OpenAI provider."""

    async def classify_complaint(
        self, text: str, image_url: str | None = None
    ) -> ClassificationResult:
        """Stub implementation - returns default classification."""
        return ClassificationResult(
            dept_id="dept_001",
            dept_name="Public Works",
            issue_summary=text[:100],
            location_extracted="Unknown",
            language_detected="en",
            confidence=0.8,
            needs_clarification=False,
        )

    async def verify_work_completion(
        self, before_url: str, after_url: str, issue_type: str
    ) -> VisionResult:
        """Stub implementation - returns positive verification."""
        return VisionResult(
            work_completed=True,
            is_genuine_fix=True,
            confidence=0.85,
            explanation="Work appears to be completed successfully",
            requires_human_review=False,
        )

    async def draft_response(
        self, issue_summary: str, language: str = "en"
    ) -> DraftResult:
        """Stub implementation - returns sample draft."""
        return DraftResult(
            content="We acknowledge your complaint and will address it soon.",
            language=language,
        )
