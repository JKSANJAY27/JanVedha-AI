import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import AsyncSessionLocal
from app.models.department import Department
from app.models.user import User, UserRole
from app.services.auth_service import AuthService
from app.models.ticket import Ticket, TicketSource, TicketStatus
from datetime import datetime

async def seed_data():
    async with AsyncSessionLocal() as db:
        
        # 1. Departments
        depts = [
            Department(dept_id="D01", name="Sanitation & Solid Waste", description="Garbage, dumping", sla_days=3),
            Department(dept_id="D02", name="Roads & Bridges", description="Potholes, cracks", sla_days=14),
            Department(dept_id="D03", name="Water Supply", description="No water, contamination", sla_days=5),
            Department(dept_id="D04", name="Storm Water Drains", description="Flooding, blockages", sla_days=3),
            Department(dept_id="D05", name="Street Lights", description="Dark streets", sla_days=2),
            Department(dept_id="D06", name="Public Health", description="Disease, stray animals", sla_days=7),
            Department(dept_id="D07", name="Town Planning", description="Illegal construction", sla_days=30),
            Department(dept_id="D08", name="Parks & Playgrounds", description="Maintenance", sla_days=5),
            Department(dept_id="D09", name="Disaster Management", description="Emergencies", sla_days=1),
            Department(dept_id="D10", name="Revenue", description="Tax issues", sla_days=1),
            Department(dept_id="D11", name="Education", description="Corporation schools", sla_days=21),
            Department(dept_id="D12", name="Buildings", description="Public toilet maintenance", sla_days=7),
            Department(dept_id="D13", name="Bridges", description="Overpass issues", sla_days=14),
            Department(dept_id="D14", name="IT Cell", description="App bugs", sla_days=1),
        ]
        
        # Merge ensures we don't duplicate on re-runs
        for dept in depts:
            await db.merge(dept)

        # 2. Users mapped to Chennai Ward 12 (Demo Ward)
        hashed_pw = AuthService.get_password_hash("password123")
        
        users = [
            User(id=1, name="Commissioner Admin", email="comm@janvedha.online", phone="9999999901", role=UserRole.COMMISSIONER, password_hash=hashed_pw),
            User(id=2, name="Aarav (Ward 12 Officer)", email="ward12@janvedha.online", phone="9999999902", role=UserRole.WARD_OFFICER, password_hash=hashed_pw, ward_id=12),
            User(id=3, name="Priya (Zonal Officer)", email="zone1@janvedha.online", phone="9999999903", role=UserRole.ZONAL_OFFICER, password_hash=hashed_pw, zone_id=1),
            User(id=4, name="Ramesh (Roads Dept Head)", email="roads@janvedha.online", phone="9999999904", role=UserRole.DEPT_HEAD, password_hash=hashed_pw, dept_id="D02")
        ]
        
        for user in users:
            await db.merge(user)

        # Commit foundation logic
        await db.commit()
        print("Successfully seeded fundamental Departments and Users.")

if __name__ == "__main__":
    asyncio.run(seed_data())
