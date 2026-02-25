"""
Main application entrypoint for JanVedha AI backend.

Startup sequence:
1. init_mongodb()         — connects Motor, initialises Beanie ODM
2. load_priority_model()  — loads ML model from MongoDB (or starts fresh)

Shutdown:
1. close_mongodb()        — closes Motor connection pool
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.mongodb.database import init_mongodb, close_mongodb


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle manager."""
    # ── Startup ──────────────────────────────────────────────────────────────
    await init_mongodb()

    # Load the ML priority model from MongoDB (if trained data exists)
    from app.services.ai.priority_agent import load_priority_model
    await load_priority_model()

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    await close_mongodb()


app = FastAPI(
    title="JanVedha AI API",
    version="2.0.0",
    description="AI-powered civic issue management platform for local governance.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api import public, auth, officer, webhooks

app.include_router(public.router, prefix="/api/public", tags=["public"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(officer.router, prefix="/api/officer", tags=["officer"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["webhooks"])


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT,
        "city": settings.CITY_NAME,
        "db": "mongodb",
    }
