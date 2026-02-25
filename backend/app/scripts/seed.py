"""
Seed script — populate MongoDB with initial departments and admin user.
Run: python -m app.scripts.seed
"""
import asyncio
from datetime import datetime

from app.mongodb.database import init_mongodb, close_mongodb
from app.mongodb.models.department import DepartmentMongo
from app.mongodb.models.user import UserMongo
from app.enums import UserRole
from app.services.auth_service import AuthService

DEPARTMENTS = [
    {"dept_id": "D01", "dept_name": "Roads & Bridges", "sla_days": 14, "handles": "pothole,road,bridge,footpath"},
    {"dept_id": "D02", "dept_name": "Buildings & Planning", "sla_days": 30, "handles": "construction,illegal,encroachment"},
    {"dept_id": "D03", "dept_name": "Water Supply", "sla_days": 5, "handles": "water,pipe,leak,pressure"},
    {"dept_id": "D04", "dept_name": "Sewage & Drainage", "sla_days": 3, "handles": "sewage,drain,blocked,manhole"},
    {"dept_id": "D05", "dept_name": "Solid Waste Management", "sla_days": 2, "handles": "garbage,waste,bin,dumping"},
    {"dept_id": "D06", "dept_name": "Street Lighting", "sla_days": 7, "handles": "light,lamp,dark,electric"},
    {"dept_id": "D07", "dept_name": "Parks & Greenery", "sla_days": 30, "handles": "park,tree,garden,playground"},
    {"dept_id": "D08", "dept_name": "Health & Sanitation", "sla_days": 5, "handles": "mosquito,stray,disease,dead animal"},
    {"dept_id": "D09", "dept_name": "Fire & Emergency", "sla_days": 1, "handles": "fire,accident,emergency,collapse"},
    {"dept_id": "D10", "dept_name": "Traffic & Transport", "sla_days": 1, "handles": "traffic,signal,bus,parking"},
    {"dept_id": "D11", "dept_name": "Revenue & Property", "sla_days": 21, "handles": "tax,property,document,certificate"},
    {"dept_id": "D12", "dept_name": "Social Welfare", "sla_days": 7, "handles": "pension,welfare,disability,ration"},
    {"dept_id": "D13", "dept_name": "Education", "sla_days": 14, "handles": "school,teacher,college,student"},
    {"dept_id": "D14", "dept_name": "Disaster Management", "sla_days": 1, "handles": "flood,cyclone,landslide,disaster"},
]

ADMIN_USER = {
    "name": "System Admin",
    "email": "admin@janvedha.ai",
    "phone": "0000000000",
    "password": "Admin@123",
    "role": UserRole.SUPER_ADMIN,
}


async def seed():
    await init_mongodb()
    print("Seeding departments...")
    for dept_data in DEPARTMENTS:
        existing = await DepartmentMongo.find_one(DepartmentMongo.dept_id == dept_data["dept_id"])
        if not existing:
            dept = DepartmentMongo(**dept_data)
            await dept.insert()
            print(f"  Created department: {dept_data['dept_id']} - {dept_data['dept_name']}")
        else:
            print(f"  Department {dept_data['dept_id']} already exists, skipping.")

    print("Seeding admin user...")
    existing_admin = await UserMongo.find_one(UserMongo.email == ADMIN_USER["email"])
    if not existing_admin:
        admin = UserMongo(
            name=ADMIN_USER["name"],
            email=ADMIN_USER["email"],
            phone=ADMIN_USER["phone"],
            password_hash=AuthService.get_password_hash(ADMIN_USER["password"]),
            role=ADMIN_USER["role"],
        )
        await admin.insert()
        print(f"  Created admin: {ADMIN_USER['email']}")
    else:
        print(f"  Admin user already exists, skipping.")

    await close_mongodb()
    print("Seeding complete!")


if __name__ == "__main__":
    asyncio.run(seed())
