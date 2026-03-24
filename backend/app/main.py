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

#    await load_priority_model()


    from app.services.telegram_bot import get_bot_application
    bot_app = get_bot_application()
    if bot_app:
        try:
            print("Telegram bot initializing...")
            await bot_app.initialize()
            await bot_app.start()
            await bot_app.updater.start_polling(drop_pending_updates=True)
            print("Telegram bot successfully started.")
        except Exception as e:
            print(f"Failed to start telegram bot: {e}")

#    # Start Misinformation Detector background task (Feature 3)
#    try:
#        import asyncio
#        from app.services.misinformation_detector import start_misinformation_detector
#        asyncio.create_task(start_misinformation_detector())
#        print("Misinformation detector started.")
#    except Exception as e:
#        print(f"Failed to start misinformation detector: {e}")

    # Start background scheduler (weekly digest + daily pattern detection)
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger
        from app.api.commissioner import generate_weekly_digest
        from app.utils.pattern_detector import run_all_detections

        scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")
        # Weekly digest every Monday at 06:00 IST
        scheduler.add_job(generate_weekly_digest, CronTrigger(day_of_week="mon", hour=6, minute=0),
                          id="weekly_digest", replace_existing=True)
        # Daily intelligence detection at 07:00 IST
        scheduler.add_job(run_all_detections, CronTrigger(hour=7, minute=0),
                          id="daily_detection", replace_existing=True)
        scheduler.start()
        app.state.scheduler = scheduler
        print("Scheduler started: weekly digest (Mon 06:00 IST) + daily detection (07:00 IST)")
    except Exception as e:
        print(f"Scheduler failed to start (non-fatal): {e}")

    # Start grievance ingestion background task
    try:
        import asyncio
        from app.tasks.grievance_tasks import grievance_scrape_loop
        asyncio.create_task(grievance_scrape_loop())
        print("Grievance ingestion loop started (interval=%d mins)" % settings.GRIEVANCE_SCRAPE_INTERVAL_MINUTES)
    except Exception as e:
        print(f"Grievance ingestion loop failed to start (non-fatal): {e}")

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    if hasattr(app.state, "scheduler"):
        try:
            app.state.scheduler.shutdown(wait=False)
        except Exception:
            pass

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

from app.api import cctv, public, auth, officer, webhooks, chat, calendar, councillor, commissioner, documents, social_intel, analytics, public_trust, opportunity, proposals, casework, communications, media_rti, scheme_advisor, voice_agent, blockchain, grievances

app.include_router(public.router, prefix="/api/public", tags=["public"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(officer.router, prefix="/api/officer", tags=["officer"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["webhooks"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(calendar.router, prefix="/api/calendar", tags=["calendar"])
app.include_router(councillor.router, prefix="/api/councillor", tags=["councillor"])
app.include_router(commissioner.router, prefix="/api/commissioner", tags=["commissioner"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(social_intel.router, prefix="/api/social-intel", tags=["social-intel"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(public_trust.router, prefix="/api/v1/trust", tags=["public-trust"])
app.include_router(opportunity.router, prefix="/api/opportunity", tags=["opportunity"])
app.include_router(proposals.router, prefix="/api/proposals", tags=["proposals"])
app.include_router(casework.router, prefix="/api/casework", tags=["casework"])
app.include_router(communications.router, prefix="/api/communications", tags=["communications"])
app.include_router(media_rti.router, prefix="/api/media-rti", tags=["media-rti"])
app.include_router(cctv.router, prefix="/api/cctv", tags=["cctv"])
app.include_router(scheme_advisor.router, prefix="/api/scheme-advisor", tags=["scheme-advisor"])
app.include_router(voice_agent.router, prefix="/api/voice-agent", tags=["voice-agent"])
app.include_router(blockchain.router, prefix="/api/blockchain", tags=["blockchain"])
app.include_router(grievances.router, prefix="/api/grievances", tags=["grievances"])



@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT,
        "city": settings.CITY_NAME,
        "db": "mongodb",
    }
