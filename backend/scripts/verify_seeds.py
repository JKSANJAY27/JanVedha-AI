import asyncio
import os
import sys
import hashlib
import bcrypt

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.config import settings
from motor.motor_asyncio import AsyncIOMotorClient

async def check_users():
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db_name = settings.MONGODB_URI.rsplit("/", 1)[-1].split("?")[0] or "civicai"
    db = client[db_name]
    users_col = db["users"]
    
    users_to_check = [
        ("admin@janvedha.ai", "Admin@123"),
        ("admin@janvedha.com", "password123"),
        ("pgo@janvedha.com", "password123")
    ]
    
    for email, pwd in users_to_check:
        user = await users_col.find_one({"email": email})
        if not user:
            print(f"User {email} NOT FOUND")
            continue
            
        hashed = user.get("password_hash")
        if not hashed:
            print(f"User {email} has NO password_hash")
            continue
            
        digest = hashlib.sha256(pwd.encode("utf-8")).hexdigest().encode("utf-8")
        is_ok = bcrypt.checkpw(digest, hashed.encode("utf-8"))
        print(f"User: {email}, Password: {pwd}, Match: {is_ok}")
        
    client.close()

if __name__ == "__main__":
    asyncio.run(check_users())
