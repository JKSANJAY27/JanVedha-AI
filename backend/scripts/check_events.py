import asyncio
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
from app.mongodb.models.scheduled_event import ScheduledEventMongo
from app.mongodb.models.ticket import TicketMongo

async def run():
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.MONGODB_NAME]
    await init_beanie(database=db, document_models=[ScheduledEventMongo, TicketMongo])
    
    events = await ScheduledEventMongo.find(ScheduledEventMongo.event_type == "deadline").to_list()
    print(f"Found {len(events)} deadline events")
    for e in events:
        print(f"- Tk: {e.ticket_code}, Ward: {e.ward_id}, Dept: {e.dept_id}, Date: {e.scheduled_date}")

if __name__ == "__main__":
    asyncio.run(run())
