import asyncio
import os
import sys
from datetime import datetime, timedelta, date

# Add the backend directory to sys.path since this script is in backend/scripts/
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_dir)

from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from app.mongodb.models.user import UserMongo
from app.mongodb.models.ticket import TicketMongo
from app.enums import UserRole, PriorityLabel, TicketStatus
from app.services.ai.smart_assigner import generate_smart_schedule

async def init_db():
    client = AsyncIOMotorClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017"))
    await init_beanie(
        database=client.janvedha,
        document_models=[UserMongo, TicketMongo]
    )

async def check_smart_schedule():
    await init_db()
    print("Database initialized.")

    ward_id = 999
    dept_id = "TEST_DEPT_SMART"

    # Cleanup any previous test data
    await UserMongo.find(UserMongo.ward_id == ward_id, UserMongo.dept_id == dept_id).delete()
    await TicketMongo.find(TicketMongo.ward_id == ward_id, TicketMongo.dept_id == dept_id).delete()

    # 1. Create a Technician
    tech = UserMongo(
        name="Test Tech 1",
        email="testtech1@example.com",
        phone="8888888888",
        role=UserRole.FIELD_STAFF,
        ward_id=ward_id,
        dept_id=dept_id
    )
    await tech.insert()
    print(f"Created technician {tech.id}")

    # 2. Create a LOW priority ticket SCHEDULED for tomorrow
    tomorrow = (datetime.utcnow() + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    # Ensure tomorrow is a workday (skip sunday)
    if tomorrow.weekday() == 6:
        tomorrow += timedelta(days=1)
        
    day_after = tomorrow + timedelta(days=1)
    if day_after.weekday() == 6:
        day_after += timedelta(days=1)

    low_ticket = TicketMongo(
        ticket_code="TCK-LOW-001",
        description="Low priority issue",
        dept_id=dept_id,
        ward_id=ward_id,
        priority_label=PriorityLabel.LOW,
        priority_score=10.0,
        status=TicketStatus.SCHEDULED,
        technician_id=str(tech.id),
        scheduled_date=tomorrow,
        sla_deadline=datetime.utcnow() + timedelta(days=30)
    )
    await low_ticket.insert()
    print(f"Created LOW priority scheduled ticket {low_ticket.id} on {tomorrow.date()}")

    # 3. Create a CRITICAL priority ticket that needs scheduling
    crit_ticket = TicketMongo(
        ticket_code="TCK-CRIT-002",
        description="Critical priority issue",
        dept_id=dept_id,
        ward_id=ward_id,
        priority_label=PriorityLabel.CRITICAL,
        priority_score=95.0,
        status=TicketStatus.OPEN,
        sla_deadline=datetime.utcnow() + timedelta(days=5)
    )
    await crit_ticket.insert()
    print(f"Created CRITICAL priority open ticket {crit_ticket.id}")

    # 4. Generate Smart Schedule
    print("\nGenerating Smart Schedule for CRITICAL ticket...")
    res = await generate_smart_schedule(str(crit_ticket.id))
    print(res)

    assert res is not None, "Algorithm returned None"
    assert res['suggested_date'].date() == tomorrow.date(), "Critical ticket should take the slot for tomorrow."
    assert len(res['postponed_tickets']) == 1, "There should be 1 postponed ticket."
    
    postponed = res['postponed_tickets'][0]
    assert postponed['ticket_id'] == str(low_ticket.id), "The postponed ticket should be the LOW priority ticket."
    assert postponed['new_date'].date() > tomorrow.date(), "The LOW ticket should be moved to a future date."

    print("\n✅ Verification Successful: Algorithm preempts low priority ticket to schedule critical ticket.")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(backend_dir, ".env"))
    asyncio.run(check_smart_schedule())
