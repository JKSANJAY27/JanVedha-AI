import asyncio
import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.mongodb.database import init_mongodb, close_mongodb
from app.mongodb.models import UserMongo
from app.enums import UserRole
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

async def seed_users():
    print("Connecting to MongoDB...")
    # Get configuration from settings
    from app.core.config import settings
    from motor.motor_asyncio import AsyncIOMotorClient
    import hashlib
    import bcrypt

    def get_password_hash(password: str) -> str:
        digest = hashlib.sha256(password.encode("utf-8")).hexdigest().encode("utf-8")
        return bcrypt.hashpw(digest, bcrypt.gensalt()).decode("utf-8")

    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db_name = settings.MONGODB_URI.rsplit("/", 1)[-1].split("?")[0] or "civicai"
    db = client[db_name]
    users_col = db["users"]
    
    mock_users = [
        {
            "name": "Super Admin Service",
            "email": "admin@janvedha.ai",
            "phone": "0000000000",
            "role": "SUPER_ADMIN",
            "password": "Admin@123",
        },
        {
            "name": "Commissioner Head",
            "email": "admin@janvedha.com",
            "phone": "9999999999",
            "role": "SUPER_ADMIN",
            "password": "password123",
        },
        {
            "name": "Ward 1 Supervisor",
            "email": "pgo@janvedha.com",
            "phone": "8888888888",
            "role": "SUPERVISOR",
            "ward_id": 1,
            "password": "password123",
        },
        {
            "name": "Electrical Dept Head",
            "email": "dept@janvedha.com",
            "phone": "7777777777",
            "role": "JUNIOR_ENGINEER",
            "ward_id": 1,
            "dept_id": "D05",
            "password": "password123",
        },
        {
            "name": "Sanitation Dept Head",
            "email": "sanitation@janvedha.com",
            "phone": "7777777778",
            "role": "JUNIOR_ENGINEER",
            "ward_id": 1,
            "dept_id": "D08",
            "password": "password123",
        },
        {
            "name": "Water Supply Head",
            "email": "water@janvedha.com",
            "phone": "7777777779",
            "role": "JUNIOR_ENGINEER",
            "ward_id": 1,
            "dept_id": "D01",
            "password": "password123",
        },
        {
            "name": "Field Technician - Elec",
            "email": "tech@janvedha.com",
            "phone": "6666666666",
            "role": "FIELD_STAFF",
            "ward_id": 1,
            "dept_id": "D05",
            "password": "password123",
        },
        {
            "name": "Ward 1 Councillor",
            "email": "councillor@janvedha.com",
            "phone": "5555555555",
            "role": "COUNCILLOR",
            "ward_id": 1,
            "password": "password123",
        }
    ]

    for data in mock_users:
        # Check if exists
        existing = await users_col.find_one({"email": data["email"]})
        if existing:
            print(f"User {data['email']} already exists. Updating password/role.")
            await users_col.update_one(
                {"email": data["email"]},
                {"$set": {
                    "role": data["role"],
                    "name": data["name"],
                    "password_hash": get_password_hash(data["password"]),
                    "ward_id": data.get("ward_id"),
                    "dept_id": data.get("dept_id"),
                    "is_active": True
                }}
            )
            continue
        
        user_doc = {
            "name": data["name"],
            "email": data["email"],
            "phone": data["phone"],
            "role": data["role"],
            "ward_id": data.get("ward_id"),
            "dept_id": data.get("dept_id"),
            "password_hash": get_password_hash(data["password"]),
            "is_active": True,
            "created_at": datetime.utcnow()
        }
        await users_col.insert_one(user_doc)
        print(f"Created user: {data['email']} (Role: {data['role']})")
        
    print("Done seeding users.")
    client.close()

if __name__ == "__main__":
    from datetime import datetime
    asyncio.run(seed_users())

