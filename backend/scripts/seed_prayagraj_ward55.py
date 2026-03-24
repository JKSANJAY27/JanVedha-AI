"""
Prayagraj Ward 55 (Teliarganj) Seed Script — JanVedha AI
======================================================
Seeds everything needed to test Prayagraj Ward 55 (MNNIT / Teliarganj):

1. Ward 1055 departments (D01–D14 with ward_id=1055)
2. Users:
   - 1 Supervisor
   - 1 Councillor
   - 14 Junior Engineers
3. Sample tickets for Prayagraj (MNNIT / Teliarganj area)
"""
import asyncio
import os
import sys
import hashlib
import bcrypt
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

def hash_password(password: str) -> str:
    digest = hashlib.sha256(password.encode("utf-8")).hexdigest().encode("utf-8")
    return bcrypt.hashpw(digest, bcrypt.gensalt()).decode("utf-8")

DEPARTMENTS = [
    {"dept_id": "D01", "dept_name": "Roads & Bridges",        "handles": "pothole,road,bridge,footpath", "sla_days": 7},
    {"dept_id": "D02", "dept_name": "Buildings & Planning",   "handles": "construction,illegal,encroachment,building", "sla_days": 14},
    {"dept_id": "D03", "dept_name": "Water Supply",           "handles": "water,supply,pipe,leak,pressure", "sla_days": 3},
    {"dept_id": "D04", "dept_name": "Sewage & Drainage",      "handles": "sewage,drain,blocked,overflow,manhole", "sla_days": 3},
    {"dept_id": "D05", "dept_name": "Solid Waste Management", "handles": "garbage,waste,bin,collection,dumping", "sla_days": 2},
    {"dept_id": "D06", "dept_name": "Street Lighting",        "handles": "light,lamp,dark,street light,bulb", "sla_days": 5},
    {"dept_id": "D07", "dept_name": "Parks & Greenery",       "handles": "park,tree,garden,grass,playground", "sla_days": 10},
    {"dept_id": "D08", "dept_name": "Health & Sanitation",    "handles": "mosquito,dengue,fever,epidemic,stray,dog", "sla_days": 2},
    {"dept_id": "D09", "dept_name": "Fire & Emergency",       "handles": "fire,accident,emergency,explosion,hazard", "sla_days": 1},
    {"dept_id": "D10", "dept_name": "Traffic & Transport",    "handles": "traffic,signal,bus,road block,parking", "sla_days": 5},
    {"dept_id": "D11", "dept_name": "Revenue & Property",     "handles": "tax,property,document,certificate", "sla_days": 14},
    {"dept_id": "D12", "dept_name": "Social Welfare",         "handles": "pension,welfare,disability,ration,subsidy", "sla_days": 14},
    {"dept_id": "D13", "dept_name": "Education",              "handles": "school,teacher,education,college,student", "sla_days": 14},
    {"dept_id": "D14", "dept_name": "Disaster Management",    "handles": "flood,cyclone,landslide,tsunami,disaster", "sla_days": 1},
]

WARD_ID = 1055
WARD_NAME = "Ward 55 - Teliarganj (Prayagraj)"
PASSWORD = "password123"

SUPERVISOR = {
    "name": f"Ward 55 Supervisor Prayagraj",
    "email": f"supervisor.w{WARD_ID}@janvedha.com",
    "phone": f"8888{WARD_ID:04d}1",
    "role": "SUPERVISOR",
    "ward_id": WARD_ID,
}

COUNCILLOR = {
    "name": f"Ward 55 Councillor Prayagraj",
    "email": f"councillor.w{WARD_ID}@janvedha.com",
    "phone": f"5555{WARD_ID:04d}1",
    "role": "COUNCILLOR",
    "ward_id": WARD_ID,
}

DEPT_SLUGS = {
    "D01": "roads", "D02": "buildings", "D03": "water", "D04": "sewage",
    "D05": "waste", "D06": "lights", "D07": "parks", "D08": "health",
    "D09": "fire", "D10": "traffic", "D11": "revenue", "D12": "welfare",
    "D13": "education", "D14": "disaster",
}

JUNIOR_ENGINEERS = [
    {
        "name": f"JE {dept['dept_name']} W55 PRYJ",
        "email": f"je.{DEPT_SLUGS[dept['dept_id']]}.w{WARD_ID}@janvedha.com",
        "phone": f"7777{WARD_ID:04d}{int(dept['dept_id'][1:]):02d}0",
        "role": "JUNIOR_ENGINEER",
        "ward_id": WARD_ID,
        "dept_id": dept["dept_id"],
    }
    for dept in DEPARTMENTS
]

async def upsert_user(col, data: dict, pw: str = PASSWORD):
    existing = await col.find_one({"email": data["email"]})
    doc = {**data, "password_hash": hash_password(pw), "is_active": True, "created_at": datetime.utcnow()}
    if existing:
        await col.update_one({"email": data["email"]}, {"$set": doc})
        print(f"  [U] Updated  {data['role']:20s} {data['email']}")
    else:
        await col.insert_one(doc)
        print(f"  [+] Created  {data['role']:20s} {data['email']}")

async def upsert_department(col, dept: dict, ward_id=None):
    query = {"dept_id": dept["dept_id"], "ward_id": ward_id}
    doc = {**dept, "ward_id": ward_id, "is_external": False}
    existing = await col.find_one(query)
    if existing:
        await col.update_one(query, {"$set": doc})
        scope = f"Ward {ward_id}" if ward_id else "Global"
        print(f"  [U] Updated  dept {dept['dept_id']} ({scope})")
    else:
        await col.insert_one(doc)
        scope = f"Ward {ward_id}" if ward_id else "Global"
        print(f"  [+] Created  dept {dept['dept_id']} - {dept['dept_name']} ({scope})")

async def seed_sample_tickets(db, users_col):
    tickets_col = db["tickets"]

    je_roads = await users_col.find_one({"email": f"je.roads.w{WARD_ID}@janvedha.com"})
    je_water = await users_col.find_one({"email": f"je.water.w{WARD_ID}@janvedha.com"})
    je_waste = await users_col.find_one({"email": f"je.waste.w{WARD_ID}@janvedha.com"})

    import random, string

    def ticket_code():
        return "JV-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

    now = datetime.utcnow()

    SAMPLE_TICKETS = [
        {
            "ticket_code": ticket_code(),
            "source": "WEB_PORTAL",
            "description": "Deep potholes on the main road outside MNNIT Allahabad gate. It is causing severe traffic.",
            "dept_id": "D01",
            "issue_category": "general_complaint",
            "ward_id": WARD_ID,
            "location_text": f"MNNIT Main Gate, Teliarganj, Prayagraj",
            "location": {"lat": 25.4930, "lng": 81.8687, "address": f"MNNIT Main Gate, Teliarganj, Prayagraj, UP"},
            "reporter_phone": "9998887771",
            "reporter_name": "Rohan Tiwari",
            "reporter_user_id": None,
            "consent_given": True,
            "consent_timestamp": now,
            "language_detected": "en",
            "ai_confidence": 0.89,
            "ai_routing_reason": "Road repair and pothole fixing — routed to Roads & Bridges",
            "ai_suggestions": ["Patch road with bitumen", "Place barricades warning drivers"],
            "priority_score": 75.0,
            "priority_label": "HIGH",
            "priority_source": "rules",
            "status": "OPEN",
            "report_count": 2,
            "requires_human_review": False,
            "is_validated": False,
            "social_media_mentions": 0,
            "assigned_officer_id": str(je_roads["_id"]) if je_roads else None,
            "assigned_at": now,
            "technician_id": None,
            "sla_deadline": now + timedelta(days=7),
            "created_at": now - timedelta(hours=24),
            "status_timeline": [{"status": "OPEN", "timestamp": (now - timedelta(hours=24)).isoformat(), "actor_role": "PUBLIC_USER", "note": "Complaint submitted"}],
            "remarks": [],
            "blockchain_hash": None,
        },
        {
            "ticket_code": ticket_code(),
            "source": "WEB_PORTAL",
            "description": "Water leaking from main supply pipe near Teliarganj market.",
            "dept_id": "D03",
            "issue_category": "general_complaint",
            "ward_id": WARD_ID,
            "location_text": f"Teliarganj Market, Prayagraj",
            "location": {"lat": 25.4850, "lng": 81.8650, "address": f"Teliarganj Market, Prayagraj, UP"},
            "reporter_phone": "9998887772",
            "reporter_name": "Neha Sharma",
            "reporter_user_id": None,
            "consent_given": True,
            "consent_timestamp": now,
            "language_detected": "en",
            "ai_confidence": 0.92,
            "ai_routing_reason": "Pipe leak causing water waste — routed to Water Supply dept",
            "ai_suggestions": ["Locate burst pipe", "Shut off main valve", "Replace broken section"],
            "priority_score": 82.0,
            "priority_label": "CRITICAL",
            "priority_source": "rules",
            "status": "ASSIGNED",
            "report_count": 5,
            "requires_human_review": False,
            "is_validated": True,
            "social_media_mentions": 1,
            "assigned_officer_id": str(je_water["_id"]) if je_water else None,
            "assigned_at": now - timedelta(hours=2),
            "technician_id": None,
            "sla_deadline": now + timedelta(days=3),
            "created_at": now - timedelta(hours=10),
            "status_timeline": [
                {"status": "OPEN", "timestamp": (now - timedelta(hours=10)).isoformat(), "actor_role": "PUBLIC_USER", "note": "Complaint submitted"},
                {"status": "ASSIGNED", "timestamp": (now - timedelta(hours=2)).isoformat(), "actor_role": "SUPERVISOR", "note": "Assigned to Water Supply JE"},
            ],
            "remarks": [],
            "blockchain_hash": None,
        },
        {
            "ticket_code": ticket_code(),
            "source": "WEB_PORTAL",
            "description": "Garbage dump lying uncleaned for 4 days near student hostels.",
            "dept_id": "D05",
            "issue_category": "general_complaint",
            "ward_id": WARD_ID,
            "location_text": f"Hostel Area, MNNIT, Teliarganj, Prayagraj",
            "location": {"lat": 25.4940, "lng": 81.8690, "address": f"Hostels, MNNIT Campus, Teliarganj, Prayagraj"},
            "reporter_phone": "9998887773",
            "reporter_name": "Amit Kumar",
            "reporter_user_id": None,
            "consent_given": True,
            "consent_timestamp": now,
            "language_detected": "en",
            "ai_confidence": 0.88,
            "ai_routing_reason": "Solid waste uncollected — routed to SWM",
            "ai_suggestions": ["Deploy garbage truck", "Install larger bins"],
            "priority_score": 60.0,
            "priority_label": "HIGH",
            "priority_source": "rules",
            "status": "OPEN",
            "report_count": 3,
            "requires_human_review": False,
            "is_validated": False,
            "social_media_mentions": 0,
            "assigned_officer_id": None,
            "technician_id": None,
            "sla_deadline": now + timedelta(days=2),
            "created_at": now - timedelta(days=1),
            "status_timeline": [{"status": "OPEN", "timestamp": (now - timedelta(days=1)).isoformat(), "actor_role": "PUBLIC_USER", "note": "Complaint submitted"}],
            "remarks": [],
            "blockchain_hash": None,
        },
        {
            "ticket_code": ticket_code(),
            "source": "WEB_PORTAL",
            "description": "Streetlights on the route from Teliarganj square to Phaphamau bridge are completely off.",
            "dept_id": "D06",
            "issue_category": "general_complaint",
            "ward_id": WARD_ID,
            "location_text": f"Teliarganj Square, Prayagraj",
            "location": {"lat": 25.4900, "lng": 81.8655, "address": f"Teliarganj Square, Prayagraj, UP"},
            "reporter_phone": "9998887774",
            "reporter_name": "Sita Yadav",
            "reporter_user_id": None,
            "consent_given": True,
            "consent_timestamp": now,
            "language_detected": "en",
            "ai_confidence": 0.90,
            "ai_routing_reason": "Street lighting issue — routed to Street Lights dept",
            "ai_suggestions": ["Check main fuse", "Replace faulty bulbs"],
            "priority_score": 55.0,
            "priority_label": "MEDIUM",
            "priority_source": "rules",
            "status": "OPEN",
            "report_count": 1,
            "requires_human_review": False,
            "is_validated": False,
            "social_media_mentions": 0,
            "assigned_officer_id": None,
            "technician_id": None,
            "sla_deadline": now + timedelta(days=5),
            "created_at": now - timedelta(hours=5),
            "status_timeline": [{"status": "OPEN", "timestamp": (now - timedelta(hours=5)).isoformat(), "actor_role": "PUBLIC_USER", "note": "Complaint submitted"}],
            "remarks": [],
            "blockchain_hash": None,
        },
        {
            "ticket_code": ticket_code(),
            "source": "WEB_PORTAL",
            "description": "Sewage water overflowing into the streets in low-lying area near Shivkuti.",
            "dept_id": "D04",
            "issue_category": "general_complaint",
            "ward_id": WARD_ID,
            "location_text": f"Shivkuti, Teliarganj, Prayagraj",
            "location": {"lat": 25.4960, "lng": 81.8720, "address": f"Shivkuti, Near Teliarganj, Prayagraj, UP"},
            "reporter_phone": "9998887775",
            "reporter_name": "Ramesh Mishra",
            "reporter_user_id": None,
            "consent_given": True,
            "consent_timestamp": now,
            "language_detected": "en",
            "ai_confidence": 0.93,
            "ai_routing_reason": "Drainage overflow — routed to Sewage & Drainage",
            "ai_suggestions": ["Send sucker machine", "Clear blockage"],
            "priority_score": 85.0,
            "priority_label": "CRITICAL",
            "priority_source": "rules",
            "status": "OPEN",
            "report_count": 6,
            "requires_human_review": False,
            "is_validated": True,
            "social_media_mentions": 2,
            "assigned_officer_id": None,
            "technician_id": None,
            "sla_deadline": now + timedelta(days=3),
            "created_at": now - timedelta(hours=6),
            "status_timeline": [{"status": "OPEN", "timestamp": (now - timedelta(hours=6)).isoformat(), "actor_role": "PUBLIC_USER", "note": "Complaint submitted"}],
            "remarks": [],
            "blockchain_hash": None,
        }
    ]

    for ticket in SAMPLE_TICKETS:
        existing = await tickets_col.find_one({"description": ticket["description"]})
        if existing:
            print(f"  [S] Skip ticket: {ticket['dept_id']} - {ticket['description'][:50]}...")
        else:
            await tickets_col.insert_one(ticket)
            print(f"  [+] Ticket created: {ticket['ticket_code']} - {ticket['dept_id']} [{ticket['priority_label']}]")

async def main():
    print("=" * 60)
    print(f"  JanVedha AI — {WARD_NAME} Complete Seed")
    print("=" * 60)

    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db_name = settings.MONGODB_URI.rsplit("/", 1)[-1].split("?")[0] or "civicai"
    db = client[db_name]

    users_col = db["users"]
    depts_col = db["departments"]

    # 1. Ward-scoped departments
    print(f"\n[1/3] Seeding {WARD_NAME} departments (D01–D14)...")
    for dept in DEPARTMENTS:
        await upsert_department(depts_col, dept, ward_id=WARD_ID)

    # 2. Supervisor + Councillor + JEs
    print(f"\n[2/3] Seeding Supervisor, Councillor, & 14 JEs for {WARD_NAME}...")
    await upsert_user(users_col, SUPERVISOR)
    await upsert_user(users_col, COUNCILLOR)
    for je in JUNIOR_ENGINEERS:
        await upsert_user(users_col, je)

    # 3. Sample tickets
    print(f"\n[3/3] Seeding 5 sample tickets for {WARD_NAME}...")
    await seed_sample_tickets(db, users_col)

    print("\n" + "=" * 60)
    print("[DONE] Seed complete for Prayagraj Teliarganj Ward!")
    client.close()

if __name__ == "__main__":
    asyncio.run(main())
