from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ClassificationResult:
    dept_id: str
    dept_name: str
    issue_summary: str
    location_extracted: str
    language_detected: str
    confidence: float
    needs_clarification: bool
    clarification_question: str | None = None
    requires_human_review: bool = False

@dataclass
class VisionResult:
    work_completed: bool
    is_genuine_fix: bool
    confidence: float
    explanation: str
    requires_human_review: bool

@dataclass
class DraftResult:
    content: str
    language: str

class AIProvider(ABC):

    @abstractmethod
    async def classify_complaint(
        self, text: str, image_url: str | None = None
    ) -> ClassificationResult:
        """
        Classify a complaint into a department.
        Must return requires_human_review=True if confidence < 0.75.
        Must never raise — return low-confidence result on failure.
        """
        pass

    @abstractmethod
    async def verify_work_completion(
        self, before_url: str, after_url: str, issue_type: str
    ) -> VisionResult:
        """
        Compare before/after photos to verify work is genuinely done.
        Must return requires_human_review=True if confidence < 0.85.
        """
        pass

    @abstractmethod
    async def draft_communication(
        self, context: dict, communication_type: str, language: str
    ) -> DraftResult:
        """
        Draft a rebuttal, announcement, or recommendation.
        Output is always a DRAFT. Never auto-published.
        """
        pass

    @abstractmethod
    async def generate_ward_recommendation(
        self, ward_stats: dict, risk_level: str
    ) -> str:
        """Generate a strategic recommendation for a ward."""
        pass
