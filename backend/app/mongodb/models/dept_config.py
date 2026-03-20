"""
MongoDB Document: DeptConfig

Department configuration — maps ticket categories to departments,
stores SLA targets and visual identity.
Collection: department_config
"""
import uuid
from datetime import datetime
from typing import List, Optional
from beanie import Document, Indexed
from pydantic import Field


class DeptConfigMongo(Document):
    dept_id: Indexed(str, unique=True)  # type: ignore[valid-type]
    dept_name: str
    ticket_categories: List[str]
    sla_days: int
    color_hex: str = "#5F5E5A"
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "department_config"
        indexes = ["dept_id"]

    class Config:
        populate_by_name = True
