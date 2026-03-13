"""
Seed script: populate the ward_benchmarks collection with 3 synthetic peer wards.

Usage:
    cd backend
    python scripts/seed_ward_benchmarks.py

Safe to run multiple times — clears existing benchmark data before inserting.
"""
import asyncio
import sys
import os

# Allow running from the backend/ directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.mongodb.database import init_mongodb, close_mongodb
from app.mongodb.models.ward_benchmark import WardBenchmarkMongo


PEER_WARDS = [
    {
        "ward_name": "Adyar Zone",
        "ward_id": 101,
        "avg_resolution_days_by_dept": {
            "Roads & Infrastructure": 2.8,
            "Electrical": 1.4,
            "Water Supply": 3.1,
            "Sanitation & Waste": 2.0,
        },
        "ticket_volume": 312,
        "technician_count": 18,
        "resolution_rate_pct": 84.6,
        "top_practice": "Pre-assigned dedicated technicians per category — Roads issues always go to the same crew, reducing handoff time.",
        "notes": "Consistently top-performing zone. Strong technician specialization.",
    },
    {
        "ward_name": "Tambaram Zone",
        "ward_id": 102,
        "avg_resolution_days_by_dept": {
            "Roads & Infrastructure": 5.4,
            "Electrical": 2.9,
            "Water Supply": 4.7,
            "Sanitation & Waste": 3.5,
        },
        "ticket_volume": 278,
        "technician_count": 12,
        "resolution_rate_pct": 71.2,
        "top_practice": "Twice-weekly batch scheduling — all OPEN tickets reviewed every Monday and Thursday, reducing idle queue time.",
        "notes": "Mid-tier performer. Electrical and Roads are bottlenecks due to shared technician pool.",
    },
    {
        "ward_name": "Kodambakkam Zone",
        "ward_id": 103,
        "avg_resolution_days_by_dept": {
            "Roads & Infrastructure": 3.9,
            "Electrical": 1.8,
            "Water Supply": 2.6,
            "Sanitation & Waste": 1.9,
        },
        "ticket_volume": 395,
        "technician_count": 22,
        "resolution_rate_pct": 78.9,
        "top_practice": "Sanitation handled by rotating two-person teams with GPS tracked routes — no duplicate assignments, faster sweeps.",
        "notes": "High ticket volume with good throughput. Water + Electrical are strengths; Roads is an outlier.",
    },
]


async def seed():
    print("Connecting to MongoDB...")
    await init_mongodb()

    print("Clearing existing benchmark data...")
    await WardBenchmarkMongo.find_all().delete()

    print(f"Inserting {len(PEER_WARDS)} peer ward benchmarks...")
    for pw in PEER_WARDS:
        doc = WardBenchmarkMongo(**pw)
        await doc.insert()
        print(f"  > Inserted: {pw['ward_name']}")

    print("\nSeed complete! Ward benchmarks are ready.")
    await close_mongodb()


if __name__ == "__main__":
    asyncio.run(seed())
