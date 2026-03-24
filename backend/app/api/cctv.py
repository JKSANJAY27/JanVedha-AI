import os
import uuid
import json
import base64
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import FileResponse
import cv2

from app.mongodb.models.camera import Camera
from app.mongodb.models.cctv_alert import CCTVAlert, SourceMedia, AIAnalysis, Verification
from app.mongodb.models.ticket import TicketMongo, GeoPoint
from app.mongodb.models.notification import NotificationMongo
from app.enums import TicketSource, TicketStatus, PriorityLabel

# AI Helpers
from langchain_core.messages import HumanMessage, SystemMessage
from app.services.ai.gemini_client import get_llm

router = APIRouter()

TEMP_FRAMES_DIR = "/tmp/cctv_frames"
TEMP_UPLOADS_DIR = "/tmp/cctv_uploads"
os.makedirs(TEMP_FRAMES_DIR, exist_ok=True)
os.makedirs(TEMP_UPLOADS_DIR, exist_ok=True)


def extract_best_frame(video_path: str, alert_id: str) -> Optional[str]:
    """
    Use OpenCV to extract 5 evenly-spaced frames from a video.
    Return the path of the middle frame for analysis.
    """
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return None
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            return None

        # Calculate indices for 5 evenly-spaced frames
        indices = [int(total_frames * i / 5) for i in range(5)]
        middle_idx = indices[2]  # We use the 3rd frame (50% duration)
        
        cap.set(cv2.CAP_PROP_POS_FRAMES, middle_idx)
        ret, frame = cap.read()
        if not ret:
            cap.release()
            return None
        
        frame_path = os.path.join(TEMP_FRAMES_DIR, f"{alert_id}_frame_2.jpg")
        cv2.imwrite(frame_path, frame)
        cap.release()
        return frame_path
    except Exception as e:
        print(f"Error extracting frame: {e}")
        return None


def _bytes_to_b64(img_bytes: bytes, mime: str = "image/jpeg") -> str:
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    return f"data:{mime};base64,{b64}"


async def analyze_frame_for_civic_issues(
    frame_path: str, 
    camera_location: str,
    ward_context: str = ""
) -> dict:
    prompt = f"""
    You are analyzing a CCTV camera frame from a municipal ward in Tamil Nadu, India for civic infrastructure issues.
    
    Camera location: {camera_location}
    
    Carefully examine this image and identify any civic issues that would require municipal attention. Focus ONLY on infrastructure and civic issues — do not identify, describe, or comment on any people visible in the image.

    Civic issues to look for:
    - Road damage: potholes, cracks, broken road surface, cave-ins
    - Waterlogging or flooding on roads or public areas
    - Garbage overflow: overflowing bins, illegal dumping, large waste accumulation on roads or public land
    - Drainage issues: blocked drains, open drain covers, sewage overflow
    - Fallen trees, branches, or debris blocking roads or paths
    - Damaged public infrastructure: broken footpath, collapsed boundary wall, damaged signage

    Respond in this exact JSON format:
    {{
      "what_is_visible": "Neutral description of what the camera is showing (road, area, surroundings). Do not mention people. 2 sentences max.",
      "issue_detected": true | false,
      "confidence_score": 0.0 to 1.0 (how confident you are that a genuine civic issue exists),
      "issue_category": "roads | water | drainage | waste | other | none",
      "severity": "low | medium | high | null",
      "issue_summary": "One concise sentence describing the issue, or null if no issue detected.",
      "detailed_description": "2-3 sentence description of the issue with specific observations (size, extent, location within frame), suitable for a ticket description. Null if no issue.",
      "suggested_ticket_title": "8-12 word ticket title, null if no issue. Example: Waterlogging near school gate blocking pedestrian access",
      "suggested_priority": "low | medium | high | null",
      "analysis_notes": "Any important caveats: poor lighting, partially obstructed view, ambiguous condition. Null if none."
    }}
    
    Severity guidelines:
    - high: immediate public safety risk (flooding, fallen tree blocking road, open manhole, large pothole on main road)
    - medium: significant inconvenience, will worsen if unaddressed (garbage overflow, waterlogging, moderate road damage)
    - low: minor issue, non-urgent (small pothole, minor debris, cosmetic damage)
    
    confidence_score guidelines:
    - 0.9+: Very clear, unambiguous issue visible
    - 0.7-0.89: Clear issue but some uncertainty about severity
    - 0.5-0.69: Possible issue but image quality or angle makes it uncertain
    - Below 0.5: No clear issue or too ambiguous to determine
    
    If no civic issue is detected, set issue_detected to false and all issue fields to null.
    """
    try:
        with open(frame_path, "rb") as f:
            img_bytes = f.read()
            mime = "image/jpeg"
            if frame_path.lower().endswith(".png"): mime = "image/png"
            elif frame_path.lower().endswith(".webp"): mime = "image/webp"
            b64_img = _bytes_to_b64(img_bytes, mime)
            
        llm = get_llm()
        system = SystemMessage(content="You are an expert civic infrastructure quality AI.")
        human = HumanMessage(content=[
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": b64_img}}
        ])
        
        response = await llm.ainvoke([system, human])
        raw = str(response.content).strip()
        if raw.startswith("```json"):
            raw = raw[7:]
        if raw.startswith("```"):
            raw = raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()
        
        return json.loads(raw)
    except Exception as e:
        print(f"Gemini Analysis Failed: {e}")
        return {
            "issue_detected": False,
            "confidence_score": 0.0,
            "what_is_visible": "Analysis unavailable",
            "analysis_notes": "AI analysis failed — manual review required"
        }

# ENDPOINTS

@router.post("/upload-and-analyze")
async def upload_and_analyze(
    camera_id: str = Form(...),
    ward_id: str = Form(...),
    uploaded_by: str = Form(...),
    media_file: UploadFile = File(...)
):
    if ward_id == "1" or str(ward_id) == "1":
        ward_id = "demo_ward_1"
    camera = await Camera.find_one({"camera_id": camera_id})
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    if camera.status != "active":
        raise HTTPException(status_code=400, detail=f"Camera {camera_id} is currently inactive.")
    
    alert_id = uuid.uuid4().hex[:10]
    ext = media_file.filename.split('.')[-1]
    original_path = os.path.join(TEMP_UPLOADS_DIR, f"{alert_id}_original.{ext}")
    
    content = await media_file.read()
    with open(original_path, "wb") as f:
        f.write(content)
        
    mime_type = media_file.content_type
    is_video = mime_type.startswith("video/")
    analysis_frame_path = original_path
    
    ai_notes = None
    if is_video:
        extracted = extract_best_frame(original_path, alert_id)
        if extracted:
            analysis_frame_path = extracted
        else:
            ai_notes = "Video frame extraction failed — analyzed from original upload (if supported)"

    analysis_res = await analyze_frame_for_civic_issues(analysis_frame_path, camera.location_description, ward_id)
    if ai_notes and not analysis_res.get("analysis_notes"):
        analysis_res["analysis_notes"] = ai_notes
        
    status = "dismissed"
    verification = None
    issue_detected = analysis_res.get("issue_detected", False)
    conf = analysis_res.get("confidence_score", 0.0)
    
    if issue_detected and conf >= 0.65:
        status = "pending_verification"
    else:
        status = "dismissed"
        verification = Verification(
            verification_action="auto_dismissed",
            verifier_note=f"Auto-dismissed: {'No issue detected' if not issue_detected else f'Low confidence ({conf:.0%})'}"
        )

    alert = CCTVAlert(
        alert_id=alert_id,
        ward_id=ward_id,
        camera_id=camera_id,
        camera_location_description=camera.location_description,
        camera_lat=camera.lat,
        camera_lng=camera.lng,
        area_label=camera.area_label,
        source_media=SourceMedia(
            type="video_clip" if is_video else "image",
            original_path=original_path,
            analysis_frame_path=analysis_frame_path,
            uploaded_at=datetime.utcnow(),
            uploaded_by=uploaded_by
        ),
        ai_analysis=AIAnalysis(**analysis_res),
        status=status,
        verification=verification
    )
    await alert.insert()
    
    if status == "pending_verification":
        notif = NotificationMongo(
            notification_id=uuid.uuid4().hex[:8],
            ward_id=ward_id,
            target={"type": "role", "value": "councillor"}, # We use existing Notification format if possible, or adapt it.
            title=f"New CCTV alert — {camera.area_label}",
            body=analysis_res.get("issue_summary", "Civic issue detected"),
            type="cctv_alert",
            metadata={"alert_id": alert_id, "severity": analysis_res.get("severity")},
        )
        await notif.insert()
        # Add supervisor notification
        notif_sup = NotificationMongo(
            notification_id=uuid.uuid4().hex[:8],
            ward_id=ward_id,
            target={"type": "role", "value": "commissioner"},
            title=f"New CCTV alert — {camera.area_label}",
            body=analysis_res.get("issue_summary", "Civic issue detected"),
            type="cctv_alert",
            metadata={"alert_id": alert_id, "severity": analysis_res.get("severity")},
        )
        await notif_sup.insert()

    return {
        "alert_id": alert_id,
        "status": status,
        "issue_detected": issue_detected,
        "confidence_score": conf,
        "issue_summary": analysis_res.get("issue_summary"),
        "severity": analysis_res.get("severity"),
        "auto_dismissed": status == "dismissed",
        "camera": {
            "camera_id": camera.camera_id,
            "location_description": camera.location_description,
            "area_label": camera.area_label
        }
    }

@router.get("/alerts")
async def get_alerts(ward_id: str, status: Optional[str] = None, severity: Optional[str] = None, page: int = 1, limit: int = 20):
    if ward_id == "1" or str(ward_id) == "1":
        ward_id = "demo_ward_1"
    query = {"ward_id": ward_id}
    if status:
        query["status"] = status
    if severity:
        query["ai_analysis.severity"] = severity
        
    skip = (page - 1) * limit
    alerts = await CCTVAlert.find(query).sort("-created_at").skip(skip).limit(limit).to_list()
    
    res = []
    for a in alerts:
        d = a.dict()
        d["analysis_frame_url"] = f"/api/cctv/alerts/{a.alert_id}/frame"
        res.append(d)
    return res

@router.get("/alerts/counts")
async def get_alert_counts(ward_id: str):
    if ward_id == "1" or str(ward_id) == "1":
        ward_id = "demo_ward_1"
    pending = await CCTVAlert.find({"ward_id": ward_id, "status": "pending_verification"}).count()
    flagged = await CCTVAlert.find({"ward_id": ward_id, "status": "flagged_for_discussion"}).count()
    # Mock date filter since this is prototype
    tickets_today = await CCTVAlert.find({"ward_id": ward_id, "status": "ticket_raised"}).count()
    total = await CCTVAlert.find({"ward_id": ward_id}).count()
    
    return {
        "pending_verification": pending,
        "flagged_for_discussion": flagged,
        "ticket_raised_today": tickets_today,
        "total_alerts_this_week": total
    }

@router.get("/alerts/{alert_id}")
async def get_alert(alert_id: str):
    alert = await CCTVAlert.find_one({"alert_id": alert_id})
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    res = alert.dict()
    if alert.raised_ticket_id:
        from bson import ObjectId
        ticket = await TicketMongo.get(ObjectId(alert.raised_ticket_id))
        if ticket:
            res["raised_ticket"] = ticket.dict()
    return res

@router.get("/alerts/{alert_id}/frame")
async def get_alert_frame(alert_id: str):
    alert = await CCTVAlert.find_one({"alert_id": alert_id})
    if not alert:
        raise HTTPException(status_code=404, detail="Frame not available")
    path = alert.source_media.analysis_frame_path
    if not os.path.exists(path):
        from fastapi.responses import Response
        # Generate placeholder
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (200, 150), color=(100, 100, 100))
        d = ImageDraw.Draw(img)
        label = f"{alert.camera_id} - {alert.camera_location_description}"
        words = label.split()
        lines = []
        line = ""
        for w in words:
            if len(line + w) > 25:
                lines.append(line)
                line = w + " "
            else:
                line += w + " "
        if line: lines.append(line)
        y = 20
        for l in lines:
            d.text((10, y), l, fill=(255, 255, 255))
            y += 20
        import io
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return Response(content=buf.getvalue(), media_type="image/jpeg")

    return FileResponse(path)

from pydantic import BaseModel

class VerifyRequest(BaseModel):
    action: str
    verifier_id: str
    verifier_name: str
    verifier_role: str
    verifier_note: Optional[str] = None
    ticket_title: Optional[str] = None
    ticket_description: Optional[str] = None
    ticket_category: Optional[str] = None
    ticket_priority: Optional[str] = None
    ward_id: Optional[str] = None

@router.post("/alerts/{alert_id}/verify")
async def verify_alert(alert_id: str, req: VerifyRequest):
    alert = await CCTVAlert.find_one({"alert_id": alert_id})
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.status != "pending_verification" and alert.status != "flagged_for_discussion":
        raise HTTPException(status_code=409, detail={
            "error": "already_actioned",
            "message": f"This alert was already actioned by {alert.verification.verified_by_name if alert.verification else 'someone'} at {alert.verification.verified_at if alert.verification else 'earlier'}",
            "current_status": alert.status,
            "raised_ticket_id": alert.raised_ticket_id
        })
        
    verif = Verification(
        verified_by_id=req.verifier_id,
        verified_by_name=req.verifier_name,
        verified_by_role=req.verifier_role,
        verified_at=datetime.utcnow(),
        verification_action=req.action,
        verifier_note=req.verifier_note
    )
    
    if req.action == "raise_ticket":
        # Map category to dept_id
        dept_map = {
            "roads": "roads_dept",
            "water": "water_supply_dept",
            "drainage": "drainage_dept",
            "waste": "solid_waste_dept",
            "other": "other_dept"
        }
        dept_id = dept_map.get(req.ticket_category or "other", "other_dept")
        
        # Format ward_id
        ward_int = None
        if req.ward_id and str(req.ward_id).isdigit():
            ward_int = int(str(req.ward_id))
        elif req.ward_id == "demo_ward_1":
            ward_int = 1
            
        # Format priority
        pri_map = {
            "low": PriorityLabel.LOW,
            "medium": PriorityLabel.MEDIUM,
            "high": PriorityLabel.HIGH,
            "critical": PriorityLabel.CRITICAL
        }
        priority_enum = pri_map.get((req.ticket_priority or "medium").lower(), PriorityLabel.MEDIUM)
        
        ticket = TicketMongo(
            ticket_code=f"CCTV-{alert_id[:6].upper()}",
            dept_id=dept_id,
            issue_category=req.ticket_category,
            description=f"{req.ticket_title}\n\n{req.ticket_description}\n\n[Source: CCTV Detection — {alert.camera_location_description} | Camera: {alert.camera_id}]",
            source=TicketSource.CCTV_DETECTION,
            priority_label=priority_enum,
            ward_id=ward_int,
            location_text=alert.camera_location_description,
            location=GeoPoint.from_coords(lat=alert.camera_lat, lng=alert.camera_lng),
            status=TicketStatus.OPEN,
            reporter_name=req.verifier_name,
            reporter_user_id=req.verifier_id
        )
        await ticket.insert()
        
        alert.status = "ticket_raised"
        alert.raised_ticket_id = str(ticket.id)
        verif.priority_override = req.ticket_priority if req.ticket_priority != alert.ai_analysis.suggested_priority else None
        alert.verification = verif
        alert.updated_at = datetime.utcnow()
        await alert.save()
        
        return {"success": True, "action": "raise_ticket", "ticket_id": str(ticket.id), "ticket_title": req.ticket_title}
        
    elif req.action == "dismiss":
        alert.status = "dismissed"
        alert.verification = verif
        alert.updated_at = datetime.utcnow()
        await alert.save()
        return {"success": True, "action": "dismiss"}
        
    elif req.action == "flag_for_discussion":
        alert.status = "flagged_for_discussion"
        alert.verification = verif
        alert.updated_at = datetime.utcnow()
        await alert.save()
        return {"success": True, "action": "flag_for_discussion"}



@router.get("/cameras")
async def get_cameras(ward_id: str):
    if ward_id == "1" or str(ward_id) == "1":
        ward_id = "demo_ward_1"
    cameras = await Camera.find({"ward_id": ward_id}).to_list()
    return [c.dict() for c in cameras]

@router.post("/alerts/{alert_id}/mark-resolved")
async def mark_alert_resolved(alert_id: str):
    alert = await CCTVAlert.find_one({"alert_id": alert_id})
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    if alert.status != "ticket_raised":
        # Maybe it was already dismissed
        if alert.status == "dismissed":
             return {"success": True, "action": "already_dismissed"}
        raise HTTPException(status_code=400, detail="Alert is not in ticket_raised status")
        
    alert.status = "dismissed"
    if alert.verification:
        alert.verification.verifier_note = (alert.verification.verifier_note or "") + " [System: Ticket marked as resolved, alert dismissed]"
    alert.updated_at = datetime.utcnow()
    await alert.save()
    
    return {"success": True, "action": "mark_resolved"}

@router.get("/alerts/{alert_id}/ticket-status")
async def check_ticket_status(alert_id: str):
    alert = await CCTVAlert.find_one({"alert_id": alert_id})
    if not alert or not alert.raised_ticket_id:
        raise HTTPException(status_code=404, detail="Alert or linked ticket not found")
        
    from bson import ObjectId
    ticket = await TicketMongo.get(ObjectId(alert.raised_ticket_id))
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found in DB")
        
    if ticket.status in [TicketStatus.CLOSED, TicketStatus.CLOSED_UNVERIFIED, TicketStatus.REJECTED, TicketStatus.WITHDRAWN]:
        if alert.status != "dismissed":
            alert.status = "dismissed"
            if alert.verification:
                alert.verification.verifier_note = (alert.verification.verifier_note or "") + f" [System: Auto-dismissed because ticket is now {ticket.status}]"
            alert.updated_at = datetime.utcnow()
            await alert.save()
            return {"status": "dismissed", "ticket_status": ticket.status, "updated": True}
            
    return {"status": alert.status, "ticket_status": ticket.status, "updated": False}

