from celery import Celery
import asyncio
from app.core.config import settings
from app.services.sla_service import SLAService
from app.core.database import AsyncSessionLocal

celery_app = Celery(
    "civic_ai_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

celery_app.conf.beat_schedule = {
    "process-sla-breaches-every-5-minutes": {
        "task": "app.tasks.sla_tasks.run_sla_processor",
        "schedule": 300.0, # 5 minutes in seconds
    },
}
celery_app.conf.timezone = "UTC"

async def _async_run_sla_processor():
    async with AsyncSessionLocal() as db:
        await SLAService.process_sla_breaches(db)

@celery_app.task
def run_sla_processor():
    # Celery operates synchronously, we need to run our async service in a loop
    asyncio.run(_async_run_sla_processor())
