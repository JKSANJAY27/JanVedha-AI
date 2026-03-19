import asyncio
import sys
import os
import uuid
import random
from datetime import datetime, timedelta

from PIL import Image, ImageDraw, ImageFont

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.mongodb.database import init_mongodb, close_mongodb
from app.mongodb.models.cctv_alert import CCTVAlert, SourceMedia, AIAnalysis, Verification
from app.mongodb.models.camera import Camera
from app.mongodb.models.ticket import TicketMongo

def create_placeholder_image(alert_id: str, label: str):
    os.makedirs("/tmp/cctv_demo", exist_ok=True)
    path = f"/tmp/cctv_demo/{alert_id}_frame.jpg"
    img = Image.new("RGB", (200, 150), color=(100, 100, 100))
    d = ImageDraw.Draw(img)
    # Basic text wrap
    words = label.split()
    lines = []
    line = ""
    for w in words:
        if len(line + w) > 25:
            lines.append(line)
            line = w + " "
        else:
            line += w + " "
    if line:
        lines.append(line)
    
    y = 20
    for l in lines:
        d.text((10, y), l, fill=(255, 255, 255))
        y += 20
        
    img.save(path)
    return path


async def seed_demo_alerts():
    print("Initialising MongoDB...")
    await init_mongodb()
    
    ward_id = "demo_ward_1"
    
    cameras = await Camera.find({"ward_id": ward_id, "status": "active"}).to_list()
    if not cameras:
        print("No cameras found. Run seed_cameras.py first.")
        await close_mongodb()
        return

    print("Clearing old demo alerts (and associated tickets roughly)...")
    await CCTVAlert.find({"ward_id": ward_id}).delete()
    
    alerts = []
    
    base_time = datetime.utcnow()
    
    data = [
        # 3 Pending (high, medium, medium)
        {
            "status": "pending_verification",
            "issue_detected": True, "conf": 0.92, "cat": "water", "sev": "high", 
            "sum": "Severe waterlogging blocking traffic", 
            "det": "There is significant waterlogging visible on the main road, covering both lanes. Vehicles are struggling to pass.",
            "ver": None, "tick": False, "days_ago": 0, "cam_idx": 0
        },
        {
            "status": "pending_verification",
            "issue_detected": True, "conf": 0.85, "cat": "waste", "sev": "medium", 
            "sum": "Garbage bin overflowing onto road", 
            "det": "The municipal garbage bin is full and waste has spilled over a 2-meter radius onto the footpath.",
            "ver": None, "tick": False, "days_ago": 1, "cam_idx": 1
        },
        {
            "status": "pending_verification",
            "issue_detected": True, "conf": 0.75, "cat": "roads", "sev": "medium", 
            "sum": "Medium pothole near bus stop", 
            "det": "A circular pothole roughly 1 meter wide is disrupting the Bus lane near the bus stop.",
            "ver": None, "tick": False, "days_ago": 2, "cam_idx": 2
        },
        # 1 Flagged
        {
            "status": "flagged_for_discussion",
            "issue_detected": True, "conf": 0.68, "cat": "other", "sev": "low", 
            "sum": "Abandoned vehicle on roadside", 
            "det": "A rusted car has been parked on the edge of the road for several days.",
            "ver": Verification(
                verified_by_id="demo_councillor_1", verified_by_name="Ravi Kumar", verified_by_role="councillor",
                verified_at=base_time - timedelta(days=2, hours=1), verification_action="flag_for_discussion",
                verifier_note="Is this our jurisdiction or traffic police?"
            ), "tick": False, "days_ago": 3, "cam_idx": 3
        },
        # 2 Ticket Raised
        {
            "status": "ticket_raised",
            "issue_detected": True, "conf": 0.88, "cat": "drainage", "sev": "high", 
            "sum": "Open manhole cover on footpath", 
            "det": "The manhole cover is completely missing, creating an immediate physical hazard.",
            "ver": Verification(
                verified_by_id="demo_supervisor_1", verified_by_name="Arun Supervisor", verified_by_role="supervisor",
                verified_at=base_time - timedelta(days=3, hours=2), verification_action="raise_ticket",
                verifier_note="Raised urgent ticket."
            ), "tick": True, "days_ago": 4, "cam_idx": 4
        },
        {
            "status": "ticket_raised",
            "issue_detected": True, "conf": 0.81, "cat": "waste", "sev": "medium", 
            "sum": "Construction debris left on road", 
            "det": "A pile of bricks and sand is partially blocking the left lane of the street.",
            "ver": Verification(
                verified_by_id="demo_councillor_1", verified_by_name="Ravi Kumar", verified_by_role="councillor",
                verified_at=base_time - timedelta(days=4, hours=12), verification_action="raise_ticket",
                verifier_note="Need clearance quickly."
            ), "tick": True, "days_ago": 5, "cam_idx": 5
        },
        # 2 Dismissed
        {
            "status": "dismissed",
            "issue_detected": False, "conf": 0.45, "cat": "none", "sev": None, 
            "sum": None, "det": None,
            "ver": Verification(
                verification_action="auto_dismissed", verifier_note="Auto-dismissed: Low confidence (45%)"
            ), "tick": False, "days_ago": 0, "cam_idx": 6
        },
        {
            "status": "dismissed",
            "issue_detected": True, "conf": 0.70, "cat": "other", "sev": "low", 
            "sum": "Minor debris near park", 
            "det": "A few loose leaves and branches next to the park wall.",
            "ver": Verification(
                verified_by_id="demo_councillor_1", verified_by_name="Ravi Kumar", verified_by_role="councillor",
                verified_at=base_time - timedelta(days=6, hours=5), verification_action="dismiss",
                verifier_note="Just regular autumn leaves. Sweepers will handle it."
            ), "tick": False, "days_ago": 6, "cam_idx": 7
        }
    ]
    
    for item in data:
        alert_id = uuid.uuid4().hex[:10]
        cam = cameras[item["cam_idx"]]
        
        path = create_placeholder_image(alert_id, f"{cam.camera_id} - {cam.location_description}")
        
        created = base_time - timedelta(days=item["days_ago"], hours=random.randint(1, 10))
        
        ai = AIAnalysis(
            issue_detected=item["issue_detected"],
            confidence_score=item["conf"],
            issue_category=item["cat"],
            severity=item["sev"],
            issue_summary=item["sum"],
            detailed_description=item["det"],
            suggested_ticket_title=f"CCTV: {item['sum']}" if item["sum"] else None,
            suggested_priority=item["sev"] if item["sev"] else None,
            what_is_visible="A regular street view with normal traffic and some pedestrians." if not item["issue_detected"] else "A street view capturing the indicated issue clearly."
        )
        
        media = SourceMedia(
            type="image",
            original_path=path,
            analysis_frame_path=path,
            uploaded_at=created,
            uploaded_by="system"
        )
        
        ticket_id = None
        if item["tick"]:
            # Determine dept_id from category
            dept_map = {
                "waste": "health",
                "water": "water_sewerage",
                "roads": "roads",
                "drainage": "water_sewerage",
                "other": "general"
            }
            dept_id_val = dept_map.get(item["cat"], "general")

            ticket_code_val = f"TK-{uuid.uuid4().hex[:6].upper()}"
            
            # Ward ID for ticket must be an int
            try:
                numeric_ward = int("".join(filter(str.isdigit, ward_id)))
            except ValueError:
                numeric_ward = 1

            ticket = TicketMongo(
                ticket_code=ticket_code_val,
                dept_id=dept_id_val,
                title=f"CCTV: {item['sum']}",
                description=f"{item['det']}\n\n[Source: CCTV Detection — {cam.location_description} | Camera: {cam.camera_id}]",
                category=item["cat"],
                priority=item["sev"],
                status="OPEN",
                ward_id=numeric_ward,
                location={"lat": cam.lat, "lng": cam.lng, "description": cam.location_description},
                created_by=item["ver"].verified_by_id,
                created_via="cctv_detection" if hasattr(TicketMongo, 'created_via') else "citizen"
            )
            # monkey patch created_via if it exists
            if hasattr(ticket, 'created_via'):
                ticket.created_via = "cctv_detection"
            await ticket.insert()
            ticket_id = str(ticket.id)
            
        alert = CCTVAlert(
            alert_id=alert_id,
            ward_id=ward_id,
            camera_id=cam.camera_id,
            camera_location_description=cam.location_description,
            camera_lat=cam.lat,
            camera_lng=cam.lng,
            area_label=cam.area_label,
            source_media=media,
            ai_analysis=ai,
            status=item["status"],
            verification=item["ver"],
            raised_ticket_id=ticket_id,
            created_at=created,
            updated_at=created
        )
        alerts.append(alert)
        
    await CCTVAlert.insert_many(alerts)
    print(f"Seed complete: {len(alerts)} alerts created.")
    
    await close_mongodb()

if __name__ == "__main__":
    asyncio.run(seed_demo_alerts())
