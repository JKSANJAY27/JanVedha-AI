"""
MongoDB async connection manager using Motor + Beanie.

Usage (add to app startup):
    from app.mongodb.database import init_mongodb
    await init_mongodb()

Provides:
    get_motor_client()  — returns the singleton Motor client
    init_mongodb()      — initialises Beanie with all documents
    close_mongodb()     — shuts down the Motor connection
"""
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from typing import Optional

from app.core.config import settings

_motor_client: Optional[AsyncIOMotorClient] = None


def get_motor_client() -> AsyncIOMotorClient:
    """Return the singleton Motor client (call init_mongodb() first)."""
    if _motor_client is None:
        raise RuntimeError("MongoDB not initialised. Call init_mongodb() at startup.")
    return _motor_client


async def init_mongodb() -> None:
    """
    Initialise Motor + Beanie. Call once during application startup.

    Example (in main.py lifespan):
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            await init_mongodb()
            yield
            await close_mongodb()
    """
    global _motor_client

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
    )

    _motor_client = AsyncIOMotorClient(settings.MONGODB_URI)

    # Extract DB name from URI (e.g. "mongodb://localhost:27017/civicai" → "civicai")
    db_name = settings.MONGODB_URI.rsplit("/", 1)[-1].split("?")[0] or "civicai"
    database = _motor_client[db_name]

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
        ],
    )


async def close_mongodb() -> None:
    """Cleanly shut down the Motor connection pool."""
    global _motor_client
    if _motor_client is not None:
        _motor_client.close()
        _motor_client = None
