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

    # Comms keys
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""
    TWILIO_WHATSAPP_NUMBER: str = ""
    MSG91_API_KEY: str = ""
    SENDGRID_API_KEY: str = ""

    # Voice
    VOMYRA_API_KEY: str = ""
    SARVAM_API_KEY: str = ""

    # Storage
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = ""
    MINIO_SECRET_KEY: str = ""
    MINIO_BUCKET: str = "civicai"
    MINIO_USE_SSL: bool = False
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_S3_BUCKET: str = ""
    AWS_REGION: str = "ap-south-1"

    # Databases
    DATABASE_URL: str = "postgresql+asyncpg://civicai:civicai_local@localhost:5432/civicai"
    MONGODB_URI: str = "mongodb://localhost:27017/civicai"
    REDIS_URL: str = "redis://localhost:6379"

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
