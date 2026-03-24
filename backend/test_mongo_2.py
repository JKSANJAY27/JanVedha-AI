import asyncio
import certifi
import sys
from motor.motor_asyncio import AsyncIOMotorClient

uri = "mongodb://jksanjay2006_db_user:janvedha@ac-kwhh2i5-shard-00-00.evfoip0.mongodb.net:27017,ac-kwhh2i5-shard-00-01.evfoip0.mongodb.net:27017,ac-kwhh2i5-shard-00-02.evfoip0.mongodb.net:27017/?ssl=true&replicaSet=atlas-qr0pwx-shard-0&authSource=admin&appName=Cluster0"

async def test_conn():
    try:
        client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
        await client.admin.command('ping')
        print("Connected without certifi")
    except Exception as e:
        print("Failed without certifi:", type(e), e)

asyncio.run(test_conn())
