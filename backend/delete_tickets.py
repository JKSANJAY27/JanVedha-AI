import asyncio
import os
import sys

# Add backend directory to sys.path so we can import app modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from app.core.config import settings
from app.mongodb.models.ticket import TicketMongo

async def delete_all_tickets():
    print(f"Connecting to MongoDB at {settings.MONGODB_URI}")
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db_name = settings.MONGODB_URI.split("/")[-1]
    db = client.get_database(db_name)
    
    await init_beanie(database=db, document_models=[TicketMongo])
    
    count = await TicketMongo.count()
    print(f"Found {count} tickets.")
    
    if count > 0:
        print("Deleting all tickets...")
        await TicketMongo.find_all().delete()
        print("Successfully deleted all tickets.")
    else:
        print("No tickets to delete.")

if __name__ == "__main__":
    asyncio.run(delete_all_tickets())
