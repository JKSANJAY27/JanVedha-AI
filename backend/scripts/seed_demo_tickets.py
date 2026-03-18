"""
Seed script: Creates 60 realistic geo-tagged demo tickets for testing
the Infrastructure Opportunity Spotter.

Usage:
    python scripts/seed_demo_tickets.py [--ward-id 1] [--mongo-uri mongodb://...]

Area: Chennai Adyar area (lat 12.96–12.98, lng 80.23–80.26)
"""
import asyncio
import argparse
import random
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient

# ── CLI args ──────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Seed demo tickets for Opportunity Spotter")
parser.add_argument("--ward-id", type=int, default=1, help="Ward ID to seed tickets for")
parser.add_argument("--mongo-uri", default="mongodb://localhost:27017/civicai", help="MongoDB URI")
parser.add_argument("--dry-run", action="store_true", help="Print tickets without inserting")
args = parser.parse_args()

WARD_ID = args.ward_id
MONGO_URI = args.mongo_uri

# ── Ticket data ───────────────────────────────────────────────────────────────

CATEGORIES = ["roads", "water", "lighting", "drainage", "waste"]
STATUSES = ["OPEN", "IN_PROGRESS", "CLOSED"]

# Pre-defined clusters — each cluster is (center_lat, center_lng, primary_category, count)
CLUSTERS = [
    (12.9650, 80.2350, "drainage", 10),   # Zone A: recurring drainage issues
    (12.9700, 80.2400, "roads", 9),        # Zone B: road damage cluster
    (12.9760, 80.2450, "water", 8),        # Zone C: water supply issues
    (12.9720, 80.2480, "lighting", 8),     # Zone D: streetlight failures
    (12.9680, 80.2520, "waste", 7),        # Zone E: waste management
    (12.9640, 80.2600, "drainage", 5),     # Zone F: secondary drainage
    (12.9790, 80.2380, "roads", 5),        # Zone G: pothole cluster
]

DESCRIPTIONS = {
    "roads": [
        "Large pothole on main road causing accidents",
        "Road surface completely broken near bus stop",
        "Water logging on road after rain due to no drainage",
        "Road cave-in risk — needs immediate repair",
        "Footpath encroached and road narrowed dangerously",
    ],
    "water": [
        "Water supply line broken — no water for 3 days",
        "Pipe leakage flooding the road",
        "Contaminated water supply — residents falling sick",
        "Low pressure water supply in the morning",
        "No water connection to 3 houses on this street",
    ],
    "lighting": [
        "Streetlight not working for 2 weeks",
        "Multiple lights on the stretch are dark — unsafe at night",
        "Lights flickering and turning off randomly",
        "No lighting on the main road near school",
        "Light pole fallen — safety hazard",
    ],
    "drainage": [
        "Drainage blocked — stagnant water breeding mosquitoes",
        "Open drain overflow during rain",
        "Drain completely choked with garbage",
        "Flooding on road due to blocked storm drain",
        "Manhole cover missing — danger to pedestrians",
    ],
    "waste": [
        "Garbage not collected for 5 days",
        "Illegal dumping site near residential area",
        "Waste bin overflowing — foul smell",
        "No garbage collection van coming to this area",
        "Compost waste left on road for weeks",
    ],
}


def random_jitter(radius_deg=0.002):
    """Random offset within radius."""
    return random.uniform(-radius_deg, radius_deg)


def random_date_within_days(days_back=240):
    """Random datetime within the past N days."""
    return datetime.utcnow() - timedelta(days=random.uniform(0, days_back))


def make_ticket(i: int, lat: float, lng: float, category: str, ward_id: int) -> dict:
    """Build a single ticket dict."""
    status = random.choices(
        ["OPEN", "IN_PROGRESS", "CLOSED"],
        weights=[0.35, 0.2, 0.45]
    )[0]

    created_at = random_date_within_days(240)
    resolved_at = None
    if status == "CLOSED":
        resolved_at = created_at + timedelta(days=random.randint(1, 30))

    description = random.choice(DESCRIPTIONS[category])

    return {
        "ticket_code": f"DEMO-{ward_id:02d}-{i:04d}",
        "source": "WEB_PORTAL",
        "description": description,
        "dept_id": {
            "roads": "PWD",
            "water": "WATER",
            "lighting": "ELEC",
            "drainage": "DRAINAGE",
            "waste": "SWM",
        }.get(category, "PWD"),
        "issue_category": category,
        "ward_id": ward_id,
        "location": {
            "type": "Point",
            "coordinates": [round(lng, 6), round(lat, 6)],  # GeoJSON: [lng, lat]
        },
        "coordinates": f"{lat},{lng}",
        "status": status,
        "priority_score": round(random.uniform(20, 90), 1),
        "priority_label": random.choice(["LOW", "MEDIUM", "HIGH", "CRITICAL"]),
        "priority_source": "rules",
        "report_count": random.randint(1, 5),
        "created_at": created_at,
        "resolved_at": resolved_at,
        "consent_given": True,
        "consent_timestamp": created_at,
    }


async def seed():
    db_name = MONGO_URI.rsplit("/", 1)[-1].split("?")[0] or "civicai"
    client = AsyncIOMotorClient(MONGO_URI)
    col = client[db_name]["tickets"]

    tickets = []
    i = 1

    for center_lat, center_lng, primary_cat, count in CLUSTERS:
        for j in range(count):
            # Primary category with occasional mixed tickets nearby
            cat = primary_cat if j < count - 2 else random.choice(CATEGORIES)
            lat = center_lat + random_jitter(0.0015)
            lng = center_lng + random_jitter(0.0015)
            tickets.append(make_ticket(i, lat, lng, cat, WARD_ID))
            i += 1

    # Fill remaining to reach 60 total (scattered across the area)
    while len(tickets) < 60:
        lat = random.uniform(12.960, 12.980)
        lng = random.uniform(80.230, 80.260)
        cat = random.choice(CATEGORIES)
        tickets.append(make_ticket(i, lat, lng, cat, WARD_ID))
        i += 1

    if args.dry_run:
        print(f"Would insert {len(tickets)} tickets for ward {WARD_ID}")
        for t in tickets[:3]:
            import json
            print(json.dumps({**t, "created_at": str(t["created_at"]), "resolved_at": str(t.get("resolved_at"))}, indent=2))
        return

    # Check existing demo tickets to avoid duplicates
    existing = await col.count_documents({"ward_id": WARD_ID, "ticket_code": {"$regex": "^DEMO-"}})
    if existing > 0:
        print(f"Found {existing} existing DEMO tickets for ward {WARD_ID}. Skipping seed.")
        print("Use --force to delete and re-seed (delete manually from mongo first).")
        client.close()
        return

    result = await col.insert_many(tickets)
    print(f"Inserted {len(result.inserted_ids)} demo tickets for ward {WARD_ID}")
    print(f"  Clusters: {len(CLUSTERS)}, Scattered: {len(tickets) - sum(c[3] for c in CLUSTERS)}")
    client.close()


asyncio.run(seed())
