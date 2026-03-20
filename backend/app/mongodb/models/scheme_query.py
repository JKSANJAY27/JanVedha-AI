"""
MongoDB Document: SchemeQuery

Records historical requests to the Scheme Eligibility Advisor.
Collection: scheme_queries
"""
from beanie import Document, Indexed
from pydantic import Field
from typing import Optional, Dict, Any
from datetime import datetime

class SchemeQueryMongo(Document):
    constituent_profile: str
    ward_id: Optional[Indexed(int)] = None # type: ignore[valid-type]
    councillor_user_id: Optional[Indexed(str)] = None # type: ignore[valid-type]
    
    # The structured result from the RAG pipeline
    result: Optional[Dict[str, Any]] = None
    
    # Langfuse tracing
    langfuse_trace_id: Optional[str] = None
    
    # User feedback loop
    feedback_score: Optional[int] = None # e.g. 1 for thumbs up, 0 for thumbs down
    
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "scheme_queries"
        indexes = [
            "councillor_user_id",
            "created_at"
        ]
