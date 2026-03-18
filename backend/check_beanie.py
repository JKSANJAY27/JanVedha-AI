import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.core.config import settings
from app.mongodb.models import *

async def test_init():
    uri = settings.MONGODB_URI
    db_name = uri.rsplit("/", 1)[-1].split("?")[0] or "civicai"
    client = AsyncIOMotorClient(uri)
    database = client[db_name]

    print(f"Connecting to {db_name}...")
    try:
        from app.mongodb.models import (
            UserMongo,
            TicketMongo,
            DepartmentMongo,
            AnnouncementMongo,
            AuditLogMongo,
            WardDeptOfficerMongo,
            WardPredictionMongo,
            IssueMemoryMongo,
            PriorityModelMongo,
            ScheduledEventMongo,
            SocialPostMongo,
            WardBenchmarkMongo,
            NotificationMongo,
            MisinformationFlagMongo,
            TrustScoreMongo,
            WardConfigMongo,
        )

        await init_beanie(
            database=database,
            document_models=[
                UserMongo,
                TicketMongo,
                DepartmentMongo,
                AnnouncementMongo,
                AuditLogMongo,
                WardDeptOfficerMongo,
                WardPredictionMongo,
                IssueMemoryMongo,
                PriorityModelMongo,
                ScheduledEventMongo,
                SocialPostMongo,
                WardBenchmarkMongo,
                NotificationMongo,
                MisinformationFlagMongo,
                TrustScoreMongo,
                WardConfigMongo,
            ],
        )
        print("Success!")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(test_init())
