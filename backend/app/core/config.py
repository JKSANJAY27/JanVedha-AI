from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Providers — change these to swap implementations
    AI_PROVIDER: str = "gemini"
    STORAGE_PROVIDER: str = "minio"        # minio | s3 | local
    WHATSAPP_PROVIDER: str = "twilio"
    SMS_PROVIDER: str = "msg91"
    EMAIL_PROVIDER: str = "sendgrid"
    VOICE_PROVIDER: str = "stub"           # stub until Vomyra ready
    SENTIMENT_PROVIDER: str = "huggingface"
    BLOCKCHAIN_PROVIDER: str = "stub"      # stub until blockchain ready
    ACTIVE_SCRAPERS: list[str] = []        # empty until scrapers ready

    # AI keys
    GEMINI_API_KEY: str = ""
    NVIDIA_API_KEY: str = ""

    # Comms keys
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""
    TWILIO_WHATSAPP_NUMBER: str = ""
    MSG91_API_KEY: str = ""
    SENDGRID_API_KEY: str = ""
    TELEGRAM_BOT_TOKEN: str = ""

    # Voice
    VOMYRA_API_KEY: str = ""
    SARVAM_API_KEY: str = ""

    # Storage
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = ""
    MINIO_SECRET_KEY: str = ""
    MINIO_BUCKET: str = "civicai"
    MINIO_USE_SSL: bool = False
    
    # GCP
    GOOGLE_APPLICATION_CREDENTIALS: str = ""

    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_S3_BUCKET: str = ""
    AWS_REGION: str = "ap-south-1"

    # Databases
    DATABASE_URL: str = "postgresql+asyncpg://civicai:civicai_local@localhost:5432/civicai"
    MONGODB_URI: str = "mongodb://localhost:27017/civicai"
    REDIS_URL: str = "redis://localhost:6379"

    # ── Social Media Scraping (Scrapify integration) ──────────────────────────
    # Apify — cloud-based social media scraping
    APIFY_API_TOKEN: str = ""
    # Reddit (PRAW) — https://www.reddit.com/prefs/apps
    REDDIT_CLIENT_ID: str = ""
    REDDIT_CLIENT_SECRET: str = ""
    REDDIT_USER_AGENT: str = "JanVedhaAI/1.0"
    # YouTube Data API v3
    YOUTUBE_API_KEY: str = ""
    # News APIs
    GNEWS_API_KEY: str = "34f5754bd852334a1bc6b1a6e1970f44"
    CURRENTS_API_KEY: str = "yHyeCtUokXL6t6-Evcw4zuJ_bXGfJ4xt6dQcmgzOqqhLou39"
    NEWSDATA_API_KEY: str = "pub_ea435c80fd684848b16cb1ad2fc1c469"
    # City scope for scrapers
    DEMO_CITY: str = "Chennai"
    # Scrape interval (minutes)
    SCRAPE_INTERVAL_MINUTES: int = 60

    # Maps
    GOOGLE_MAPS_API_KEY: str = ""

    # Blockchain
    POLYGON_RPC_URL: str = ""
    POLYGON_PRIVATE_KEY: str = ""
    POLYGON_CONTRACT_ADDRESS: str = ""

    # Auth
    JWT_SECRET_KEY: str = "change_this_in_production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480

    # App
    ENVIRONMENT: str = "development"
    CITY_NAME: str = "Chennai"

    class Config:
        env_file = ".env"

settings = Settings()
