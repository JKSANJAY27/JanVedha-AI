"""
Complete Ward 1 Seed Script — JanVedha AI
==========================================
Seeds everything needed to fully test the Ward 1 lifecycle:

1. Global departments (D01–D14) — fallback when no ward-scoped dept exists
2. Ward 1 departments (D01–D14 with ward_id=1)
3. Users:
   - 1 Supervisor (Ward 1)
   - 1 Councillor (Ward 1)
   - 14 Junior Engineers (one per department, Ward 1)
   - 28 Field Technicians (2 per department, Ward 1)
4. Sample tickets (Ward 1, various depts and priorities)

All passwords: password123
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


# ── Department catalogue (must match classifier_agent.py) ─────────────────────
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

WARD_ID = 1
WARD_NAME = "Kathivakkam"
PASSWORD = "password123"

# ── Users to seed ──────────────────────────────────────────────────────────────

SUPERVISOR = {
    "name": f"Ward {WARD_ID} Supervisor",
    "email": f"supervisor.w{WARD_ID}@janvedha.com",
    "phone": f"8888{WARD_ID:02d}0001",
    "role": "SUPERVISOR",
    "ward_id": WARD_ID,
}

COUNCILLOR = {
    "name": f"Ward {WARD_ID} Councillor",
    "email": f"councillor.w{WARD_ID}@janvedha.com",
    "phone": f"5555{WARD_ID:02d}0001",
    "role": "COUNCILLOR",
    "ward_id": WARD_ID,
}

# Dept slug for email-friendly names
DEPT_SLUGS = {
    "D01": "roads", "D02": "buildings", "D03": "water", "D04": "sewage",
    "D05": "waste", "D06": "lights", "D07": "parks", "D08": "health",
    "D09": "fire", "D10": "traffic", "D11": "revenue", "D12": "welfare",
    "D13": "education", "D14": "disaster",
}

JUNIOR_ENGINEERS = [
    {
        "name": f"JE {dept['dept_name']} Ward {WARD_ID}",
        "email": f"je.{DEPT_SLUGS[dept['dept_id']]}.w{WARD_ID}@janvedha.com",
        "phone": f"7777{WARD_ID:02d}{int(dept['dept_id'][1:]):02d}0",
        "role": "JUNIOR_ENGINEER",
        "ward_id": WARD_ID,
        "dept_id": dept["dept_id"],
    }
    for dept in DEPARTMENTS
]

FIELD_STAFF = []
for dept in DEPARTMENTS:
    slug = DEPT_SLUGS[dept["dept_id"]]
    for i in range(1, 3):  # 2 technicians per dept
        FIELD_STAFF.append({
            "name": f"Tech {dept['dept_name']} {i} Ward {WARD_ID}",
            "email": f"tech.{slug}{i}.w{WARD_ID}@janvedha.com",
            "phone": f"6666{WARD_ID:02d}{int(dept['dept_id'][1:]):02d}{i}",
            "role": "FIELD_STAFF",
            "ward_id": WARD_ID,
            "dept_id": dept["dept_id"],
        })


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
    """Seed 6 sample tickets for Ward 1 with realistic data."""
    tickets_col = db["tickets"]

    # Get supervisor id for assignment
    supervisor = await users_col.find_one({"email": SUPERVISOR["email"]})
    sup_id = str(supervisor["_id"]) if supervisor else None

    # Get a JE for roads
    je_roads = await users_col.find_one({"email": f"je.roads.w{WARD_ID}@janvedha.com"})
    je_water = await users_col.find_one({"email": f"je.water.w{WARD_ID}@janvedha.com"})
    je_waste = await users_col.find_one({"email": f"je.waste.w{WARD_ID}@janvedha.com"})

    # Get technicians
    tech_roads = await users_col.find_one({"email": f"tech.roads1.w{WARD_ID}@janvedha.com"})
    tech_water = await users_col.find_one({"email": f"tech.water1.w{WARD_ID}@janvedha.com"})

    import random, string

    def ticket_code():
        return "JV-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

    now = datetime.utcnow()

    SAMPLE_TICKETS = [
        {
            "ticket_code": ticket_code(),
            "source": "WEB_PORTAL",
            "description": "Large pothole on Lattice Bridge Road near Kathivakkam junction. Water logging happening during rain.",
            "dept_id": "D01",
            "issue_category": "general_complaint",
            "ward_id": WARD_ID,
            "location_text": f"{WARD_NAME}, Chennai",
            "location": {"lat": 13.2136, "lng": 80.3254, "address": f"Lattice Bridge Road, {WARD_NAME}, Chennai"},
            "reporter_phone": "9876543210",
            "reporter_name": "Ravi Kumar",
            "reporter_user_id": None,
            "consent_given": True,
            "consent_timestamp": now,
            "language_detected": "en",
            "ai_confidence": 0.85,
            "ai_routing_reason": "Road damage with water logging — routed to Roads & Bridges",
            "ai_suggestions": ["Fill with bituminous concrete", "Improve drainage", "Add warning sign"],
            "priority_score": 72.0,
            "priority_label": "HIGH",
            "priority_source": "rules",
            "status": "OPEN",
            "report_count": 1,
            "requires_human_review": False,
            "is_validated": False,
            "social_media_mentions": 0,
            "assigned_officer_id": str(je_roads["_id"]) if je_roads else None,
            "assigned_at": now,
            "technician_id": str(tech_roads["_id"]) if tech_roads else None,
            "sla_deadline": now + timedelta(days=7),
            "created_at": now - timedelta(hours=5),
            "status_timeline": [{"status": "OPEN", "timestamp": (now - timedelta(hours=5)).isoformat(), "actor_role": "PUBLIC_USER", "note": "Complaint submitted"}],
            "remarks": [],
            "blockchain_hash": None,
        },
        {
            "ticket_code": ticket_code(),
            "source": "WEB_PORTAL",
            "description": "No water supply for the past 3 days in Ernavoor 2nd street. Pipes may be burst.",
            "dept_id": "D03",
            "issue_category": "general_complaint",
            "ward_id": WARD_ID,
            "location_text": f"Ernavoor 2nd street, {WARD_NAME}, Chennai",
            "location": {"lat": 13.2150, "lng": 80.3260, "address": f"Ernavoor 2nd Street, {WARD_NAME}, Chennai"},
            "reporter_phone": "9876543211",
            "reporter_name": "Meena Varghese",
            "reporter_user_id": None,
            "consent_given": True,
            "consent_timestamp": now,
            "language_detected": "en",
            "ai_confidence": 0.90,
            "ai_routing_reason": "Water supply failure — routed to Water Supply dept",
            "ai_suggestions": ["Inspect pipeline", "Send water tanker immediately", "Repair burst pipe"],
            "priority_score": 85.0,
            "priority_label": "CRITICAL",
            "priority_source": "rules",
            "status": "ASSIGNED",
            "report_count": 3,
            "requires_human_review": False,
            "is_validated": True,
            "social_media_mentions": 2,
            "assigned_officer_id": str(je_water["_id"]) if je_water else None,
            "assigned_at": now - timedelta(hours=2),
            "technician_id": str(tech_water["_id"]) if tech_water else None,
            "sla_deadline": now + timedelta(days=3),
            "created_at": now - timedelta(hours=10),
            "status_timeline": [
                {"status": "OPEN", "timestamp": (now - timedelta(hours=10)).isoformat(), "actor_role": "PUBLIC_USER", "note": "Complaint submitted"},
                {"status": "ASSIGNED", "timestamp": (now - timedelta(hours=2)).isoformat(), "actor_role": "SUPERVISOR", "note": "Assigned to Water Supply JE"},
            ],
            "remarks": [{"text": "Pipeline inspection scheduled for tomorrow morning", "timestamp": (now - timedelta(hours=1)).isoformat(), "officer_id": str(je_water["_id"]) if je_water else ""}],
            "blockchain_hash": None,
        },
        {
            "ticket_code": ticket_code(),
            "source": "WEB_PORTAL",
            "description": "Garbage not collected for a week in Colony Road, Kathivakkam. Stray animals spreading waste.",
            "dept_id": "D05",
            "issue_category": "general_complaint",
            "ward_id": WARD_ID,
            "location_text": f"Colony Road, {WARD_NAME}, Chennai",
            "location": {"lat": 13.2100, "lng": 80.3200, "address": f"Colony Road, {WARD_NAME}, Chennai"},
            "reporter_phone": "9876543212",
            "reporter_name": "Suresh Nair",
            "reporter_user_id": None,
            "consent_given": True,
            "consent_timestamp": now,
            "language_detected": "en",
            "ai_confidence": 0.88,
            "ai_routing_reason": "Solid waste collection failure — routed to SWM dept",
            "ai_suggestions": ["Deploy extra collection vehicle", "Set daily schedule", "Install community bins"],
            "priority_score": 60.0,
            "priority_label": "HIGH",
            "priority_source": "rules",
            "status": "IN_PROGRESS",
            "report_count": 5,
            "requires_human_review": False,
            "is_validated": True,
            "social_media_mentions": 0,
            "assigned_officer_id": str(je_waste["_id"]) if je_waste else None,
            "assigned_at": now - timedelta(days=1),
            "technician_id": None,
            "scheduled_date": now + timedelta(days=1),
            "sla_deadline": now + timedelta(days=2),
            "created_at": now - timedelta(days=2),
            "status_timeline": [
                {"status": "OPEN", "timestamp": (now - timedelta(days=2)).isoformat(), "actor_role": "PUBLIC_USER", "note": "Complaint submitted"},
                {"status": "IN_PROGRESS", "timestamp": (now - timedelta(days=1)).isoformat(), "actor_role": "JUNIOR_ENGINEER", "note": "Collection arranged for tomorrow"},
            ],
            "remarks": [],
            "blockchain_hash": None,
        },
        {
            "ticket_code": ticket_code(),
            "source": "WEB_PORTAL",
            "description": "Street light not working near school entrance on Main Road Kathivakkam. Safety concern for children.",
            "dept_id": "D06",
            "issue_category": "general_complaint",
            "ward_id": WARD_ID,
            "location_text": f"Main Road near school, {WARD_NAME}, Chennai",
            "location": {"lat": 13.2120, "lng": 80.3240, "address": f"Main Road, {WARD_NAME}, Chennai"},
            "reporter_phone": "9876543213",
            "reporter_name": "Priya Ramachandran",
            "reporter_user_id": None,
            "consent_given": True,
            "consent_timestamp": now,
            "language_detected": "en",
            "ai_confidence": 0.82,
            "ai_routing_reason": "Street light failure — routed to Street Lighting dept",
            "ai_suggestions": ["Replace bulb immediately", "Check electrical connection", "Install solar lamp as backup"],
            "priority_score": 55.0,
            "priority_label": "MEDIUM",
            "priority_source": "rules",
            "status": "OPEN",
            "report_count": 2,
            "requires_human_review": False,
            "is_validated": False,
            "social_media_mentions": 0,
            "assigned_officer_id": None,
            "technician_id": None,
            "sla_deadline": now + timedelta(days=5),
            "created_at": now - timedelta(hours=3),
            "status_timeline": [{"status": "OPEN", "timestamp": (now - timedelta(hours=3)).isoformat(), "actor_role": "PUBLIC_USER", "note": "Complaint submitted"}],
            "remarks": [],
            "blockchain_hash": None,
        },
        {
            "ticket_code": ticket_code(),
            "source": "WEB_PORTAL",
            "description": "Sewage overflow in 3rd cross street. Foul smell and health hazard for residents.",
            "dept_id": "D04",
            "issue_category": "general_complaint",
            "ward_id": WARD_ID,
            "location_text": f"3rd Cross Street, {WARD_NAME}, Chennai",
            "location": {"lat": 13.2130, "lng": 80.3220, "address": f"3rd Cross Street, {WARD_NAME}, Chennai"},
            "reporter_phone": "9876543214",
            "reporter_name": "Anand Krishnan",
            "reporter_user_id": None,
            "consent_given": True,
            "consent_timestamp": now,
            "language_detected": "en",
            "ai_confidence": 0.92,
            "ai_routing_reason": "Sewage overflow — critical health risk — routed to Sewage & Drainage",
            "ai_suggestions": ["Clear blockage immediately", "Disinfect affected area", "Inspect drain capacity"],
            "priority_score": 90.0,
            "priority_label": "CRITICAL",
            "priority_source": "rules",
            "status": "SCHEDULED",
            "report_count": 8,
            "requires_human_review": False,
            "is_validated": True,
            "social_media_mentions": 5,
            "assigned_officer_id": None,
            "technician_id": None,
            "scheduled_date": now + timedelta(days=1),
            "sla_deadline": now + timedelta(days=3),
            "created_at": now - timedelta(days=1, hours=3),
            "status_timeline": [
                {"status": "OPEN", "timestamp": (now - timedelta(days=1, hours=3)).isoformat(), "actor_role": "PUBLIC_USER", "note": "Complaint submitted"},
                {"status": "SCHEDULED", "timestamp": (now - timedelta(hours=6)).isoformat(), "actor_role": "SUPERVISOR", "note": f"Work scheduled for {(now + timedelta(days=1)).strftime('%d %b %Y')} by Supervisor"},
            ],
            "remarks": [],
            "blockchain_hash": None,
        },
        {
            "ticket_code": ticket_code(),
            "source": "WEB_PORTAL",
            "description": "Stagnant water causing mosquito breeding in playground near Kathivakkam park. Dengue risk.",
            "dept_id": "D08",
            "issue_category": "general_complaint",
            "ward_id": WARD_ID,
            "location_text": f"Playground, {WARD_NAME}, Chennai",
            "location": {"lat": 13.2145, "lng": 80.3235, "address": f"Park Playground, {WARD_NAME}, Chennai"},
            "reporter_phone": "9876543215",
            "reporter_name": "Lakshmi Murugan",
            "reporter_user_id": None,
            "consent_given": True,
            "consent_timestamp": now,
            "language_detected": "en",
            "ai_confidence": 0.87,
            "ai_routing_reason": "Public health risk — mosquito breeding — routed to Health & Sanitation",
            "ai_suggestions": ["Fogging operation", "Drain stagnant water", "Apply anti-larval treatment"],
            "priority_score": 78.0,
            "priority_label": "HIGH",
            "priority_source": "rules",
            "status": "OPEN",
            "report_count": 4,
            "requires_human_review": False,
            "is_validated": False,
            "social_media_mentions": 1,
            "assigned_officer_id": None,
            "technician_id": None,
            "sla_deadline": now + timedelta(days=2),
            "created_at": now - timedelta(hours=8),
            "status_timeline": [{"status": "OPEN", "timestamp": (now - timedelta(hours=8)).isoformat(), "actor_role": "PUBLIC_USER", "note": "Complaint submitted"}],
            "remarks": [],
            "blockchain_hash": None,
        },
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
    print(f"  JanVedha AI — Ward {WARD_ID} ({WARD_NAME}) Complete Seed")
    print("=" * 60)

    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db_name = settings.MONGODB_URI.rsplit("/", 1)[-1].split("?")[0] or "civicai"
    db = client[db_name]

    users_col = db["users"]
    depts_col = db["departments"]

    # Drop old unique index on dept_id alone (we now use composite dept_id+ward_id)
    try:
        existing_indexes = await depts_col.index_information()
        for idx_name, idx_info in existing_indexes.items():
            key = idx_info.get("key", {})
            # Drop index if it's unique on dept_id only (not the composite one)
            if list(key.keys()) == ["dept_id"] and idx_info.get("unique", False):
                print(f"  [*] Dropping old unique index: {idx_name} on dept_id")
                await depts_col.drop_index(idx_name)
    except Exception as e:
        print(f"  [!] Could not inspect/drop indexes: {e}")
    # ── 1. Global departments ──────────────────────────────────────────────────
    print("\n[1/5] Seeding global departments (D01–D14)...")
    for dept in DEPARTMENTS:
        await upsert_department(depts_col, dept, ward_id=None)

    # ── 2. Ward-scoped departments ─────────────────────────────────────────────
    print(f"\n[2/5] Seeding Ward {WARD_ID} departments (D01–D14)...")
    for dept in DEPARTMENTS:
        await upsert_department(depts_col, dept, ward_id=WARD_ID)

    # ── 3. Supervisor + Councillor ─────────────────────────────────────────────
    print(f"\n[3/5] Seeding Supervisor & Councillor for Ward {WARD_ID}...")
    await upsert_user(users_col, SUPERVISOR)
    await upsert_user(users_col, COUNCILLOR)

    # ── 4. Junior Engineers ────────────────────────────────────────────────────
    print(f"\n[4/5] Seeding 14 Junior Engineers for Ward {WARD_ID}...")
    for je in JUNIOR_ENGINEERS:
        await upsert_user(users_col, je)

    # ── 4b. Field Staff ────────────────────────────────────────────────────────
    print(f"\n[4b] Seeding 28 Field Technicians for Ward {WARD_ID}...")
    for fs in FIELD_STAFF:
        await upsert_user(users_col, fs)

    # ── 5. Sample tickets ──────────────────────────────────────────────────────
    print(f"\n[5/5] Seeding 6 sample tickets for Ward {WARD_ID}...")
    await seed_sample_tickets(db, users_col)

    print("\n" + "=" * 60)
    print("[DONE] Seed complete!")
    print(f"\nLogin credentials (all password: '{PASSWORD}'):")
    print(f"   Supervisor  : supervisor.w{WARD_ID}@janvedha.com")
    print(f"   Councillor  : councillor.w{WARD_ID}@janvedha.com")
    for dept in DEPARTMENTS:
        slug = DEPT_SLUGS[dept['dept_id']]
        print(f"   JE ({dept['dept_id']:3s})   : je.{slug}.w{WARD_ID}@janvedha.com")
    print(f"\n   Tech (Roads): tech.roads1.w{WARD_ID}@janvedha.com")
    print(f"   Tech (Water): tech.water1.w{WARD_ID}@janvedha.com")
    print(f"   Tech (Waste): tech.waste1.w{WARD_ID}@janvedha.com")
    print("=" * 60)

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
