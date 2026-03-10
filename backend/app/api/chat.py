"""
Chat WebSocket API — Gemini-powered civic assistant with live data & RBAC.
"""
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from datetime import datetime
from app.core.config import settings
from app.services.auth_service import AuthService
from app.mongodb.models.user import UserMongo
from app.mongodb.models.ticket import TicketMongo
from app.enums import UserRole
import google.generativeai as genai
from google.generativeai.types import content_types

router = APIRouter()

# Global config
genai.configure(api_key=settings.GEMINI_API_KEY)


def get_base_system_prompt(role: str, name: str, ward_id: int = None) -> str:
    prompt = f"""You are JanVedha AI's conversational assistant for the Chennai Municipal Corporation.
You are currently talking to: {name} (Role: {role}).
"""
    if ward_id:
        prompt += f"They are associated with Ward {ward_id}.\n"

    prompt += """
You can answer questions about the municipal corporation, SLAs, and rules.
CRITICAL: You are connected to live databases via tools! 
If they ask for ticket status, ward stats, or city summaries, ALWAYS USE THE TOOLS PROVIDED. Do not make up ticket statuses.

SLA policies:
- Critical (80+): 72hrs
- High (60-79): 7 days
- Medium (35-59): 14 days
- Low (0-34): 30 days

If asked about a specific ticket code (format: CIV-YYYY-XXXXX) use the `get_ticket_details` tool.
Be concise, helpful, and empathetic. Do not use markdown that won't format well in a small chat window.
"""
    return prompt


# ─── Live Data Functions (for Gemini Tools) ───────────────────────────────────

async def get_ticket_details(ticket_code: str) -> dict:
    """Fetch live details of a specific ticket by its code (e.g. CIV-2026-ABCDE). Use only when user provides a specific ticket code."""
    ticket = await TicketMongo.find_one(TicketMongo.ticket_code == ticket_code)
    if not ticket:
        return {"error": f"Ticket code {ticket_code} not found. Please double check the code."}
    
    return {
        "ticket_code": ticket.ticket_code,
        "status": ticket.status,
        "priority_label": ticket.priority_label,
        "priority_score": ticket.priority_score,
        "ward_id": ticket.ward_id,
        "department": ticket.dept_id,
        "created_at": ticket.created_at.strftime("%Y-%m-%d"),
        "issue_category": ticket.issue_category,
        "sla_deadline": ticket.sla_deadline.strftime("%Y-%m-%d") if ticket.sla_deadline else "N/A"
    }

async def get_ward_summary(ward_id: int) -> dict:
    """Fetch live summary of tickets for a specific ward. Give the user counts of open, closed, and overdue tickets."""
    tickets = await TicketMongo.find(TicketMongo.ward_id == ward_id).to_list()
    if not tickets:
        return {"message": f"No tickets found for ward {ward_id}."}
    
    total = len(tickets)
    closed = sum(1 for t in tickets if t.status in {"CLOSED", "REJECTED"})
    open_tickets = total - closed
    
    now = datetime.utcnow()
    overdue = sum(1 for t in tickets if t.status not in {"CLOSED", "REJECTED"} and t.sla_deadline and t.sla_deadline < now)
    
    return {
        "ward_id": ward_id,
        "total_tickets": total,
        "open_tickets": open_tickets,
        "closed_tickets": closed,
        "overdue_tickets": overdue,
        "resolution_rate": f"{(closed/total*100):.1f}%" if total > 0 else "0%"
    }

async def get_city_summary() -> dict:
    """Fetch live system-wide summary metrics for the entire city. Call this if the user asks for overall, city, or global stats."""
    tickets = await TicketMongo.find_all().to_list()
    if not tickets:
        return {"message": "No tickets found in the city."}
        
    total = len(tickets)
    closed = sum(1 for t in tickets if t.status in {"CLOSED", "REJECTED"})
    open_tickets = total - closed
    
    now = datetime.utcnow()
    overdue = sum(1 for t in tickets if t.status not in {"CLOSED", "REJECTED"} and t.sla_deadline and t.sla_deadline < now)

    return {
        "city_total_tickets": total,
        "city_open_tickets": open_tickets,
        "city_closed_tickets": closed,
        "city_overdue_tickets": overdue,
        "city_resolution_rate": f"{(closed/total*100):.1f}%" if total > 0 else "0%"
    }

# We pass these to Gemini
TOOLS = [get_ticket_details, get_ward_summary, get_city_summary]


async def call_gemini(message: str, history: list[dict], user: UserMongo = None) -> str:
    """Call Gemini API utilizing Function Calling for live data."""
    try:
        # Determine RBAC Context
        role = user.role if user else "PUBLIC_USER"
        name = user.name if user else "Citizen"
        ward_id = user.ward_id if hasattr(user, "ward_id") else None

        system_instruction = get_base_system_prompt(role, name, ward_id)

        # Remove restricted tools based on RBAC
        available_tools = [get_ticket_details] # Everyone can query ticket codes
        
        if role in {UserRole.COUNCILLOR, UserRole.WARD_OFFICER, UserRole.ZONAL_OFFICER, UserRole.SUPERVISOR, UserRole.SUPER_ADMIN, UserRole.COMMISSIONER}:
            available_tools.append(get_ward_summary)
            
        if role in {UserRole.SUPERVISOR, UserRole.COMMISSIONER, UserRole.SUPER_ADMIN}:
            available_tools.append(get_city_summary)

        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=system_instruction,
            tools=available_tools
        )

        # Build conversation history
        chat_history = []
        for h in history[-8:]:  # Last 8 plain messages
            r = "user" if h["role"] == "user" else "model"
            chat_history.append({"role": r, "parts": [h["text"]]})

        chat = model.start_chat(history=chat_history)
        
        # We need to manually handle function calling loop if Gemini decides to call a function.
        # But `chat.send_message` in the python SDK correctly auto-calls functions if they are Python functions!
        response = await chat.send_message_async(message)
        
        return response.text
    except Exception as e:
        # Fallback
        lower = message.lower()
        if "ticket" in lower or "civ-" in lower.upper():
            return "To track your ticket, please visit the **Track** page. I encountered an error accessing live data right now."
        return "I'm here to help with civic issues! You can ask me about filing complaints or tracking tickets."


@router.websocket("/ws")
async def chat_websocket(websocket: WebSocket, token: str = None):
    """Real-time Gemini chatbot via WebSocket, authenticated via query param."""
    await websocket.accept()
    
    # 1. Auth via JWT token
    user = None
    if token:
        try:
            payload = AuthService.decode_access_token(token)
            uid = payload.get("sub")
            if uid:
                from beanie import PydanticObjectId
                user = await UserMongo.get(PydanticObjectId(uid))
        except Exception:
            pass

    history: list[dict] = []

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)

            if payload.get("type") == "USER_MESSAGE":
                user_text = payload.get("message", "")
                if not user_text.strip():
                    continue

                # Add to history
                history.append({"role": "user", "text": user_text})

                # Send typing indicator
                await websocket.send_text(json.dumps({"type": "TYPING"}))

                # Get Gemini response
                bot_reply = await call_gemini(user_text, history, user)
                history.append({"role": "bot", "text": bot_reply})

                # Build action buttons for common queries
                actions = []
                lower = user_text.lower()
                if "track" in lower or "ticket" in lower or "civ-" in lower.upper():
                    actions.append({"label": "Track Ticket", "href": "/track"})
                if "file" in lower or "submit" in lower or "complain" in lower:
                    actions.append({"label": "Submit Complaint", "href": "/"})
                
                # Check RBAC for button logic
                r = user.role if user else "PUBLIC_USER"
                if ("ward" in lower) and r in ["COUNCILLOR", "WARD_OFFICER"]:
                    actions.append({"label": "Ward Dashboard", "href": "/councillor"})
                if "city" in lower and r in ["COMMISSIONER", "SUPER_ADMIN"]:
                     actions.append({"label": "City Dashboard", "href": "/commissioner"})

                await websocket.send_text(json.dumps({
                    "type": "BOT_MESSAGE",
                    "message": bot_reply,
                    "actions": actions if actions else None,
                }))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_text(json.dumps({
                "type": "BOT_MESSAGE",
                "message": "I encountered an error. Please try again.",
            }))
        except Exception:
            pass
