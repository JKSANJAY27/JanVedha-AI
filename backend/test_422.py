import asyncio
import httpx
from pymongo import MongoClient
import os

async def main():
    # find user
    client = MongoClient("mongodb://localhost:27017")
    db = client["civicai"]
    user = db["users"].find_one({"role": "COMMISSIONER"})
    if not user:
        print("no user")
        return

    # login
    email = user["email"]
    # use a hardcoded login or a JWT token generation logic.
    # since we have DB, we can just grab an existing valid token or issue one.
    
    # Or instead of messing with JWT, we can just do a direct POST to http://localhost:8000/api/commissioner/digest/generate
    # Wait, auth is required. Let's just create a token.
    from jose import jwt
    from datetime import datetime, timedelta
    
    SECRET_KEY = "dummy_secret_key_from_env" # Wait, need accurate secret key.
    
    # Actually, we can just read the `.env` to get SECRET_KEY
    import sys
    sys.path.append(r"C:\Users\harsh\Documents\JanVedha\JanVedha-AI\backend")
    from app.core.config import settings
    from app.core.security import create_access_token
    token = create_access_token(user["_id"], user["role"])
    
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    async with httpx.AsyncClient() as c:
        resp = await c.post("http://127.0.0.1:8000/api/commissioner/digest/generate", json={}, headers=headers)
        print("STATUS:", resp.status_code)
        print("BODY:", resp.text)

if __name__ == "__main__":
    asyncio.run(main())
