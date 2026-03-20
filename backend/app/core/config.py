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
    NEWS_API_KEY: str = "2082e154a8944e1988b2c6015c6b7ddc"  # NewsAPI.org
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
    APP_NAME: str = "JanVedhaAI"
    APP_ENV: str = "development"
    APP_PORT: int = 8000
    APP_LOG_LEVEL: str = "INFO"
    ENVIRONMENT: str = "development"
    CITY_NAME: str = "Chennai"

    # Social Media extras
    TWITTER_ACCOUNTS: str = ""
    TWITTER_AUTH_TOKEN: str = ""
    TWITTER_CT0: str = ""
    INSTAGRAM_USERNAME: str = ""
    INSTAGRAM_PASSWORD: str = ""
    INSTAGRAM_SESSION_ID: str = ""
    WEBHOOK_URL: str = ""
    WEBHOOK_SECRET: str = ""

    # Langfuse
    LANGFUSE_HOST: str = "http://localhost:4000"
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""

    # RAG Configuration
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    CHROMA_SCHEMES_COLLECTION: str = "scheme_documents"
    RAG_TOP_K: int = 5
    RAG_RERANKER_TOP_K: int = 3
    RAG_CITATION_THRESHOLD: float = 0.1

    class Config:
        env_file = ".env"

        extra = "ignore"

settings = Settings()
