"""
MongoDB Document: Grievance

Raw ingested public grievance — scraped from external sources,
AI-structured via Gemini, and optionally auto-converted to a TicketMongo.
Collection: grievances
"""
from beanie import Document, Indexed
from pydantic import Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class GrievanceMongo(Document):
    """
    A scraped public grievance enriched by Gemini AI.
    Acts as a staging area before ticket creation.
    """
    # ── Source identification ─────────────────────────────────────────────
    source_platform: Indexed(str)                    # type: ignore[valid-type]
    source_id: str = ""                              # dedup key from source
    source_url: str = ""
    raw_content: str = ""                            # original unprocessed text
    author: Optional[str] = None

    # ── AI-structured fields (filled by Gemini) ──────────────────────────
    structured_summary: Optional[str] = None
    category: Optional[str] = None                   # maps to DEPARTMENT_CATALOGUE
    subcategory: Optional[str] = None
    dept_id: Optional[str] = None                    # AI-mapped department
    location_text: Optional[str] = None
    ward_id: Optional[Indexed(int)] = None           # type: ignore[valid-type]

    # ── Severity assessment ──────────────────────────────────────────────
    severity: str = "low"                            # "critical" | "high" | "medium" | "low"
    severity_score: float = 0.0                      # 0.0 - 1.0
    severity_reasoning: Optional[str] = None         # AI explanation for severity
    sentiment: str = "neutral"                       # "negative" | "neutral" | "positive"
    affected_population: Optional[int] = None        # estimated people affected

    # ── Auto-ticketing ───────────────────────────────────────────────────
    auto_ticket_generated: bool = False
    ticket_id: Optional[str] = None                  # linked TicketMongo ObjectId
    ticket_code: Optional[str] = None

    # ── Lifecycle ────────────────────────────────────────────────────────
    status: Indexed(str) = "pending"                 # type: ignore[valid-type]
    # "pending" | "processed" | "ticket_created" | "dismissed"
    reviewed_by: Optional[str] = None                # officer who reviewed

    # ── Timestamps ───────────────────────────────────────────────────────
    original_timestamp: Optional[datetime] = None
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None

    # ── Scraper metadata ─────────────────────────────────────────────────
    keywords: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Settings:
        name = "grievances"
        indexes = [
            "source_platform",
            "severity",
            "ward_id",
            "status",
            "ingested_at",
        ]

    class Config:
        populate_by_name = True
