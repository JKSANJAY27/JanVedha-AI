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
    await init_mongodb()
    
    mock_users = [
        {
            "name": "Commissioner Head",
            "email": "admin@janvedha.com",
            "phone": "9999999999",
            "role": UserRole.COMMISSIONER,
            "password": "password123",
        },
        {
            "name": "Ward 1 PGO",
            "email": "pgo@janvedha.com",
            "phone": "8888888888",
            "role": UserRole.WARD_OFFICER,
            "ward_id": 1,
            "password": "password123",
        },
        {
            "name": "Electrical Dept Head",
            "email": "dept@janvedha.com",
            "phone": "7777777777",
            "role": UserRole.DEPT_HEAD,
            "ward_id": 1,
            "dept_id": "STREET_LIGHTING",
            "password": "password123",
        },
        {
            "name": "Field Technician - Elec",
            "email": "tech@janvedha.com",
            "phone": "6666666666",
            "role": UserRole.TECHNICIAN,
            "ward_id": 1,
            "dept_id": "STREET_LIGHTING",
            "password": "password123",
        },
        {
            "name": "Ward 1 Councillor",
            "email": "councillor@janvedha.com",
            "phone": "5555555555",
            "role": UserRole.COUNCILLOR,
            "ward_id": 1,
            "password": "password123",
        }
    ]

    for data in mock_users:
        # Check if exists
        existing = await UserMongo.find_one(UserMongo.email == data["email"])
        if existing:
            print(f"User {data['email']} already exists. Skipping.")
            continue
        
        user = UserMongo(
            name=data["name"],
            email=data["email"],
            phone=data["phone"],
            role=data["role"],
            ward_id=data.get("ward_id"),
            dept_id=data.get("dept_id"),
            password_hash=get_password_hash(data["password"])
        )
        await user.insert()
        print(f"Created user: {data['email']} (Role: {data['role']})")
        
    print("Done seeding users.")
    await close_mongodb()

if __name__ == "__main__":
    asyncio.run(seed_users())
