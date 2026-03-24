from fastapi import FastAPI
from asgi_lifespan import LifespanManager
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

uri = "mongodb://jksanjay2006_db_user:janvedha@ac-kwhh2i5-shard-00-00.evfoip0.mongodb.net:27017,ac-kwhh2i5-shard-00-01.evfoip0.mongodb.net:27017,ac-kwhh2i5-shard-00-02.evfoip0.mongodb.net:27017/?ssl=true&replicaSet=atlas-qr0pwx-shard-0&authSource=admin&appName=Cluster0"

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    print("Starting up...")
    try:
        client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
        await client.admin.command('ping')
        print("Connected inside FastAPI")
    except Exception as e:
        print("Failed inside FastAPI:", type(e), e)

@app.get("/")
def read_root():
    return {"Hello": "World"}
