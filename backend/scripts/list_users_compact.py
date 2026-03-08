import asyncio
import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.config import settings
from motor.motor_asyncio import AsyncIOMotorClient

async def list_users():
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db_name = settings.MONGODB_URI.rsplit("/", 1)[-1].split("?")[0] or "civicai"
    db = client[db_name]
    users_col = db["users"]
    
    users = await users_col.find().to_list(100)
    for u in users:
        print(f"U:{u.get('email')} R:{u.get('role')} N:{u.get('name')}")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(list_users())
