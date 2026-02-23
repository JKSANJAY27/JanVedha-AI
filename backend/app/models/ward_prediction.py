from sqlalchemy import Column, Integer, String, Float, Text, DateTime
from datetime import datetime
from .base import Base

class WardPrediction(Base):
    __tablename__ = "ward_predictions"
    id = Column(Integer, primary_key=True)
    ward_id = Column(Integer, nullable=False)
    current_score = Column(Float)
    predicted_next_month_score = Column(Float)
    risk_level = Column(String(20))
    ai_recommendation = Column(Text)
    computed_at = Column(DateTime, default=datetime.utcnow)
