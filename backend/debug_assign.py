import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.core.config import settings
from app.mongodb.models.ticket import TicketMongo
from app.mongodb.models.user import UserMongo

async def test_assign():
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db_name = settings.MONGODB_URI.split("/")[-1].split("?")[0]
    print(f"db_name is {db_name}")
    db = client.get_database(db_name)
    await init_beanie(database=db, document_models=[TicketMongo, UserMongo])
    
    tickets = await TicketMongo.find_all().to_list()
    print(f"Total tickets: {len(tickets)}")
    for t in tickets:
        print(f"Ticket: {t.ticket_code}, dept: {t.dept_id}, ward: {t.ward_id}")
    
    techs = await UserMongo.find(UserMongo.role == "FIELD_STAFF").to_list()
    print(f"Total techs field staff: {len(techs)}")
    for t in techs:
        print(f"Tech: {t.name[:5]}..., dept: {t.dept_id}, ward: {t.ward_id}")

if __name__ == "__main__":
    asyncio.run(test_assign())
