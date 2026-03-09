import asyncio
import logging
import os
from io import BytesIO
from pathlib import Path

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

from app.core.config import settings
from app.services.ticket_service import TicketService
from app.enums import TicketSource

# ── Ensure Google Cloud credentials are available as OS env var ────────────
# pydantic-settings reads the .env value but Google's SDK only checks os.environ
_BACKEND_DIR = Path(__file__).resolve().parents[2]  # backend/
if settings.GOOGLE_APPLICATION_CREDENTIALS and not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
    _cred_path = Path(settings.GOOGLE_APPLICATION_CREDENTIALS)
    if not _cred_path.is_absolute():
        _cred_path = _BACKEND_DIR / _cred_path
    if _cred_path.exists():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(_cred_path)

# Google Cloud STT / TTS
try:
    from google.cloud import speech, texttospeech
    GOOGLE_CLOUD_ENABLED = True
except ImportError:
    GOOGLE_CLOUD_ENABLED = False

logger = logging.getLogger(__name__)

# Conversation states
DESCRIPTION, LOCATION, PHOTO, PHONE, CONSENT = range(5)


def transcribe_voice_sync(audio_bytes: bytes) -> str:
    if not GOOGLE_CLOUD_ENABLED:
        return ""
    
    client = speech.SpeechClient()
    audio = speech.RecognitionAudio(content=audio_bytes)
    # Telegram sends voice notes usually as OGG_OPUS (sample rate can be 16k or 48k)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.OGG_OPUS,
        sample_rate_hertz=48000, 
        language_code="hi-IN",
        alternative_language_codes=["en-IN"],
    )
    
    response = client.recognize(config=config, audio=audio)
    
    transcript = ""
    for result in response.results:
        transcript += result.alternatives[0].transcript
        
    return transcript.strip()


def synthesize_speech_sync(text: str) -> bytes:
    if not GOOGLE_CLOUD_ENABLED:
        return b""
        
    client = texttospeech.TextToSpeechClient()
    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code="hi-IN",
        name="hi-IN-Neural2-B"
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.OGG_OPUS
    )
    
    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )
    return response.audio_content


# Background tasks for sync Google API calls
async def transcribe_voice(audio_bytes: bytes) -> str:
    return await asyncio.to_thread(transcribe_voice_sync, audio_bytes)

async def synthesize_speech(text: str) -> bytes:
    return await asyncio.to_thread(synthesize_speech_sync, text)


# --- Command Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🙏 Welcome to JanVedha Civic Bot!\n\n"
        "I can help you report civic issues. You can type or send a VOICE NOTE 🎤.\n\n"
        "Send /new to report a complaint.\n"
        "Send /track <ticket_code> to track."
    )
    await update.message.reply_text(msg)


async def track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please provide the ticket code. Example: /track JV-ABCD")
        return
        
    ticket_code = context.args[0].upper()
    from app.mongodb.models.ticket import TicketMongo
    ticket = await TicketMongo.find_one(TicketMongo.ticket_code == ticket_code)
    
    if not ticket:
        await update.message.reply_text(f"Ticket {ticket_code} not found.")
        return
        
    msg = (
        f"🎫 Ticket: {ticket.ticket_code}\n"
        f"📊 Status: {ticket.status}\n"
        f"🚨 Priority: {ticket.priority_label}\n"
        f"💡 AI Suggestion: {ticket.ai_suggestions[0] if ticket.ai_suggestions else 'None'}\n"
    )
    await update.message.reply_text(msg)


# --- Conversation Handlers ---

async def start_complaint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    msg = "📝 Please describe the civic issue. You can type it or hold the mic 🎤 to send a voice note!"
    await update.message.reply_text(msg)
    return DESCRIPTION


async def process_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.voice:
        voice_file = await update.message.voice.get_file()
        voice_bytes = await voice_file.download_as_bytearray()
        
        await update.message.reply_text("🎙️ Processing voice note...")
        try:
            transcript = await transcribe_voice(bytes(voice_bytes))
            if not transcript:
                await update.message.reply_text("Could not transcribe audio. Please type it.")
                return DESCRIPTION
            description = transcript
            context.user_data["wants_voice_reply"] = True
            await update.message.reply_text(f"📝 Transcribed: {description}")
        except Exception as e:
            logger.error(f"STT failed: {e}")
            await update.message.reply_text("Voice processing failed. Please type.")
            return DESCRIPTION
    else:
        description = update.message.text
        if len(description) < 10:
            await update.message.reply_text("Description too short. Please add details.")
            return DESCRIPTION
            
    context.user_data['description'] = description
    
    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("📍 Share Location", request_location=True)]], 
        one_time_keyboard=True, resize_keyboard=True
    )
    await update.message.reply_text(
        "📍 Where is the issue? Please share GPS or type address.", 
        reply_markup=keyboard
    )
    return LOCATION


async def process_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.location:
        lat = update.message.location.latitude
        lng = update.message.location.longitude
        context.user_data['lat'] = lat
        context.user_data['lng'] = lng
        context.user_data['location_text'] = f"{lat}, {lng}"
    else:
        context.user_data['location_text'] = update.message.text
            
    await update.message.reply_text(
        "📷 Send a photo of the issue, or type 'skip'.", 
        reply_markup=ReplyKeyboardRemove()
    )
    return PHOTO


async def process_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        context.user_data['photo_url'] = "telegram_photo_url_placeholder"
    
    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("📱 Share Phone Number", request_contact=True)]], 
        one_time_keyboard=True, resize_keyboard=True
    )
    await update.message.reply_text("📱 Please enter your 10-digit mobile number.", reply_markup=keyboard)
    return PHONE


async def process_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.contact:
        context.user_data['reporter_phone'] = update.message.contact.phone_number[-10:]
        context.user_data['reporter_name'] = update.message.contact.first_name
    else:
        context.user_data['reporter_phone'] = update.message.text[-10:]
        context.user_data['reporter_name'] = update.message.from_user.first_name
        
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, I consent", callback_data="consent_yes")],
        [InlineKeyboardButton("❌ No", callback_data="consent_no")]
    ])
    await update.message.reply_text(
        "🔒 Do you consent to share your contact information with the municipal authority?", 
        reply_markup=keyboard
    )
    return CONSENT


async def process_consent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "consent_no":
        await query.edit_message_text("❌ Complaint cancelled. Consent required.")
        context.user_data.clear()
        return ConversationHandler.END
        
    await query.edit_message_text("✅ Concent recorded. \n\n🚀 Submitting to JanVedha AI Pipeline...")
    
    try:
        data = context.user_data
        ticket = await TicketService.create_ticket(
            description=data.get('description', ''),
            location_text=data.get('location_text', ''),
            reporter_phone=data.get('reporter_phone', '0000000000'),
            consent_given=True,
            reporter_name=data.get('reporter_name'),
            photo_url=data.get('photo_url'),
            source=TicketSource.TELEGRAM,
            lat=data.get('lat'),
            lng=data.get('lng'),
        )
        
        success_msg = (
            f"✅ Complaint Registered via Telegram!\n\n"
            f"🎫 Ticket: {ticket.ticket_code}\n"
            f"🏛 Dept: {ticket.dept_id}\n"
            f"⚡ Priority: {ticket.priority_label}\n"
        )
        await query.message.reply_text(success_msg)
        
        # If user spoke to us originally, speak back!
        if data.get("wants_voice_reply") and GOOGLE_CLOUD_ENABLED:
            try:
                voice_msg = f"Aapki shikayat darj kar li gayi hai. Aapka ticket code hai {ticket.ticket_code}. Dhanyawaad."
                audio_bytes = await synthesize_speech(voice_msg)
                if audio_bytes:
                    await query.message.reply_voice(BytesIO(audio_bytes))
            except Exception as e:
                logger.error(f"TTS post-submission failed: {e}")

    except Exception as e:
        logger.exception("Failed to create ticket")
        await query.message.reply_text(f"❌ Failed to submit constraint. Ensure location and description are valid.")
        
    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Complaint cancelled.", reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()
    return ConversationHandler.END


# --- Application Setup ---

_bot_application = None

def get_bot_application() -> Application:
    global _bot_application
    if _bot_application is None and settings.TELEGRAM_BOT_TOKEN:
        _bot_application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
        
        _bot_application.add_handler(CommandHandler("start", start))
        _bot_application.add_handler(CommandHandler("track", track))
        
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("new", start_complaint)],
            states={
                DESCRIPTION: [MessageHandler(filters.TEXT | filters.VOICE, process_description)],
                LOCATION: [MessageHandler(filters.LOCATION | filters.TEXT, process_location)],
                PHOTO: [MessageHandler(filters.PHOTO | filters.TEXT, process_photo)],
                PHONE: [MessageHandler(filters.CONTACT | filters.TEXT, process_phone)],
                CONSENT: [CallbackQueryHandler(process_consent, pattern="^consent_yes|consent_no$")],
            },
            fallbacks=[CommandHandler("cancel", cancel)]
        )
        _bot_application.add_handler(conv_handler)
        
    return _bot_application
