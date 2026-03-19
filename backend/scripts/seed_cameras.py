import asyncio
import sys
import os
from datetime import datetime, timedelta
import random

# Add backend directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.mongodb.database import init_mongodb, close_mongodb
from app.mongodb.models.camera import Camera

async def seed_cameras():
    print("Initialising MongoDB...")
    await init_mongodb()
    
    ward_id = "demo_ward_1"
    
    cameras_data = [
        {"camera_id": "CAM-001", "location_description": "Gandhi School main gate, MG Road", "lat": 12.9716, "lng": 80.2443, "area_label": "Zone A - MG Road"},
        {"camera_id": "CAM-002", "location_description": "Adyar bus stop, LB Road junction", "lat": 12.9698, "lng": 80.2456, "area_label": "Zone A - LB Road"},
        {"camera_id": "CAM-003", "location_description": "Near SBI Bank, 4th Main Road", "lat": 12.9732, "lng": 80.2401, "area_label": "Zone B - 4th Main"},
        {"camera_id": "CAM-004", "location_description": "Municipal park entrance, 2nd Cross Street", "lat": 12.9745, "lng": 80.2389, "area_label": "Zone B - Park Area"},
        {"camera_id": "CAM-005", "location_description": "Fish market junction, Canal Road", "lat": 12.9678, "lng": 80.2412, "area_label": "Zone C - Canal Road"},
        {"camera_id": "CAM-006", "location_description": "Primary health center, Hospital Road", "lat": 12.9759, "lng": 80.2467, "area_label": "Zone C - Health Center"},
        {"camera_id": "CAM-007", "location_description": "Overhead water tank junction, Ring Road", "lat": 12.9689, "lng": 80.2378, "area_label": "Zone D - Ring Road"},
        {"camera_id": "CAM-008", "location_description": "Community hall, Temple Street", "lat": 12.9723, "lng": 80.2498, "area_label": "Zone D - Temple St"}
    ]

    print("Clearing existing demo cameras...")
    await Camera.find({"ward_id": ward_id}).delete()

    now = datetime.utcnow()
    docs = []
    
    for c in cameras_data:
        # Random install date in past 2 years
        days_ago = random.randint(10, 700)
        installed = now - timedelta(days=days_ago)
        
        doc = Camera(
            camera_id=c["camera_id"],
            ward_id=ward_id,
            location_description=c["location_description"],
            lat=c["lat"],
            lng=c["lng"],
            area_label=c["area_label"],
            status="active",
            installed_date=installed
        )
        docs.append(doc)

    print(f"Inserting {len(docs)} cameras...")
    await Camera.insert_many(docs)
    print("Done seeding cameras.")
    
    await close_mongodb()

if __name__ == "__main__":
    asyncio.run(seed_cameras())
