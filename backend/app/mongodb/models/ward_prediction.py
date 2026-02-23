"""
MongoDB Document: WardPrediction

Mirrors app/models/ward_prediction.py (SQLAlchemy) → Beanie ODM.
Stores AI-generated ward health scores and risk predictions.
"""
from beanie import Document, Indexed
from pydantic import Field
from typing import Optional
from datetime import datetime


class WardPredictionMongo(Document):
    """
    AI-computed health score and next-month prediction for a given ward.
    Collection: ward_predictions
    """
    ward_id: Indexed(int)                        # type: ignore[valid-type]
    current_score: Optional[float] = None
    predicted_next_month_score: Optional[float] = None
    risk_level: Optional[str] = Field(None, max_length=20)   # e.g. "HIGH", "MEDIUM"
    ai_recommendation: Optional[str] = None
    computed_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "ward_predictions"
        indexes = [
            "ward_id",
            "computed_at",
            "risk_level",
        ]

    class Config:
        populate_by_name = True
