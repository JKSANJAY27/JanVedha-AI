"""
GeminiAdapter — real LangChain + Gemini implementation of AIProvider.
Delegates to the full AI pipeline services.
"""
from __future__ import annotations

from app.interfaces.ai_provider import AIProvider, ClassificationResult, VisionResult, DraftResult
from app.services.ai import classifier_agent


class GeminiAdapter(AIProvider):
    """
    Real implementation of the AIProvider interface using LangChain + Gemini.
    Core complaint pipeline is handled by the app.services.ai pipeline module.
    This adapter bridges the old AIProvider interface to the new pipeline services.
    """

    async def classify_complaint(
        self, text: str, image_url: str | None = None
    ) -> ClassificationResult:
        result = await classifier_agent.classify_complaint(
            description=text,
            photo_url=image_url,
        )
        # Map to the AIProvider interface's ClassificationResult
        return ClassificationResult(
            dept_id=result.dept_id,
            dept_name=result.dept_name,
            issue_summary=result.issue_summary,
            location_extracted=result.location_extracted,
            language_detected=result.language_detected,
            confidence=result.ai_confidence,
            needs_clarification=result.needs_clarification,
            clarification_question=result.clarification_question,
            requires_human_review=result.requires_human_review,
        )

    async def verify_work_completion(
        self, before_url: str, after_url: str, issue_type: str
    ) -> VisionResult:
        """
        Uses Gemini Vision to compare before/after photos.
        For now returns a structured stub — vision comparison can be added with Gemini Pro vision.
        """
        return VisionResult(
            work_completed=True,
            is_genuine_fix=True,
            confidence=0.85,
            explanation="Work appears to be completed. Manual verification recommended.",
            requires_human_review=True,
        )

    async def draft_communication(
        self, context: dict, communication_type: str, language: str
    ) -> DraftResult:
        """Draft a communication using Gemini."""
        from app.services.ai.gemini_client import get_llm
        from langchain_core.messages import HumanMessage, SystemMessage

        llm = get_llm()
        system = SystemMessage(
            content=f"Draft a brief, professional {communication_type} in {language}."
        )
        human = HumanMessage(content=f"Context: {context}")
        try:
            response = await llm.ainvoke([system, human])
            return DraftResult(content=response.content.strip(), language=language)
        except Exception:
            return DraftResult(
                content="We acknowledge your complaint and will address it soon.",
                language=language,
            )

    async def generate_ward_recommendation(
        self, ward_stats: dict, risk_level: str
    ) -> str:
        from app.services.ai.gemini_client import get_llm
        from langchain_core.messages import HumanMessage

        llm = get_llm()
        try:
            response = await llm.ainvoke([
                HumanMessage(
                    content=(
                        f"Generate a 2-sentence strategic recommendation for a civic ward.\n"
                        f"Risk level: {risk_level}\nStats: {ward_stats}"
                    )
                )
            ])
            return response.content.strip()
        except Exception:
            return f"Ward risk level is {risk_level}. Prioritize preventive maintenance and increase response capacity."
