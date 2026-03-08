import asyncio
import os
import sys
import hashlib
import bcrypt

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.mongodb.database import init_mongodb, close_mongodb
from app.mongodb.models import UserMongo
from app.enums import UserRole

def get_password_hash(password: str) -> str:
    # Match the AuthService._hash_password logic exactly
    digest = hashlib.sha256(password.encode("utf-8")).hexdigest().encode("utf-8")
    return bcrypt.hashpw(digest, bcrypt.gensalt()).decode("utf-8")

async def reset_passwords():
    print("Connecting to MongoDB...")
    await init_mongodb()
    
    users_to_reset = [
        "admin@janvedha.ai",
        "admin@janvedha.com",
        "pgo@janvedha.com",
        "dept@janvedha.com",
        "tech@janvedha.com",
        "councillor@janvedha.com"
    ]

    for email in users_to_reset:
        user = await UserMongo.find_one(UserMongo.email == email)
        if user:
            # Special case for admin@janvedha.ai
            password = "Admin@123" if email == "admin@janvedha.ai" else "password123"
            
            user.password_hash = get_password_hash(password)
            await user.save()
            print(f"Updated password for: {email}")
        else:
            print(f"User not found: {email}")
            
    print("Done resetting passwords.")
    await close_mongodb()

if __name__ == "__main__":
    asyncio.run(reset_passwords())
