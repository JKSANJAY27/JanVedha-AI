"""
Seed test tickets directly into Atlas MongoDB for Ward 1.
Includes geographic clusters for Root Cause Radar testing.
"""
import asyncio
import os
import sys
import random
from datetime import datetime, timedelta

import certifi
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.mongodb.models.ticket import TicketMongo

ATLAS_URI = settings.MONGODB_URI

async def seed_atlas_tickets():
    client = AsyncIOMotorClient(ATLAS_URI, tlsCAFile=certifi.where())
    db_name = ATLAS_URI.rsplit("/", 1)[-1].split("?")[0] or "civicai"
    if not db_name or db_name.startswith("mongodb"):
        db_name = "civicai"
    db = client[db_name]
    
    await init_beanie(database=db, document_models=[TicketMongo])
    
    existing = await TicketMongo.find(TicketMongo.ward_id == 1).count()
    print(f"Existing Ward 1 tickets in Atlas: {existing}")
    
    if existing > 30:
        print("Enough tickets already. Skipping seed.")
        return
    
    # Ward 1 coordinates – Chennai area: [lon, lat]
    BASE_LON = 80.27
    BASE_LAT = 13.08
    
    now = datetime.utcnow()
    tickets = []
    
    # Cluster 1: 5 potholes within 150m of each other
    for i in range(5):
        t = TicketMongo(
            ticket_code=f"TKT-SEED-POT-{random.randint(10000, 99999)}",
            ward_id=1,
            dept_id="D01",
            source="WEB_PORTAL",
            description=f"Pothole causing accidents near junction {i+1}. Road base is severely damaged.",
            reporter_name="Citizen",
            reporter_phone="9999999999",
            location={
                "type": "Point",
                "coordinates": [
                    BASE_LON + random.uniform(-0.0008, 0.0008),
                    BASE_LAT + random.uniform(-0.0008, 0.0008)
                ]
            },
            issue_category="pothole",
            status="OPEN",
            priority_label="HIGH",
            created_at=now - timedelta(days=random.randint(0, 5)),
            sla_deadline=now + timedelta(days=9),
        )
        tickets.append(t)
    
    # Cluster 2: 4 water logging within 200m
    for i in range(4):
        t = TicketMongo(
            ticket_code=f"TKT-SEED-WTR-{random.randint(10000, 99999)}",
            ward_id=1,
            dept_id="D04",
            source="WEB_PORTAL",
            description=f"Water logging near drainage area {i+1}. Drain is blocked for days.",
            reporter_name="Citizen2",
            reporter_phone="8888888888",
            location={
                "type": "Point",
                "coordinates": [
                    BASE_LON + 0.006 + random.uniform(-0.001, 0.001),
                    BASE_LAT + 0.006 + random.uniform(-0.001, 0.001)
                ]
            },
            issue_category="water_logging",
            status="OPEN",
            priority_label="CRITICAL",
            created_at=now - timedelta(days=random.randint(0, 3)),
            sla_deadline=now - timedelta(days=1),  # overdue!
        )
        tickets.append(t)
    
    # Cluster 3: 4 garbage within 100m
    for i in range(4):
        t = TicketMongo(
            ticket_code=f"TKT-SEED-GRB-{random.randint(10000, 99999)}",
            ward_id=1,
            dept_id="D05",
            source="WEB_PORTAL",
            description=f"Garbage pile near residential area {i+1}. Bin not collected in a week.",
            reporter_name="Citizen3",
            reporter_phone="7777777777",
            location={
                "type": "Point",
                "coordinates": [
                    BASE_LON - 0.004 + random.uniform(-0.0005, 0.0005),
                    BASE_LAT - 0.004 + random.uniform(-0.0005, 0.0005)
                ]
            },
            issue_category="garbage",
            status="OPEN",
            priority_label="MEDIUM",
            created_at=now - timedelta(days=random.randint(1, 7)),
            sla_deadline=now + timedelta(days=5),
        )
        tickets.append(t)
    
    # Random scattered tickets (open + closed mix)
    categories = ["mosquito", "street_light", "pipeline_leak", "sewage", "road_damage"]
    for i in range(12):
        cat = random.choice(categories)
        status = random.choice(["OPEN", "CLOSED", "IN_PROGRESS"])
        t = TicketMongo(
            ticket_code=f"TKT-SEED-RND-{random.randint(10000, 99999)}",
            ward_id=1,
            dept_id="D00",
            source="WEB_PORTAL",
            description=f"Complaint about {cat} in the area.",
            reporter_name="Resident",
            reporter_phone="6666666666",
            location={
                "type": "Point",
                "coordinates": [
                    BASE_LON + random.uniform(-0.03, 0.03),
                    BASE_LAT + random.uniform(-0.03, 0.03)
                ]
            },
            issue_category=cat,
            status=status,
            priority_label=random.choice(["LOW", "MEDIUM", "HIGH"]),
            created_at=now - timedelta(days=random.randint(0, 10)),
            sla_deadline=now + timedelta(days=random.randint(-2, 14)),
        )
        tickets.append(t)
    
    await TicketMongo.insert_many(tickets)
    print(f"✅ Inserted {len(tickets)} test tickets into Atlas (Ward 1).")

if __name__ == "__main__":
    asyncio.run(seed_atlas_tickets())
