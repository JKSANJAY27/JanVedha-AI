"""
Seed demo casework entries for ward_id 1 (demo ward).

Run from: /backend
  python -m app.scripts.seed_demo_casework
"""
import asyncio
import uuid
from datetime import datetime, timedelta

from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
import certifi

from app.core.config import settings

MONGODB_URI = settings.MONGODB_URI

NAMES = ["Murugan", "Lakshmi", "Suresh", "Priya", "Rajan",
         "Meenakshi", "Karthi", "Selvi", "Balu", "Anbu"]

PHONES = [
    "9876543210",  # escalation phone
    "9123456789",
    "8234567890",
    "9345678901",
    "8456789012",
    "9567890123",
    "8678901234",
    "9789012345",
    "8890123456",
    "9901234567",
]

RECEIVED_MODES = ["walk_in", "phone_call", "whatsapp", "other"]

WARD_ID = 1

DEMO_ENTRIES = [
    # 5 logged (no ticket)
    {
        "constituent_name": "Murugan",
        "constituent_phone": PHONES[1],
        "complaint_description": "Street light on Anna Nagar 3rd Street has been non-functional for 2 weeks.",
        "complaint_category": "lighting",
        "location_description": "Anna Nagar 3rd Street",
        "urgency": "medium",
        "how_received": "walk_in",
        "status": "logged",
    },
    {
        "constituent_name": "Lakshmi",
        "constituent_phone": PHONES[2],
        "complaint_description": "Garbage not collected for 5 days near Nehru Park. Stray dogs are a problem.",
        "complaint_category": "waste",
        "location_description": "Near Nehru Park",
        "urgency": "high",
        "how_received": "phone_call",
        "status": "logged",
    },
    {
        "constituent_name": "Suresh",
        "constituent_phone": PHONES[3],
        "complaint_description": "Pothole on T. Nagar main road causing accidents. Needs urgent repair.",
        "complaint_category": "roads",
        "location_description": "T. Nagar main road near Panagal Park",
        "urgency": "high",
        "how_received": "whatsapp",
        "status": "logged",
    },
    {
        "constituent_name": "Karthi",
        "constituent_phone": PHONES[6],
        "complaint_description": "Enquiry about PM Awas Yojana scheme eligibility for new construction.",
        "complaint_category": "scheme_enquiry",
        "location_description": None,
        "urgency": "low",
        "how_received": "walk_in",
        "status": "logged",
    },
    {
        "constituent_name": "Selvi",
        "constituent_phone": PHONES[7],
        "complaint_description": "Road in front of GH Hospital is heavily flooded after rain. No drainage.",
        "complaint_category": "drainage",
        "location_description": "GH Hospital entrance road",
        "urgency": "high",
        "how_received": "phone_call",
        "status": "logged",
    },
    # 4 with ticket_linked (offset tickets assumed)
    {
        "constituent_name": "Priya",
        "constituent_phone": PHONES[4],
        "complaint_description": "Borewell near Saidapet bus stop has been leaking for 3 days.",
        "complaint_category": "water",
        "location_description": "Saidapet bus stop",
        "urgency": "medium",
        "how_received": "whatsapp",
        "status": "ticket_linked",
        "ticket_created": False,
    },
    {
        "constituent_name": "Rajan",
        "constituent_phone": PHONES[5],
        "complaint_description": "Overhead water tank not filled since Monday, residents facing acute shortage.",
        "complaint_category": "water",
        "location_description": "Block 4, Ashok Nagar",
        "urgency": "high",
        "how_received": "walk_in",
        "status": "ticket_linked",
        "ticket_created": False,
    },
    {
        "constituent_name": "Anbu",
        "constituent_phone": PHONES[9],
        "complaint_description": "Open drain overflow near KK Nagar market, foul smell affecting whole street.",
        "complaint_category": "drainage",
        "location_description": "KK Nagar market street",
        "urgency": "high",
        "how_received": "phone_call",
        "status": "ticket_linked",
        "ticket_created": False,
    },
    {
        "constituent_name": "Balu",
        "constituent_phone": PHONES[8],
        "complaint_description": "Speed breaker near school zone on Arcot Road completely washed away.",
        "complaint_category": "roads",
        "location_description": "Arcot Road near Vel's School",
        "urgency": "medium",
        "how_received": "other",
        "status": "ticket_linked",
        "ticket_created": False,
    },
    # 3 follow_up_sent
    {
        "constituent_name": "Meenakshi",
        "constituent_phone": PHONES[2],
        "complaint_description": "Stray animal menace on South Mada Street, resident bitten yesterday.",
        "complaint_category": "general",
        "location_description": "South Mada Street",
        "urgency": "high",
        "how_received": "phone_call",
        "status": "follow_up_sent",
        "follow_up": True,
    },
    {
        "constituent_name": "Suresh",
        "constituent_phone": PHONES[3],
        "complaint_description": "Street vendor encroachment blocking pedestrian path near Metro station.",
        "complaint_category": "general",
        "location_description": "Koyambedu Metro Station entrance",
        "urgency": "medium",
        "how_received": "whatsapp",
        "status": "follow_up_sent",
        "follow_up": True,
    },
    {
        "constituent_name": "Priya",
        "constituent_phone": PHONES[4],
        "complaint_description": "Public toilet near corporation park not cleaned, unhygienic conditions.",
        "complaint_category": "waste",
        "location_description": "Corporation Park, Nungambakkam",
        "urgency": "medium",
        "how_received": "walk_in",
        "status": "follow_up_sent",
        "follow_up": True,
    },
    # 2 escalations: same phone (9876543210), category water, 3 entries
    {
        "constituent_name": "Rajan",
        "constituent_phone": PHONES[0],  # 9876543210 — repeated
        "complaint_description": "No water supply to our entire street for 2 days. Overhead tank not filled.",
        "complaint_category": "water",
        "location_description": "7th Avenue, Ashok Nagar",
        "urgency": "high",
        "how_received": "phone_call",
        "status": "escalated",
        "escalation_flag": True,
        "created_days_ago": 25,
    },
    {
        "constituent_name": "Rajan",
        "constituent_phone": PHONES[0],
        "complaint_description": "Water supply still not restored. Same issue from last week, no action taken.",
        "complaint_category": "water",
        "location_description": "7th Avenue, Ashok Nagar",
        "urgency": "high",
        "how_received": "whatsapp",
        "status": "escalated",
        "escalation_flag": True,
        "created_days_ago": 10,
    },
    # 1 resolved
    {
        "constituent_name": "Lakshmi",
        "constituent_phone": PHONES[2],
        "complaint_description": "Transformer blown on Valluvar Kottam High Road. Entire block without power for 6 hours.",
        "complaint_category": "lighting",
        "location_description": "Valluvar Kottam High Road",
        "urgency": "high",
        "how_received": "phone_call",
        "status": "resolved",
        "resolved": True,
    },
]


async def seed():
    from app.mongodb.models.casework import CaseworkMongo, ConstituentData, ComplaintData, VoiceNoteData, FollowUpData
    
    client = AsyncIOMotorClient(MONGODB_URI, tlsCAFile=certifi.where())
    db_name = MONGODB_URI.rsplit("/", 1)[-1].split("?")[0] or "civicai"
    database = client[db_name]
    
    await init_beanie(database=database, document_models=[CaseworkMongo])
    
    # Delete existing demo data for ward 1
    existing = await CaseworkMongo.find(CaseworkMongo.ward_id == WARD_ID).to_list()
    for cw in existing:
        await cw.delete()
    print(f"Cleared {len(existing)} existing casework entries for ward {WARD_ID}.")
    
    now = datetime.utcnow()
    
    for i, entry in enumerate(DEMO_ENTRIES):
        days_ago = entry.get("created_days_ago", i + 1)
        created_at = now - timedelta(days=days_ago)
        
        follow_ups = []
        if entry.get("follow_up"):
            fu = FollowUpData(
                follow_up_id=uuid.uuid4().hex[:8],
                generated_at=created_at + timedelta(hours=2),
                language="both",
                english_text=f"Dear {entry['constituent_name']}, I have noted your complaint about {entry['complaint_category']} and taken it up with the relevant department. Action will be completed within 3 working days. - Councillor Demo",
                tamil_text=f"அன்புள்ள {entry['constituent_name']}, உங்கள் {entry['complaint_category']} தொடர்பான புகாரை கவனத்தில் கொண்டு தொடர்புடைய துறையிடம் தெரிவித்துள்ளேன். 3 வேலை நாட்களில் நடவடிக்கை எடுக்கப்படும். - கவுன்சிலர்",
                sent=True,
                sent_at=created_at + timedelta(hours=3),
                sent_via="whatsapp_manual",
            )
            follow_ups.append(fu)
        
        esc_flag = entry.get("escalation_flag", False)
        esc_reason = None
        if esc_flag:
            esc_reason = f"This constituent has raised 3 water complaints in the past 30 days. Personal intervention may be needed."
        
        casework = CaseworkMongo(
            casework_id=uuid.uuid4().hex[:10],
            ward_id=WARD_ID,
            councillor_id="demo_councillor_1",
            councillor_name="Councillor Demo",
            constituent=ConstituentData(
                name=entry["constituent_name"],
                phone=entry["constituent_phone"],
                address=entry.get("location_description"),
                preferred_language="both",
            ),
            complaint=ComplaintData(
                description=entry["complaint_description"],
                category=entry["complaint_category"],
                location_description=entry.get("location_description"),
                urgency=entry["urgency"],
                how_received=entry["how_received"],
            ),
            voice_note=VoiceNoteData(),
            linked_ticket_id=None,
            ticket_created=entry.get("ticket_created", False),
            follow_ups=follow_ups,
            status=entry["status"],
            escalation_flag=esc_flag,
            escalation_reason=esc_reason,
            created_at=created_at,
            updated_at=created_at,
        )
        await casework.insert()
        print(f"  [{i+1:02d}/{len(DEMO_ENTRIES)}] {entry['constituent_name']} — {entry['complaint_category']} — {entry['status']}")
    
    print(f"\n✅ Seeded {len(DEMO_ENTRIES)} casework entries for ward {WARD_ID}.")
    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
