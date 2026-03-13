import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.mongodb.database import init_db
from app.services.intelligence_service import IntelligenceService
from app.mongodb.models.user import UserMongo
from app.mongodb.models.ticket import TicketMongo

async def main():
    await init_db()
    
    print("----- Briefing -----")
    briefing = await IntelligenceService.get_ward_briefing(1)
    print(briefing)

    print("\n----- Root Causes -----")
    causes = await IntelligenceService.get_root_cause_radar(1)
    print(causes)

    print("\n----- Predictions -----")
    predictions = await IntelligenceService.get_predictive_alerts(1)
    print(predictions)

if __name__ == "__main__":
    asyncio.run(main())
