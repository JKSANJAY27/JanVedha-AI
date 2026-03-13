import asyncio
import os
import sys
import random
from datetime import datetime, timedelta

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.mongodb.models.ticket import TicketMongo
from app.enums import TicketSource, TicketStatus, PriorityLabel

async def seed_tickets():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client.janvedha_db
    await init_beanie(database=db, document_models=[TicketMongo])
    
    # Check if tickets already exist for ward 1
    existing_count = await TicketMongo.find(TicketMongo.ward_id == 1).count()
    if existing_count > 0:
        print(f"Ward 1 already has {existing_count} tickets. Deleting them to re-seed...")
        await TicketMongo.find(TicketMongo.ward_id == 1).delete()

    print("Seeding tickets for Ward 1...")
    
    # Ward 1 coordinates roughly (Latitude, Longitude) - e.g. some central point
    # We'll use [Longitude, Latitude] for GeoJSON
    BASE_LON = 80.27
    BASE_LAT = 13.08
    
    tickets_to_insert = []
    
    now = datetime.utcnow()
    
    # 1. Create a cluster of potholes for Root Cause Radar
    # To cluster, they need to be within 300m. 0.001 degrees is ~111m.
    for i in range(5):
        t = TicketMongo(
            ticket_code=f"TKT-POTHOLE-{random.randint(1000, 9999)}",
            ward_id=1,
            dept_id="D01", # Roads
            source=TicketSource.WEB_PORTAL,
            description=f"Deep pothole causing accidents near main junction #{i}",
            citizen_name="Citizen",
            citizen_phone="9999999999",
            location={
                "type": "Point",
                "coordinates": [BASE_LON + random.uniform(-0.0005, 0.0005), BASE_LAT + random.uniform(-0.0005, 0.0005)]
            },
            issue_category="pothole",
            status=TicketStatus.OPEN,
            priority_label=PriorityLabel.HIGH,
            created_at=now - timedelta(days=random.randint(0, 3)),
        )
        t.sla_deadline = t.created_at + timedelta(days=14)
        tickets_to_insert.append(t)

    # 2. Create another cluster for Water Logging
    for i in range(4):
        t = TicketMongo(
            ticket_code=f"TKT-WATER-{random.randint(1000, 9999)}",
            ward_id=1,
            dept_id="D04", # Sewage
            source=TicketSource.SOCIAL_MEDIA,
            description=f"Severe water logging, drain is blocked #{i}",
            citizen_name="Citizen2",
            citizen_phone="8888888888",
            location={
                "type": "Point",
                "coordinates": [BASE_LON + 0.005 + random.uniform(-0.0005, 0.0005), BASE_LAT + 0.005 + random.uniform(-0.0005, 0.0005)]
            },
            issue_category="water_logging",
            status=TicketStatus.OPEN,
            priority_label=PriorityLabel.CRITICAL,
            created_at=now - timedelta(days=random.randint(0, 2)),
        )
        t.sla_deadline = t.created_at + timedelta(days=3)
        tickets_to_insert.append(t)

    # 3. Add some random scattered tickets
    categories = ["garbage", "street_light", "mosquito", "pipeline_leak"]
    for i in range(15):
        cat = random.choice(categories)
        t = TicketMongo(
            ticket_code=f"TKT-RAND-{random.randint(1000, 9999)}",
            ward_id=1,
            dept_id="D00",
            source=TicketSource.WEB_PORTAL,
            description=f"Random issue about {cat}",
            citizen_name="Random Citizen",
            citizen_phone="7777777777",
            location={
                "type": "Point",
                "coordinates": [BASE_LON + random.uniform(-0.02, 0.02), BASE_LAT + random.uniform(-0.02, 0.02)]
            },
            issue_category=cat,
            status=random.choice([TicketStatus.OPEN, TicketStatus.CLOSED]),
            priority_label=PriorityLabel.MEDIUM,
            created_at=now - timedelta(days=random.randint(0, 7)),
        )

        t.source = TicketSource.WEB_PORTAL
        t.sla_deadline = t.created_at + timedelta(days=7)
        tickets_to_insert.append(t)
        
    await TicketMongo.insert_many(tickets_to_insert)
    print(f"Successfully seeded {len(tickets_to_insert)} tickets for Ward 1.")

if __name__ == "__main__":
    asyncio.run(seed_tickets())
