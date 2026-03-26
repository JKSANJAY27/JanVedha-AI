import asyncio
import httpx
from pymongo import MongoClient
import jwt
import json
from datetime import datetime, timedelta

async def main():
    client = MongoClient("mongodb+srv://harshithbalu99_db_user:LzVxH2pOV4hrDQkO@cluster0.bymv7qp.mongodb.net/?appName=Cluster0")
    db = client.get_database("civicai")
    user = db["users"].find_one({"role": "COMMISSIONER"})
    if not user:
        user = db["users"].find_one({"role": "SUPERVISOR"})

    payload = {"sub": str(user["_id"]), "role": user["role"], "exp": datetime.utcnow() + timedelta(days=1)}
    tk = jwt.encode(payload, "janvedha", algorithm="HS256")
    
    async with httpx.AsyncClient() as c:
        r2 = await c.post('http://127.0.0.1:8000/api/commissioner/digest/generate', json={}, headers={'Authorization': f'Bearer {tk}'})
        with open("error.json", "w") as f:
            f.write(r2.text)

if __name__ == '__main__':
    asyncio.run(main())
