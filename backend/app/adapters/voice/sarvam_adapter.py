"""
Sarvam AI Voice Adapter — STT (Saaras v3) + TTS (Bulbul v3).

Sarvam API docs:
  STT: POST https://api.sarvam.ai/speech-to-text  (multipart/form-data)
  TTS: POST https://api.sarvam.ai/text-to-speech  (application/json)
"""
import logging
from dataclasses import dataclass
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger("sarvam")

SARVAM_BASE = "https://api.sarvam.ai"

# Supported languages (BCP-47 codes for Sarvam)
SUPPORTED_LANGUAGES = {
    "en-IN": "English (India)",
    "hi-IN": "Hindi",
    "ta-IN": "Tamil",
    "te-IN": "Telugu",
    "kn-IN": "Kannada",
    "ml-IN": "Malayalam",
    "bn-IN": "Bengali",
    "gu-IN": "Gujarati",
    "mr-IN": "Marathi",
    "pa-IN": "Punjabi",
    "od-IN": "Odia",
}

DEFAULT_LANGUAGE = "en-IN"

# TTS voice presets per language (professional/formal voices from Bulbul v3)
VOICE_MAP = {
    "en-IN": "priya",
    "hi-IN": "priya",
    "ta-IN": "priya",
    "te-IN": "priya",
    "kn-IN": "priya",
    "ml-IN": "priya",
    "bn-IN": "priya",
    "gu-IN": "priya",
    "mr-IN": "priya",
    "pa-IN": "priya",
    "od-IN": "priya",
}


@dataclass
class STTResult:
    """Result from Sarvam Speech-to-Text."""
    transcript: str
    language_code: str  # detected or specified


@dataclass
class TTSResult:
    """Result from Sarvam Text-to-Speech."""
    audio_base64: str
    audio_format: str   # "mp3" / "wav"


class SarvamVoiceAdapter:
    """Client for Sarvam AI STT and TTS REST APIs."""

    def __init__(self):
        self.api_key = settings.SARVAM_API_KEY
        if not self.api_key:
            logger.warning("SARVAM_API_KEY is empty — voice agent will not work")

    def _headers_json(self) -> dict:
        return {
            "api-subscription-key": self.api_key,
            "Content-Type": "application/json",
        }

    def _headers_multipart(self) -> dict:
        return {
            "api-subscription-key": self.api_key,
        }

    async def speech_to_text(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        language_code: Optional[str] = None,
    ) -> STTResult:
        """
        Convert speech audio to text using Sarvam Saaras v3.

        Args:
            audio_bytes: Raw audio file bytes (WAV, MP3, WebM, etc.)
            filename:    Original filename (for content-type detection)
            language_code: BCP-47 code, or None for auto-detect
        """
        # Determine content type from extension
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "wav"
        mime_map = {
            "wav": "audio/wav",
            "mp3": "audio/mpeg",
            "webm": "audio/webm",
            "ogg": "audio/ogg",
            "m4a": "audio/mp4",
            "aac": "audio/aac",
            "flac": "audio/flac",
        }
        content_type = mime_map.get(ext, "audio/wav")

        data = {
            "model": "saaras:v3",
            "mode": "transcribe",
        }
        if language_code and language_code != "auto":
            data["language_code"] = language_code

        files = {
            "file": (filename, audio_bytes, content_type),
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{SARVAM_BASE}/speech-to-text",
                headers=self._headers_multipart(),
                data=data,
                files=files,
            )

        if resp.status_code != 200:
            logger.error("Sarvam STT failed [%s]: %s", resp.status_code, resp.text)
            raise RuntimeError(f"Sarvam STT error: {resp.status_code} — {resp.text}")

        body = resp.json()
        transcript = body.get("transcript", "")
        detected_lang = body.get("language_code", language_code or DEFAULT_LANGUAGE)

        logger.info("STT result: lang=%s, len=%d chars", detected_lang, len(transcript))
        return STTResult(transcript=transcript, language_code=detected_lang)

    async def text_to_speech(
        self,
        text: str,
        language_code: str = DEFAULT_LANGUAGE,
        speaker: Optional[str] = None,
        audio_format: str = "mp3",
    ) -> TTSResult:
        """
        Convert text to speech audio using Sarvam Bulbul v3.

        Args:
            text:          Text to speak (max 2500 chars)
            language_code: BCP-47 target language code
            speaker:       Voice ID (defaults to language preset)
            audio_format:  Output format — "mp3", "wav"

        Returns:
            TTSResult with base64-encoded audio
        """
        if len(text) > 2500:
            text = text[:2500]
            logger.warning("TTS text truncated to 2500 chars")

        voice = speaker or VOICE_MAP.get(language_code, "priya")

        payload = {
            "text": text,
            "target_language_code": language_code,
            "model": "bulbul:v3",
            "speaker": voice,
            "audio_format": audio_format,
            "pace": 1.0,
            "sample_rate": 22050,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{SARVAM_BASE}/text-to-speech",
                headers=self._headers_json(),
                json=payload,
            )

        if resp.status_code != 200:
            logger.error("Sarvam TTS failed [%s]: %s", resp.status_code, resp.text)
            raise RuntimeError(f"Sarvam TTS error: {resp.status_code} — {resp.text}")

        body = resp.json()
        audio_b64 = body.get("audios", [None])[0] or body.get("audio", "")

        logger.info("TTS result: lang=%s, format=%s", language_code, audio_format)
        return TTSResult(audio_base64=audio_b64, audio_format=audio_format)
