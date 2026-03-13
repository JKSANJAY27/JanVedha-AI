"""
MongoDB Document: WardConfig

Per-ward configuration for notification preferences and language settings.
Collection: ward_configs
"""
from beanie import Document, Indexed
from pydantic import Field
from typing import Optional
from datetime import datetime


class WardConfigMongo(Document):
    ward_id: Indexed(int, unique=True)               # type: ignore[valid-type]
    ward_name: str = ""
    preferred_language: str = "English"              # "English" | "Tamil" | "Hindi"
    proactive_notifications_enabled: bool = True
    portal_link: str = "https://janvedha.gov.in"
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "ward_configs"
        indexes = ["ward_id"]

    class Config:
        populate_by_name = True
