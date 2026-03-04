"""
MongoDB Document: PriorityModel

Stores the serialized LightGBM model state for the self-learning priority scorer.
Persists training_X / training_y buffers so the model survives server restarts
and keeps accumulating samples between full retraining cycles.
"""
from beanie import Document
from pydantic import Field
from typing import List, Optional, Any
from datetime import datetime


class PriorityModelMongo(Document):
    """
    Persists the binary LightGBM model state + training buffer in MongoDB so
    the classifier survives server restarts and improves over time.
    Collection: priority_models
    """
    version: int = 2
    model_bytes: bytes = b""          # joblib-serialized LGBMClassifier
    scaler_bytes: bytes = b""         # Reserved (not used for LightGBM)
    feature_names: List[str] = Field(default_factory=list)
    accuracy: float = 0.0
    trained_at: datetime = Field(default_factory=datetime.utcnow)
    sample_count: int = 0             # total training samples seen
    is_active: bool = True            # only one active model at a time

    # Training buffer — accumulated between retraining cycles
    # Each row in training_X is a List[float] feature vector
    training_X: List[List[float]] = Field(default_factory=list)
    training_y: List[int] = Field(default_factory=list)

    class Settings:
        name = "priority_models"

    class Config:
        populate_by_name = True
