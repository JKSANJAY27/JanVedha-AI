from typing import Optional
from datetime import datetime
from pydantic import Field
from beanie import Document
from pymongo import IndexModel, ASCENDING

class Camera(Document):
    camera_id: str
    ward_id: str
    location_description: str
    lat: float
    lng: float
    area_label: str
    status: str = "active"  # active, inactive, maintenance
    installed_date: datetime
    notes: Optional[str] = None

    class Settings:
        name = "cameras"
        indexes = [
            IndexModel([("camera_id", ASCENDING)], unique=True),
            IndexModel([("ward_id", ASCENDING)]),
        ]
