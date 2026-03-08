import asyncio
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
from app.mongodb.models.scheduled_event import ScheduledEventMongo
from app.mongodb.models.ticket import TicketMongo

async def run():
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db = client.civicai
    await init_beanie(database=db, document_models=[ScheduledEventMongo, TicketMongo])

    events = await ScheduledEventMongo.find(ScheduledEventMongo.event_type == 'deadline').to_list()
    
    for e in events:
        print(f"Tk: {e.ticket_code}, Ward: {e.ward_id} (Type: {type(e.ward_id)})")

if __name__ == "__main__":
    asyncio.run(run())
