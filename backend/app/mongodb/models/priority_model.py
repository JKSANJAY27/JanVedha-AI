"""
MongoDB Document: PriorityModel

Stores the serialized scikit-learn model state for the self-learning priority scorer.
The model is a SGDClassifier that uses partial_fit() for online/incremental learning.
"""
from beanie import Document
from pydantic import Field
from typing import List, Optional
from datetime import datetime


class PriorityModelMongo(Document):
    """
    Persists the binary ML model state in MongoDB so the classifier
    survives server restarts and improves over time.
    Collection: priority_models
    """
    version: int = 1
    model_bytes: bytes = b""          # joblib-serialized SGDClassifier
    scaler_bytes: bytes = b""         # joblib-serialized StandardScaler
    feature_names: List[str] = Field(default_factory=list)
    accuracy: float = 0.0
    trained_at: datetime = Field(default_factory=datetime.utcnow)
    sample_count: int = 0             # total training samples seen
    is_active: bool = True            # only one active model at a time

    class Settings:
        name = "priority_models"

    class Config:
        populate_by_name = True
