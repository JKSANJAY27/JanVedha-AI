import asyncio
import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.mongodb.database import init_mongodb, close_mongodb
from app.mongodb.models import UserMongo

async def list_users():
    await init_mongodb()
    users = await UserMongo.find_all().to_list()
    for u in users:
        print(f"Email: {u.email}, Role: {u.role}, Name: {u.name}")
    await close_mongodb()

if __name__ == "__main__":
    asyncio.run(list_users())
