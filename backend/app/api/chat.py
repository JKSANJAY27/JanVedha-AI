"""
Chat WebSocket API — Gemini-powered civic assistant.
"""
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.config import settings

router = APIRouter()

SYSTEM_PROMPT = """You are JanVedha AI's civic assistant for the Chennai Municipal Corporation.
You help citizens and officers with:
- Tracking complaint status (ask the user for their ticket code)
- Filing complaints (guide them to the /submit page)
- SLA policies (Critical: 72hrs, High: 7 days, Medium: 14 days, Low: 30 days)
- Department information (Water:D01, Roads:D02, Sewerage:D03, Waste:D04, Lighting:D05)
- Ward performance stats
- General civic queries

Be concise, helpful, and empathetic. Always respond in English unless the user writes in Tamil.
If asked about a specific ticket code (format: CIV-YYYY-XXXXX), tell them to use the /track page.
"""


async def call_gemini(message: str, history: list[dict]) -> str:
    """Call Gemini API for a chat response."""
    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(
            "gemini-1.5-flash",
            system_instruction=SYSTEM_PROMPT,
        )
        # Build conversation history for Gemini
        chat_history = []
        for h in history[-10:]:  # Last 10 messages for context
            role = "user" if h["role"] == "user" else "model"
            chat_history.append({"role": role, "parts": [h["text"]]})

        chat = model.start_chat(history=chat_history)
        response = chat.send_message(message)
        return response.text
    except Exception as e:
        # Graceful fallback
        lower = message.lower()
        if "ticket" in lower or "civ-" in lower.upper():
            return "To track your ticket, please visit the **Track** page and enter your ticket code (format: CIV-YYYY-XXXXX). I can't access live ticket data in chat, but our tracking page shows full status and timeline."
        if "file" in lower or "submit" in lower or "complain" in lower:
            return "To file a complaint, go to our **Home** page. Fill in the issue description, add a photo if possible, use GPS to auto-detect your location, and enter your mobile number. Our AI will instantly classify and route your complaint!"
        if "sla" in lower or "deadline" in lower or "time" in lower:
            return "Our SLA timelines:\n🔴 **Critical** (80+): 72 hours\n🟠 **High** (60-79): 7 days\n🟡 **Medium** (35-59): 14 days\n🟢 **Low** (0-34): 30 days"
        if "ward" in lower or "performance" in lower:
            return "Ward performance rankings are available on our **Leaderboard** page. You can see resolution rates, ticket counts, and grades for all wards."
        return "I'm here to help with civic issues! You can ask me about filing complaints, tracking tickets, SLA timelines, or ward performance. How can I assist you?"


@router.websocket("/ws")
async def chat_websocket(websocket: WebSocket):
    """Real-time Gemini chatbot via WebSocket."""
    await websocket.accept()
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
                bot_reply = await call_gemini(user_text, history)
                history.append({"role": "bot", "text": bot_reply})

                # Build action buttons for common queries
                actions = []
                lower = user_text.lower()
                if "track" in lower or "ticket" in lower or "civ-" in lower.upper():
                    actions.append({"label": "Track Ticket", "href": "/track"})
                if "file" in lower or "submit" in lower or "complain" in lower:
                    actions.append({"label": "Submit Complaint", "href": "/"})
                if "map" in lower or "location" in lower:
                    actions.append({"label": "View Map", "href": "/map"})
                if "ward" in lower or "leaderboard" in lower:
                    actions.append({"label": "View Leaderboard", "href": "/ward-performance"})

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
