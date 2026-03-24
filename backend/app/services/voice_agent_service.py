"""
Voice Agent Service — orchestrates STT → Gemini → TTS for councillor voice queries.

Two modes:
  1. ask(audio, user) — open-ended voice query
  2. briefing(user, language) — one-tap morning briefing
"""
import logging
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass

from app.core.config import settings
from app.adapters.voice.sarvam_adapter import (
    SarvamVoiceAdapter,
    STTResult,
    TTSResult,
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
)
from app.mongodb.models.ticket import TicketMongo
from app.mongodb.models.user import UserMongo
from app.enums import TicketStatus

logger = logging.getLogger("voice_agent")

_sarvam: Optional[SarvamVoiceAdapter] = None


def _get_sarvam() -> SarvamVoiceAdapter:
    global _sarvam
    if _sarvam is None:
        _sarvam = SarvamVoiceAdapter()
    return _sarvam


@dataclass
class VoiceAgentResponse:
    """Complete response from the voice agent."""
    transcript: str          # what the user said (STT output)
    response_text: str       # what the agent says back
    audio_base64: str        # TTS audio (base64)
    audio_format: str        # "mp3" / "wav"
    language: str            # language used


# ── Ward Data Aggregator ──────────────────────────────────────────────────────

async def _build_ward_context(ward_id: int) -> dict:
    """
    Aggregate ward data from MongoDB for Gemini context.
    Reuses the same queries as councillor.py and analytics.py.
    """
    now = datetime.utcnow()

    # All ward tickets
    all_tickets = await TicketMongo.find(
        TicketMongo.ward_id == ward_id
    ).to_list()

    if not all_tickets:
        return {
            "ward_id": ward_id,
            "total": 0,
            "open": 0,
            "closed": 0,
            "overdue": 0,
            "resolution_rate": "0%",
            "departments": {},
            "top_issues": [],
            "overdue_tickets": [],
            "briefing_cached": None,
        }

    closed = [t for t in all_tickets if t.status in {TicketStatus.CLOSED}]
    open_tickets = [t for t in all_tickets if t.status not in {TicketStatus.CLOSED, TicketStatus.REJECTED}]
    overdue = [t for t in open_tickets if t.sla_deadline and t.sla_deadline < now]

    # Department breakdown
    dept_map: dict = {}
    for t in all_tickets:
        d = t.dept_id
        if d not in dept_map:
            dept_map[d] = {"open": 0, "closed": 0, "overdue": 0}
        if t.status in {TicketStatus.CLOSED}:
            dept_map[d]["closed"] += 1
        elif t.status not in {TicketStatus.REJECTED}:
            dept_map[d]["open"] += 1
            if t.sla_deadline and t.sla_deadline < now:
                dept_map[d]["overdue"] += 1

    # Top issue categories
    cat_count: dict = {}
    for t in all_tickets:
        cat = t.issue_category or "General"
        cat_count[cat] = cat_count.get(cat, 0) + 1
    top_issues = sorted(cat_count.items(), key=lambda x: x[1], reverse=True)[:5]

    # Top 3 most overdue tickets
    overdue_sorted = sorted(overdue, key=lambda t: t.sla_deadline or now)
    top_overdue = [
        {
            "ticket_code": t.ticket_code,
            "category": t.issue_category or "General",
            "dept": t.dept_id,
            "days_overdue": (now - t.sla_deadline).days if t.sla_deadline else 0,
        }
        for t in overdue_sorted[:3]
    ]

    # Recent 24h new tickets
    yesterday = now - timedelta(days=1)
    new_today = sum(1 for t in all_tickets if t.created_at and t.created_at >= yesterday)

    # Try to get cached intelligence briefing
    briefing_text = None
    try:
        from app.mongodb.models.ward_intelligence_cache import WardIntelligenceCache
        cached = await WardIntelligenceCache.find_one(
            WardIntelligenceCache.ward_id == ward_id,
            WardIntelligenceCache.cache_type == "briefing",
        )
        if cached and cached.briefing:
            briefing_text = cached.briefing
    except Exception:
        pass

    total = len(all_tickets)
    return {
        "ward_id": ward_id,
        "total": total,
        "open": len(open_tickets),
        "closed": len(closed),
        "overdue": len(overdue),
        "resolution_rate": f"{(len(closed)/total*100):.1f}%" if total > 0 else "0%",
        "new_today": new_today,
        "departments": dept_map,
        "top_issues": [{"category": cat, "count": cnt} for cat, cnt in top_issues],
        "overdue_tickets": top_overdue,
        "briefing_cached": briefing_text,
    }


# ── Gemini Narration ─────────────────────────────────────────────────────────

async def _gemini_voice_response(prompt: str) -> str:
    """Call Gemini to generate a spoken-style response."""
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.4,
        )
        resp = await llm.ainvoke([("user", prompt)])
        return resp.content.strip()
    except Exception as e:
        logger.error("Gemini voice call failed: %s", e)
        return "I'm having trouble generating a response right now. Please try again in a moment."


# ── Public API ────────────────────────────────────────────────────────────────

async def handle_voice_query(
    audio_bytes: bytes,
    filename: str,
    user: UserMongo,
    language_override: Optional[str] = None,
) -> VoiceAgentResponse:
    """
    Full voice query pipeline: STT → context → Gemini → TTS.
    """
    sarvam = _get_sarvam()
    ward_id = user.ward_id

    # 1. Speech-to-Text
    stt_result: STTResult = await sarvam.speech_to_text(
        audio_bytes, filename, language_code=language_override
    )
    transcript = stt_result.transcript
    detected_lang = stt_result.language_code or DEFAULT_LANGUAGE

    # Use override language for TTS if provided, else use detected
    tts_language = language_override or detected_lang
    if tts_language not in SUPPORTED_LANGUAGES:
        tts_language = DEFAULT_LANGUAGE

    logger.info("Voice query from %s (ward %s): '%s' [lang=%s]",
                user.name, ward_id, transcript[:80], tts_language)

    # 2. Build ward context
    ward_data = await _build_ward_context(ward_id) if ward_id else {}

    # 3. Ask Gemini — respond in the user's selected language
    lang_name = SUPPORTED_LANGUAGES.get(tts_language, "English (India)")
    if tts_language != "en-IN":
        lang_instruction = (
            f"CRITICAL: You MUST write your ENTIRE response in {lang_name} language using {lang_name} script. "
            f"Do NOT write in English. Every single word of your response must be in {lang_name}. "
            f"Numbers can remain as digits (1, 2, 3) but all words must be in {lang_name}."
        )
    else:
        lang_instruction = "Respond in English."

    prompt = f"""You are a professional ward intelligence assistant for the Chennai Municipal Corporation.
You are talking to Councillor {user.name}, responsible for Ward {ward_id}.

Current Ward Status:
- Total tickets: {ward_data.get('total', 0)}
- Open: {ward_data.get('open', 0)}
- Closed: {ward_data.get('closed', 0)}
- Overdue: {ward_data.get('overdue', 0)}
- Resolution rate: {ward_data.get('resolution_rate', 'N/A')}
- New today: {ward_data.get('new_today', 0)}
- Top issues: {', '.join(f"{i['category']} ({i['count']})" for i in ward_data.get('top_issues', []))}
- Departments with overdue: {', '.join(f"{d}: {s['overdue']} overdue" for d, s in ward_data.get('departments', {}).items() if s.get('overdue', 0) > 0)}
- Most overdue tickets: {', '.join(f"{t['ticket_code']} ({t['category']}, {t['days_overdue']} days overdue)" for t in ward_data.get('overdue_tickets', []))}

The councillor asked (via voice): "{transcript}"

RULES:
1. {lang_instruction}
2. Respond in 3-5 concise spoken sentences — this will be read aloud via TTS.
3. Use numbers and specifics from the data above. Do NOT make up data.
4. Be professional but warm. Address them as "Councillor" or by name.
5. Do NOT use markdown, bullet points, or formatting — plain spoken text only.
6. If the question is outside your data, say so honestly and suggest what you can help with.
"""

    response_text = await _gemini_voice_response(prompt)

    # 4. Text-to-Speech
    tts_result: TTSResult = await sarvam.text_to_speech(
        response_text, language_code=tts_language
    )

    return VoiceAgentResponse(
        transcript=transcript,
        response_text=response_text,
        audio_base64=tts_result.audio_base64,
        audio_format=tts_result.audio_format,
        language=tts_language,
    )


async def generate_morning_briefing(
    user: UserMongo,
    language: str = DEFAULT_LANGUAGE,
) -> VoiceAgentResponse:
    """
    Generate a spoken morning briefing for the councillor.
    """
    sarvam = _get_sarvam()
    ward_id = user.ward_id

    # Build context
    ward_data = await _build_ward_context(ward_id) if ward_id else {}

    # Check if we have a cached AI briefing
    cached_briefing = ward_data.get("briefing_cached")

    lang_name = SUPPORTED_LANGUAGES.get(language, "English (India)")
    if language != "en-IN":
        lang_instruction = (
            f"CRITICAL: You MUST write your ENTIRE briefing in {lang_name} language using {lang_name} script. "
            f"Do NOT write in English. Every single word must be in {lang_name}. "
            f"Numbers can remain as digits (1, 2, 3) but all words must be in {lang_name}."
        )
    else:
        lang_instruction = "Respond in English."

    prompt = f"""You are generating a 30-second spoken morning briefing for Councillor {user.name} of Ward {ward_id}, Chennai Municipal Corporation.

Ward Data:
- Total tickets: {ward_data.get('total', 0)}
- Open: {ward_data.get('open', 0)} | Closed: {ward_data.get('closed', 0)} | Overdue: {ward_data.get('overdue', 0)}
- Resolution rate: {ward_data.get('resolution_rate', 'N/A')}
- New complaints in last 24 hours: {ward_data.get('new_today', 0)}
- Top issues: {', '.join(f"{i['category']} ({i['count']})" for i in ward_data.get('top_issues', []))}
- Most overdue: {', '.join(f"{t['ticket_code']} ({t['category']}, {t['days_overdue']} days overdue)" for t in ward_data.get('overdue_tickets', []))}
{f"- Previous AI briefing (for context): {cached_briefing[:300]}" if cached_briefing else ""}

RULES:
1. {lang_instruction}
2. Give a 5-sentence spoken briefing covering: new complaints, overdue urgency, top issue, dept performance, one recommended action.
3. Use specific numbers. Be direct and actionable.
4. Plain spoken text only — NO markdown, headers, or bullet points.
5. Keep it under 200 words so TTS can read it in ~30 seconds.
"""

    briefing_text = await _gemini_voice_response(prompt)

    # TTS
    if language not in SUPPORTED_LANGUAGES:
        language = DEFAULT_LANGUAGE

    tts_result: TTSResult = await sarvam.text_to_speech(
        briefing_text, language_code=language
    )

    return VoiceAgentResponse(
        transcript="",
        response_text=briefing_text,
        audio_base64=tts_result.audio_base64,
        audio_format=tts_result.audio_format,
        language=language,
    )
