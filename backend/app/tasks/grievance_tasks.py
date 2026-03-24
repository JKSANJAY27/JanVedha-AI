"""
Grievance Ingestion Background Tasks — JanVedha AI

Runs the grievance scraping pipeline on a schedule.
Wired into app startup via main.py.
"""
import asyncio
import logging

from app.core.config import settings

logger = logging.getLogger("grievance_tasks")


async def grievance_scrape_loop():
    """
    Background loop that runs grievance ingestion at the configured interval.
    Non-blocking — runs as an asyncio task alongside FastAPI.
    """
    interval_minutes = getattr(settings, "GRIEVANCE_SCRAPE_INTERVAL_MINUTES", 30)
    interval_seconds = interval_minutes * 60

    logger.info(
        "Grievance scrape loop started (interval=%d mins)",
        interval_minutes,
    )

    # Wait a bit after startup before first scrape
    await asyncio.sleep(30)

    while True:
        try:
            from app.services.grievance_ingestion_service import run_grievance_ingestion
            stats = await run_grievance_ingestion()
            logger.info(
                "Scheduled grievance scrape: scraped=%d, new=%d, ticketed=%d",
                stats.get("scraped", 0),
                stats.get("new_after_dedup", 0),
                stats.get("auto_ticketed", 0),
            )
        except Exception as e:
            logger.error("Scheduled grievance scrape failed: %s", e, exc_info=True)

        await asyncio.sleep(interval_seconds)
