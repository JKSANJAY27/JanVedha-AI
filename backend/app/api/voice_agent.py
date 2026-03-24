"""
Voice Agent API — endpoints for the councillor voice assistant.

Endpoints:
  POST /api/voice-agent/ask       — Voice query (upload audio → get voice response)
  POST /api/voice-agent/briefing  — One-tap morning briefing
  GET  /api/voice-agent/languages — Available TTS/STT languages
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, UploadFile, Form, HTTPException
from pydantic import BaseModel

from app.core.dependencies import get_current_user
from app.mongodb.models.user import UserMongo
from app.enums import UserRole
from app.services.voice_agent_service import (
    handle_voice_query,
    generate_morning_briefing,
)
from app.adapters.voice.sarvam_adapter import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE

logger = logging.getLogger("voice_agent_api")

router = APIRouter()


# ── Auth guard ────────────────────────────────────────────────────────────────

def _require_councillor_or_above(
    current_user: UserMongo = Depends(get_current_user),
) -> UserMongo:
    """Allow councillors, supervisors, commissioners, and admins."""
    allowed = {
        UserRole.COUNCILLOR,
        UserRole.WARD_OFFICER,
        UserRole.ZONAL_OFFICER,
        UserRole.SUPERVISOR,
        UserRole.COMMISSIONER,
        UserRole.SUPER_ADMIN,
    }
    if current_user.role not in allowed:
        raise HTTPException(status_code=403, detail="Councillor-level access required")
    return current_user


# ── POST /ask — Voice query ──────────────────────────────────────────────────

@router.post("/ask")
async def voice_ask(
    audio: UploadFile = File(..., description="Recorded audio blob (WAV/WebM/MP3)"),
    language: Optional[str] = Form(None, description="BCP-47 language code override"),
    current_user: UserMongo = Depends(_require_councillor_or_above),
):
    """
    Upload a voice recording → get an AI-powered voice response.

    The audio is transcribed via Sarvam STT, ward data is fetched from MongoDB,
    Gemini generates a spoken-style response, and Sarvam TTS converts it to audio.
    """
    try:
        audio_bytes = await audio.read()
        if len(audio_bytes) < 100:
            raise HTTPException(status_code=400, detail="Audio file too small or empty")

        result = await handle_voice_query(
            audio_bytes=audio_bytes,
            filename=audio.filename or "recording.webm",
            user=current_user,
            language_override=language,
        )

        return {
            "transcript": result.transcript,
            "response_text": result.response_text,
            "audio_base64": result.audio_base64,
            "audio_format": result.audio_format,
            "language": result.language,
        }

    except RuntimeError as e:
        logger.error("Voice agent error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected voice agent error")
        raise HTTPException(status_code=500, detail=f"Voice agent error: {str(e)}")


# ── POST /briefing — Morning briefing ────────────────────────────────────────

class BriefingRequest(BaseModel):
    language: str = DEFAULT_LANGUAGE
    ward_id: Optional[int] = None


@router.post("/briefing")
async def voice_briefing(
    req: BriefingRequest = BriefingRequest(),
    current_user: UserMongo = Depends(_require_councillor_or_above),
):
    """
    Generate a spoken morning briefing for the councillor.
    No audio upload needed — the system aggregates ward data and speaks it.
    """
    try:
        # Allow ward_id override for supervisors
        if req.ward_id and current_user.role in {
            UserRole.SUPERVISOR, UserRole.COMMISSIONER, UserRole.SUPER_ADMIN
        }:
            # Temporarily set ward_id on user for the service
            current_user.ward_id = req.ward_id

        result = await generate_morning_briefing(
            user=current_user,
            language=req.language,
        )

        return {
            "briefing_text": result.response_text,
            "audio_base64": result.audio_base64,
            "audio_format": result.audio_format,
            "language": result.language,
        }

    except RuntimeError as e:
        logger.error("Briefing error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected briefing error")
        raise HTTPException(status_code=500, detail=f"Briefing error: {str(e)}")


# ── GET /languages — Supported languages ─────────────────────────────────────

@router.get("/languages")
async def get_supported_languages():
    """Return the list of supported STT/TTS languages."""
    return {
        "default": DEFAULT_LANGUAGE,
        "languages": [
            {"code": code, "name": name}
            for code, name in SUPPORTED_LANGUAGES.items()
        ],
    }
