import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import certifi
import os
import sys

# Add backend directory to sys.path to import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from app.core.config import settings

async def main():
    uri = settings.MONGODB_URI
    client = AsyncIOMotorClient(uri, tlsCAFile=certifi.where())
    db_name = uri.rsplit("/", 1)[-1].split("?")[0] or "civicai"
    db = client[db_name]
    
    cols = await db.list_collection_names()
    for col in cols:
        try:
            await db[col].drop_index("dept_id_1")
            print(f"Dropped dept_id_1 from {col}")
        except Exception as e:
            # It's fine if the index doesn't exist on this collection
            pass
    
    print("Finished checking and dropping indexes.")

if __name__ == "__main__":
    asyncio.run(main())
