from app.interfaces.ai_provider import AIProvider
from app.interfaces.storage_provider import StorageProvider
from app.interfaces.notification_provider import WhatsAppProvider, SMSProvider, EmailProvider
from app.interfaces.voice_provider import VoiceProvider
from app.interfaces.sentiment_provider import SentimentProvider
from app.interfaces.blockchain_provider import BlockchainProvider
from app.core.config import settings

def get_ai_provider() -> AIProvider:
    if settings.AI_PROVIDER == "gemini":
        from app.adapters.ai.gemini_adapter import GeminiAdapter
        return GeminiAdapter()
    elif settings.AI_PROVIDER == "openai":
        from app.adapters.ai.openai_adapter import OpenAIAdapter
        return OpenAIAdapter()
    raise ValueError(f"Unknown AI provider: {settings.AI_PROVIDER}")

def get_storage_provider() -> StorageProvider:
    if settings.STORAGE_PROVIDER == "minio":
        from app.adapters.storage.minio_adapter import MinIOAdapter
        return MinIOAdapter()
    elif settings.STORAGE_PROVIDER == "s3":
        from app.adapters.storage.s3_adapter import S3Adapter
        return S3Adapter()
    elif settings.STORAGE_PROVIDER == "local":
        from app.adapters.storage.local_adapter import LocalStorageAdapter
        return LocalStorageAdapter()
    raise ValueError(f"Unknown storage provider: {settings.STORAGE_PROVIDER}")

def get_whatsapp_provider() -> WhatsAppProvider:
    if settings.WHATSAPP_PROVIDER == "twilio":
        from app.adapters.notifications.twilio_whatsapp import TwilioWhatsAppAdapter
        return TwilioWhatsAppAdapter()
    raise ValueError(f"Unknown WhatsApp provider: {settings.WHATSAPP_PROVIDER}")

def get_sms_provider() -> SMSProvider:
    if settings.SMS_PROVIDER == "msg91":
        from app.adapters.notifications.msg91_sms import MSG91Adapter
        return MSG91Adapter()
    elif settings.SMS_PROVIDER == "twilio":
        from app.adapters.notifications.twilio_sms import TwilioSMSAdapter
        return TwilioSMSAdapter()
    raise ValueError(f"Unknown SMS provider: {settings.SMS_PROVIDER}")

def get_email_provider() -> EmailProvider:
    if settings.EMAIL_PROVIDER == "sendgrid":
        from app.adapters.notifications.sendgrid_email import SendGridAdapter
        return SendGridAdapter()
    raise ValueError(f"Unknown email provider: {settings.EMAIL_PROVIDER}")

def get_voice_provider() -> VoiceProvider:
    if settings.VOICE_PROVIDER == "vomyra":
        from app.adapters.voice.vomyra_adapter import VomyraAdapter
        return VomyraAdapter()
    elif settings.VOICE_PROVIDER == "twilio":
        from app.adapters.voice.twilio_voice_adapter import TwilioVoiceAdapter
        return TwilioVoiceAdapter()
    elif settings.VOICE_PROVIDER == "stub":
        from app.adapters.voice.stub_adapter import StubVoiceAdapter
        return StubVoiceAdapter()
    raise ValueError(f"Unknown voice provider: {settings.VOICE_PROVIDER}")

def get_sentiment_provider() -> SentimentProvider:
    if settings.SENTIMENT_PROVIDER == "huggingface":
        from app.adapters.sentiment.huggingface_adapter import HuggingFaceAdapter
        return HuggingFaceAdapter()
    raise ValueError(f"Unknown sentiment provider: {settings.SENTIMENT_PROVIDER}")

def get_blockchain_provider() -> BlockchainProvider:
    if settings.BLOCKCHAIN_PROVIDER == "polygon":
        from app.adapters.blockchain.polygon_adapter import PolygonAdapter
        return PolygonAdapter()
    elif settings.BLOCKCHAIN_PROVIDER == "stub":
        from app.adapters.blockchain.stub_adapter import StubBlockchainAdapter
        return StubBlockchainAdapter()
    raise ValueError(f"Unknown blockchain provider: {settings.BLOCKCHAIN_PROVIDER}")

def get_scraper_providers() -> list:
    providers = []
    for name in settings.ACTIVE_SCRAPERS:  # list from config
        if name == "reddit":
            from app.adapters.scrapers.reddit_adapter import RedditAdapter
            providers.append(RedditAdapter())
        elif name == "twitter":
            from app.adapters.scrapers.twitter_adapter import TwitterAdapter
            providers.append(TwitterAdapter())
    return providers
