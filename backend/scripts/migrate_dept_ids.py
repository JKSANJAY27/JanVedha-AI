import asyncio
import os
import sys
from motor.motor_asyncio import AsyncIOMotorClient

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

async def migrate():
    # Load URI from setting and avoid hardcoding secrets
    from app.core.config import settings
    uri = settings.MONGODB_URI
    
    client = AsyncIOMotorClient(uri)
    db = client["janvedha"]
    col = db["tickets"]

    mapping = {
        "roads": "D01",
        "PWD": "D01",
        "water": "D03",
        "WATER": "D03",
        "drainage": "D04",
        "DRAINAGE": "D04",
        "waste": "D05",
        "SWM": "D05",
        "lighting": "D06",
        "ELEC": "D06",
        "health": "D08",
        "sanitation": "D08",
        "traffic": "D10",
    }

    print("Starting migration of dept_id for tickets...")
    count = 0
    for old, new in mapping.items():
        result = await col.update_many(
            {"dept_id": old},
            {"$set": {"dept_id": new}}
        )
        if result.modified_count > 0:
            print(f"Updated {result.modified_count} tickets from '{old}' to '{new}'")
            count += result.modified_count

    print(f"Migration finished. Total tickets updated: {count}")

    print("Starting migration of dept_id for users...")
    user_count = 0
    # Specific corrections for common seed errors
    user_mapping = [
        ({"name": {"$regex": "Electrical"}}, "D06"),
        ({"name": {"$regex": "Lighting"}}, "D06"),
        ({"name": {"$regex": "Water"}}, "D03"),
        ({"name": {"$regex": "Sanitation"}}, "D08"),
        ({"name": {"$regex": "Health"}}, "D08"),
        ({"name": {"$regex": "Garbage"}}, "D05"),
        ({"name": {"$regex": "Waste"}}, "D05"),
        ({"name": {"$regex": "Solid Waste"}}, "D05"),
        ({"name": {"$regex": "Sewage"}}, "D04"),
        ({"name": {"$regex": "Drainage"}}, "D04"),
        ({"name": {"$regex": "Traffic"}}, "D10"),
        ({"name": {"$regex": "Transport"}}, "D10"),
    ]
    for query, new in user_mapping:
        result = await db["users"].update_many(
            query,
            {"$set": {"dept_id": new}}
        )
        if result.modified_count > 0:
            print(f"Updated {result.modified_count} users to '{new}'")
            user_count += result.modified_count

    print(f"User migration finished. Total users updated: {user_count}")
    client.close()

if __name__ == "__main__":
    asyncio.run(migrate())
