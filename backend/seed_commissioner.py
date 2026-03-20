"""
Seed script for Intelligence Alerts and Escalations.
Run from backend directory:  python seed_commissioner.py
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timedelta
import uuid

# ── Bootstrap Beanie ──────────────────────────────────────────────────────────
async def init_db():
    import motor.motor_asyncio
    from beanie import init_beanie

    from app.mongodb.models.intelligence_alert import IntelligenceAlertMongo
    from app.mongodb.models.escalation import EscalationMongo
    from app.core.config import settings

    client = motor.motor_asyncio.AsyncIOMotorClient(settings.MONGODB_URI)
    db_name = settings.MONGODB_URI.rsplit("/", 1)[-1].split("?")[0]
    if not db_name:
        db_name = "civicai"
    db = client[db_name]

    await init_beanie(
        database=db,
        document_models=[IntelligenceAlertMongo, EscalationMongo],
    )
    return IntelligenceAlertMongo, EscalationMongo


# ── Intelligence Alert seed data ──────────────────────────────────────────────
ALERTS = [
    {
        "pattern_type": "geographic_cluster",
        "severity": "high",
        "fingerprint": "geo_cluster_roads_ward3_seed",
        "summary": "Pothole cluster detected in Ward 3 — Thambu Chetty Palya",
        "detail": (
            "8 road damage complaints filed within a 400m radius in Ward 3 over the last 6 days. "
            "The cluster is centered near Thambu Chetty Palya junction. All tickets remain unresolved. "
            "This density is 3× the normal rate for this area."
        ),
        "recommended_action": (
            "Dispatch a Roads & Infrastructure survey team to Thambu Chetty Palya immediately. "
            "Consider a single bulk repair contract rather than individual fixes."
        ),
        "evidence": {
            "ticket_count": 8,
            "radius_metres": 400,
            "category": "roads",
            "center_lat": 12.9356,
            "center_lng": 77.6101,
        },
        "affected_ward_ids": ["3"],
        "affected_dept_id": "D01",
        "affected_area_label": "Thambu Chetty Palya, Ward 3",
        "status": "new",
    },
    {
        "pattern_type": "recurrence_spike",
        "severity": "high",
        "fingerprint": "recurrence_water_ward5_seed",
        "summary": "Water supply complaints recurring at same location in Ward 5",
        "detail": (
            "3 separate water supply tickets have been raised at the same address in Ward 5 "
            "(near Hebbal flyover) within 10 days of each other being marked resolved. "
            "This strongly suggests the root cause was not fixed — likely a leaking main line."
        ),
        "recommended_action": (
            "Escalate to Water & Sewerage department head. Require a physical pipe inspection "
            "within 48 hours before the next ticket is closed."
        ),
        "evidence": {
            "recurrence_count": 3,
            "days_between": 10,
            "location_label": "Hebbal, Ward 5",
            "category": "water",
        },
        "affected_ward_ids": ["5"],
        "affected_dept_id": "D03",
        "affected_area_label": "Hebbal Flyover Area, Ward 5",
        "status": "new",
    },
    {
        "pattern_type": "department_collapse",
        "severity": "high",
        "fingerprint": "dept_collapse_sanitation_seed",
        "summary": "Sanitation backlog growing for 3 consecutive weeks",
        "detail": (
            "The Sanitation department has received more new tickets than it resolved for 3 "
            "consecutive weeks. Backlog has grown from 12 → 19 → 27 open tickets. "
            "At this rate, average wait time will exceed the 1-day SLA within 5 days."
        ),
        "recommended_action": (
            "Call an emergency meeting with the Sanitation department head. "
            "Evaluate temporary staffing options or re-route tickets to adjacent contractors."
        ),
        "evidence": {
            "weeks_declining": 3,
            "backlog_trend": [12, 19, 27],
            "current_open": 27,
        },
        "affected_ward_ids": ["1", "2", "4"],
        "affected_dept_id": "D05",
        "status": "new",
    },
    {
        "pattern_type": "sentiment_drop",
        "severity": "medium",
        "fingerprint": "sentiment_drop_ward7_seed",
        "summary": "Public sentiment in Ward 7 dropped 22 points in 7 days",
        "detail": (
            "Social media monitoring shows Ward 7 sentiment score fell from 68 to 46 over the "
            "past week. Key driver topics: uncleared garbage, waterlogging after rain, and "
            "broken street lights near Market Road. Negative posts increased by 340%."
        ),
        "recommended_action": (
            "Issue a proactive public communication for Ward 7. Prioritise pending waste and "
            "lighting tickets in that ward this week to demonstrate responsiveness."
        ),
        "evidence": {
            "sentiment_before": 68,
            "sentiment_after": 46,
            "drop_points": 22,
            "top_topics": ["garbage", "waterlogging", "street lights"],
            "negative_post_increase_pct": 340,
        },
        "affected_ward_ids": ["7"],
        "status": "new",
    },
    {
        "pattern_type": "geographic_cluster",
        "severity": "medium",
        "fingerprint": "geo_cluster_lighting_ward2_seed",
        "summary": "Street light failures clustered on MG Road stretch, Ward 2",
        "detail": (
            "6 street light outage complaints in a 300m stretch of MG Road, Ward 2 — "
            "all reported within the last 4 days. The failures are likely due to a faulty "
            "feeder cable rather than individual lamp failures."
        ),
        "recommended_action": (
            "Send an Electrical department crew for a cable inspection of the MG Road feeder "
            "circuit. Single cable repair will resolve all 6 complaints simultaneously."
        ),
        "evidence": {
            "ticket_count": 6,
            "radius_metres": 300,
            "category": "lighting",
        },
        "affected_ward_ids": ["2"],
        "affected_dept_id": "D06",
        "affected_area_label": "MG Road, Ward 2",
        "status": "acknowledged",
        "acknowledged_by_name": "Ward Supervisor",
        "commissioner_note": "Electrical team dispatched for inspection on 19 Mar.",
    },
]


# ── Escalation seed data ───────────────────────────────────────────────────────
now = datetime.utcnow()

ESCALATIONS = [
    {
        "ward_id": "3",
        "ward_name": "Ward 3 — Thambu Chetty Palya",
        "from_councillor_id": "cllr_demo_001",
        "from_councillor_name": "Councillor Ramesh Kumar",
        "escalation_type": "infrastructure_failure",
        "subject": "Persistent pothole damage on main road causing accidents",
        "description": (
            "There have been 3 reported accidents in the last 2 weeks due to severe potholes "
            "on Thambu Chetty Palya main road. Citizens have filed multiple complaints but the "
            "Roads department has not acted. I am escalating this as a public safety emergency."
        ),
        "urgency": "high",
        "status": "received",
        "sla_hours": 48,
        "sla_deadline": now + timedelta(hours=12),  # almost breaching
        "sla_breached": False,
        "timeline": [
            {
                "event": "Escalation submitted",
                "actor": "Councillor Ramesh Kumar",
                "timestamp": now - timedelta(hours=36),
                "note": "Marked as high urgency due to accident risk.",
            }
        ],
    },
    {
        "ward_id": "5",
        "ward_name": "Ward 5 — Hebbal",
        "from_councillor_id": "cllr_demo_002",
        "from_councillor_name": "Councillor Priya Venkatesh",
        "escalation_type": "constituent_complaint",
        "subject": "Water supply disruption — 4 days without water in 3 streets",
        "description": (
            "Streets 12, 13, and 14 in Hebbal layout have had no piped water supply for 4 days. "
            "More than 200 households are affected. The Water department ticket has been open "
            "for 4 days with no update. Citizens are buying water at high cost. Immediate action needed."
        ),
        "urgency": "high",
        "status": "acknowledged",
        "sla_hours": 48,
        "sla_deadline": now - timedelta(hours=4),  # already breached
        "sla_breached": True,
        "timeline": [
            {
                "event": "Escalation submitted",
                "actor": "Councillor Priya Venkatesh",
                "timestamp": now - timedelta(hours=52),
                "note": "200+ households without water.",
            },
            {
                "event": "Acknowledged by supervisor",
                "actor": "Ward Supervisor",
                "timestamp": now - timedelta(hours=20),
                "note": "Looking into the Water dept delay.",
            },
        ],
        "commissioner_response": {
            "action_type": "dept_assignment",
            "response_text": "Assigned to Water & Sewerage dept head for immediate escalation.",
            "assigned_dept_id": "D03",
            "assigned_dept_name": "Water & Sewerage",
            "responding_commissioner_name": "Ward Supervisor",
            "responded_at": now - timedelta(hours=20),
        },
    },
    {
        "ward_id": "7",
        "ward_name": "Ward 7 — K.R. Market Area",
        "from_councillor_id": "cllr_demo_003",
        "from_councillor_name": "Councillor Sundar Nagarajan",
        "escalation_type": "constituent_complaint",
        "subject": "Garbage not collected for 6 days — public health risk",
        "description": (
            "Garbage collection in Ward 7 market area has not happened for 6 consecutive days. "
            "Waste is piling up near the vegetable market causing a public health hazard. "
            "Citizens have complained about foul smell and stray animals. Request immediate deployment."
        ),
        "urgency": "medium",
        "status": "in_progress",
        "sla_hours": 120,
        "sla_deadline": now + timedelta(hours=30),
        "sla_breached": False,
        "timeline": [
            {
                "event": "Escalation submitted",
                "actor": "Councillor Sundar Nagarajan",
                "timestamp": now - timedelta(hours=90),
            },
            {
                "event": "Acknowledged",
                "actor": "Ward Supervisor",
                "timestamp": now - timedelta(hours=72),
            },
            {
                "event": "Assigned to Sanitation dept",
                "actor": "Ward Supervisor",
                "timestamp": now - timedelta(hours=48),
                "note": "Sanitation contractor requested to clear within 24h.",
            },
        ],
        "commissioner_response": {
            "action_type": "dept_assignment",
            "assigned_dept_id": "D05",
            "assigned_dept_name": "Sanitation",
            "response_text": "Sanitation dept notified. Contractor deployment scheduled.",
            "responding_commissioner_name": "Ward Supervisor",
            "responded_at": now - timedelta(hours=48),
        },
    },
    {
        "ward_id": "2",
        "ward_name": "Ward 2 — MG Road",
        "from_councillor_id": "cllr_demo_004",
        "from_councillor_name": "Councillor Anjali Shetty",
        "escalation_type": "inter_department",
        "subject": "Street light repairs delayed — contractor dispute between Electrical and PWD",
        "description": (
            "The MG Road street light repair has been stalled for 2 weeks due to a dispute "
            "between the Electrical and PWD departments over who owns the cable trench. "
            "This inter-department issue needs commissioner-level resolution."
        ),
        "urgency": "medium",
        "status": "responded",
        "sla_hours": 120,
        "sla_deadline": now + timedelta(hours=10),
        "sla_breached": False,
        "timeline": [
            {
                "event": "Escalation submitted",
                "actor": "Councillor Anjali Shetty",
                "timestamp": now - timedelta(hours=110),
            },
            {
                "event": "Response sent",
                "actor": "Ward Supervisor",
                "timestamp": now - timedelta(hours=24),
                "note": "Meeting arranged between dept heads for 21 Mar.",
            },
        ],
        "commissioner_response": {
            "action_type": "response_sent",
            "response_text": (
                "A joint meeting between Electrical and PWD department heads has been scheduled "
                "for 21 March to resolve the ownership dispute. Both departments have been "
                "instructed to proceed with repairs under a shared cost agreement."
            ),
            "responding_commissioner_name": "Ward Supervisor",
            "responded_at": now - timedelta(hours=24),
        },
    },
    {
        "ward_id": "1",
        "ward_name": "Ward 1 — Kathivakkam",
        "from_councillor_id": "cllr_demo_005",
        "from_councillor_name": "Councillor Demo Councillor",
        "escalation_type": "scheme_issue",
        "subject": "PMAY housing scheme beneficiaries not receiving funds",
        "description": (
            "14 approved PMAY beneficiaries in Ward 1 have not received their second installment "
            "for 3 months despite bank account verification being complete. They are unable to "
            "continue construction. Requesting intervention with the housing department."
        ),
        "urgency": "normal",
        "status": "received",
        "sla_hours": 240,
        "sla_deadline": now + timedelta(hours=180),
        "sla_breached": False,
        "timeline": [
            {
                "event": "Escalation submitted",
                "actor": "Councillor Demo Councillor",
                "timestamp": now - timedelta(hours=60),
                "note": "14 families affected.",
            }
        ],
    },
]


async def seed():
    IntelligenceAlertMongo, EscalationMongo = await init_db()

    # ── Intelligence Alerts ───────────────────────────────────────────────────
    col_alerts = IntelligenceAlertMongo.get_pymongo_collection()
    inserted_alerts = 0
    for a in ALERTS:
        fp = a["fingerprint"]
        existing = await col_alerts.find_one({"fingerprint": fp})
        if existing:
            print(f"  [skip] Alert already exists: {fp}")
            continue
        doc = IntelligenceAlertMongo(
            alert_id=uuid.uuid4().hex[:10],
            pattern_type=a["pattern_type"],
            severity=a["severity"],
            fingerprint=fp,
            summary=a["summary"],
            detail=a["detail"],
            recommended_action=a.get("recommended_action", ""),
            evidence=a.get("evidence", {}),
            affected_ward_ids=a.get("affected_ward_ids", []),
            affected_dept_id=a.get("affected_dept_id"),
            affected_area_label=a.get("affected_area_label"),
            status=a.get("status", "new"),
            acknowledged_by_name=a.get("acknowledged_by_name"),
            commissioner_note=a.get("commissioner_note"),
            created_at=datetime.utcnow() - timedelta(hours=len(ALERTS) * 3),
            expires_at=datetime.utcnow() + timedelta(days=14),
        )
        await doc.insert()
        inserted_alerts += 1
        print(f"  [ok] Alert: {a['summary'][:60]}")

    # ── Escalations ───────────────────────────────────────────────────────────
    from app.mongodb.models.escalation import CommissionerResponse, TimelineEvent
    col_esc = EscalationMongo.get_pymongo_collection()
    inserted_esc = 0
    for e in ESCALATIONS:
        existing = await col_esc.find_one({
            "from_councillor_id": e["from_councillor_id"],
            "subject": e["subject"],
        })
        if existing:
            print(f"  [skip] Escalation already exists: {e['subject'][:50]}")
            continue

        resp_data = e.get("commissioner_response", {})
        resp = CommissionerResponse(
            action_type=resp_data.get("action_type"),
            response_text=resp_data.get("response_text"),
            assigned_dept_id=resp_data.get("assigned_dept_id"),
            assigned_dept_name=resp_data.get("assigned_dept_name"),
            responding_commissioner_name=resp_data.get("responding_commissioner_name"),
            responded_at=resp_data.get("responded_at"),
        ) if resp_data else CommissionerResponse()

        timeline = [
            TimelineEvent(
                event=t["event"],
                actor=t["actor"],
                timestamp=t["timestamp"],
                note=t.get("note"),
            )
            for t in e.get("timeline", [])
        ]

        doc = EscalationMongo(
            escalation_id=uuid.uuid4().hex[:10],
            ward_id=e["ward_id"],
            ward_name=e["ward_name"],
            from_councillor_id=e["from_councillor_id"],
            from_councillor_name=e["from_councillor_name"],
            escalation_type=e["escalation_type"],
            subject=e["subject"],
            description=e["description"],
            urgency=e["urgency"],
            status=e["status"],
            sla_hours=e["sla_hours"],
            sla_deadline=e.get("sla_deadline"),
            sla_breached=e.get("sla_breached", False),
            commissioner_response=resp,
            timeline=timeline,
            created_at=e["timeline"][0]["timestamp"] if e.get("timeline") else datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        await doc.insert()
        inserted_esc += 1
        print(f"  [ok] Escalation: {e['subject'][:60]}")

    print(f"\n✅ Seeded {inserted_alerts} intelligence alert(s), {inserted_esc} escalation(s).")


if __name__ == "__main__":
    asyncio.run(seed())
