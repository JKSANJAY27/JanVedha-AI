This requires very careful thinking. The key principle here is the **Adapter Pattern** — your core never knows which specific library or service is being used. It only knows the interface. Swapping Twilio for something else means changing one file, nothing else.

Let me lay this out completely.

---

## The Core Principle: Interfaces vs Implementations

Every external service in this project lives behind an abstract interface. Your business logic depends on the interface. The concrete implementation (Twilio, Gemini, MinIO, PRAW) is plugged in at startup via config. This is the architectural decision that gives you the flexibility you're asking for.

```
backend/app/
├── interfaces/        ← Abstract contracts. NEVER change these after Phase 0.
├── adapters/          ← Concrete implementations. Swap freely anytime.
├── core/              ← Business logic. Uses interfaces only. Never imports adapters.
├── api/               ← FastAPI routes. Thin layer. No business logic here.
├── models/            ← SQLAlchemy DB models. Core. Never changes.
└── services/          ← Orchestration. Calls core + interfaces.
```

The rule: `core/` and `api/` import from `interfaces/`. They never import from `adapters/`. Ever.

---

## Phase 0 — The Unchangeable Foundation

### *Everyone is blocked until this is done. One person does this. Takes 1–2 days.*

This phase produces the skeleton that every other phase builds on top of. After Phase 0 is committed, no one ever touches these files without a full team discussion. This is the bedrock.

---

### 0A — Repo & Local Environment

```
civicai/
├── backend/
├── frontend/
├── infra/
│   └── docker-compose.yml
├── .gitignore
├── .env.example
└── README.md
```

```yaml
# infra/docker-compose.yml — the only infra file you need locally
services:
  postgres:
    image: postgis/postgis:15-3.4
    ports: ["5432:5432"]
    environment:
      POSTGRES_USER: civicai
      POSTGRES_PASSWORD: civicai_local
      POSTGRES_DB: civicai
    volumes: [postgres_data:/var/lib/postgresql/data]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  mongodb:
    image: mongo:7
    ports: ["27017:27017"]
    volumes: [mongo_data:/data/db]

volumes:
  postgres_data:
  mongo_data:
```

```bash
# .gitignore — critical
.env
.env.local
__pycache__/
*.pyc
node_modules/
.next/
*.pkl          # ML model files
uploads/       # local file uploads
```

---

### 0B — Database Schema (PostgreSQL)

All tables defined here. Migrations written with Alembic. This schema does not change after Phase 0 except through proper migration files. Adding a column = new migration file. Dropping a column = team discussion first.

```python
# backend/app/models/ticket.py
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey, Numeric, Enum
from sqlalchemy.dialects.postgresql import JSONB, INET
from geoalchemy2 import Geography
from .base import Base
import enum

class TicketSource(str, enum.Enum):
    VOICE_CALL = "VOICE_CALL"
    WEB_PORTAL = "WEB_PORTAL"
    WHATSAPP = "WHATSAPP"
    SOCIAL_MEDIA = "SOCIAL_MEDIA"
    NEWS = "NEWS"
    CPGRAMS = "CPGRAMS"

class TicketStatus(str, enum.Enum):
    OPEN = "OPEN"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    CLOSED = "CLOSED"
    CLOSED_UNVERIFIED = "CLOSED_UNVERIFIED"
    REOPENED = "REOPENED"
    REJECTED = "REJECTED"

class PriorityLabel(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class Ticket(Base):
    __tablename__ = "tickets"
    id = Column(Integer, primary_key=True)
    ticket_code = Column(String(20), unique=True, nullable=False)
    source = Column(String(20), nullable=False)
    source_url = Column(Text)
    description = Column(Text, nullable=False)
    dept_id = Column(String(5), ForeignKey("departments.dept_id"), nullable=False)
    ward_id = Column(Integer)
    zone_id = Column(Integer)
    coordinates = Column(Geography(geometry_type='POINT', srid=4326))
    photo_url = Column(Text)
    before_photo_url = Column(Text)
    after_photo_url = Column(Text)
    reporter_phone = Column(String(15))
    reporter_name = Column(String(100))
    consent_given = Column(Boolean, default=False)
    consent_timestamp = Column(DateTime)
    language_detected = Column(String(20))
    ai_confidence = Column(Float)
    priority_score = Column(Float, default=0.0)
    priority_label = Column(String(10))
    status = Column(String(30), default="OPEN")
    report_count = Column(Integer, default=1)
    requires_human_review = Column(Boolean, default=False)
    estimated_cost = Column(Numeric(12, 2))
    citizen_satisfaction = Column(Integer)
    sla_deadline = Column(DateTime)
    social_media_mentions = Column(Integer, default=0)
    assigned_officer_id = Column(Integer, ForeignKey("users.id"))
    blockchain_hash = Column(String(66))
    created_at = Column(DateTime, server_default="NOW()")
    assigned_at = Column(DateTime)
    resolved_at = Column(DateTime)
```

```python
# backend/app/models/department.py
class Department(Base):
    __tablename__ = "departments"
    dept_id = Column(String(5), primary_key=True)
    dept_name = Column(String(100), nullable=False)
    handles = Column(Text)
    sla_days = Column(Integer, nullable=False)
    is_external = Column(Boolean, default=False)
    parent_body = Column(String(100))
    escalation_role = Column(String(50))

# backend/app/models/user.py
class UserRole(str, enum.Enum):
    WARD_OFFICER = "WARD_OFFICER"
    ZONAL_OFFICER = "ZONAL_OFFICER"
    DEPT_HEAD = "DEPT_HEAD"
    COMMISSIONER = "COMMISSIONER"
    COUNCILLOR = "COUNCILLOR"
    SUPER_ADMIN = "SUPER_ADMIN"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    phone = Column(String(15), unique=True)
    email = Column(String(100), unique=True)
    password_hash = Column(String(255))
    role = Column(String(30), nullable=False)
    ward_id = Column(Integer)
    zone_id = Column(Integer)
    dept_id = Column(String(5), ForeignKey("departments.dept_id"))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default="NOW()")

# backend/app/models/audit_log.py
class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"))
    action = Column(String(100), nullable=False)
    old_value = Column(JSONB)
    new_value = Column(JSONB)
    actor_id = Column(Integer, ForeignKey("users.id"))
    actor_role = Column(String(50))
    ip_address = Column(INET)
    created_at = Column(DateTime, server_default="NOW()")
    # NO update. NO delete. Ever.

# backend/app/models/ward_dept_officer.py
class WardDeptOfficer(Base):
    __tablename__ = "ward_dept_officers"
    ward_id = Column(Integer, primary_key=True)
    dept_id = Column(String(5), ForeignKey("departments.dept_id"), primary_key=True)
    officer_id = Column(Integer, ForeignKey("users.id"))

# backend/app/models/announcement.py
class Announcement(Base):
    __tablename__ = "announcements"
    id = Column(Integer, primary_key=True)
    title = Column(String(200))
    body = Column(Text, nullable=False)
    drafted_by = Column(Integer, ForeignKey("users.id"))
    approved_by = Column(Integer, ForeignKey("users.id"))
    approved = Column(Boolean, default=False)
    related_ticket_id = Column(Integer, ForeignKey("tickets.id"))
    announcement_type = Column(String(50))
    created_at = Column(DateTime, server_default="NOW()")
    published_at = Column(DateTime)

# backend/app/models/ward_prediction.py
class WardPrediction(Base):
    __tablename__ = "ward_predictions"
    id = Column(Integer, primary_key=True)
    ward_id = Column(Integer, nullable=False)
    current_score = Column(Float)
    predicted_next_month_score = Column(Float)
    risk_level = Column(String(20))
    ai_recommendation = Column(Text)
    computed_at = Column(DateTime, server_default="NOW()")
```

---

### 0C — All Abstract Interfaces

These are the contracts. Every pluggable service must implement one of these. The rest of the codebase imports only these, never the concrete adapters.

```python
# backend/app/interfaces/ai_provider.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ClassificationResult:
    dept_id: str
    dept_name: str
    issue_summary: str
    location_extracted: str
    language_detected: str
    confidence: float
    needs_clarification: bool
    clarification_question: str | None = None
    requires_human_review: bool = False

@dataclass
class VisionResult:
    work_completed: bool
    is_genuine_fix: bool
    confidence: float
    explanation: str
    requires_human_review: bool

@dataclass
class DraftResult:
    content: str
    language: str

class AIProvider(ABC):

    @abstractmethod
    async def classify_complaint(
        self, text: str, image_url: str | None = None
    ) -> ClassificationResult:
        """
        Classify a complaint into a department.
        Must return requires_human_review=True if confidence < 0.75.
        Must never raise — return low-confidence result on failure.
        """
        pass

    @abstractmethod
    async def verify_work_completion(
        self, before_url: str, after_url: str, issue_type: str
    ) -> VisionResult:
        """
        Compare before/after photos to verify work is genuinely done.
        Must return requires_human_review=True if confidence < 0.85.
        """
        pass

    @abstractmethod
    async def draft_communication(
        self, context: dict, communication_type: str, language: str
    ) -> DraftResult:
        """
        Draft a rebuttal, announcement, or recommendation.
        Output is always a DRAFT. Never auto-published.
        """
        pass

    @abstractmethod
    async def generate_ward_recommendation(
        self, ward_stats: dict, risk_level: str
    ) -> str:
        """Generate a strategic recommendation for a ward."""
        pass
```

```python
# backend/app/interfaces/storage_provider.py
from abc import ABC, abstractmethod

class StorageProvider(ABC):

    @abstractmethod
    async def upload_file(
        self,
        file_bytes: bytes,
        destination_path: str,
        content_type: str = "image/jpeg"
    ) -> str:
        """
        Upload file. Return the public-accessible URL.
        destination_path example: "before_photos/ticket_123/before.jpg"
        """
        pass

    @abstractmethod
    async def get_presigned_upload_url(
        self, destination_path: str, content_type: str, expires_in_seconds: int = 300
    ) -> dict:
        """
        Return a presigned URL for direct browser-to-storage upload.
        Returns: { "url": str, "fields": dict } (S3-style) or { "url": str } (direct PUT)
        """
        pass

    @abstractmethod
    async def get_file_url(self, file_path: str) -> str:
        """Return the CDN/public URL for a stored file."""
        pass

    @abstractmethod
    async def delete_file(self, file_path: str) -> bool:
        """Delete a file. Returns True on success."""
        pass
```

```python
# backend/app/interfaces/notification_provider.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class WhatsAppMessage:
    to_phone: str          # with country code: +919876543210
    body: str
    template_name: str | None = None
    template_params: list | None = None

@dataclass
class SMSMessage:
    to_phone: str
    body: str

@dataclass
class EmailMessage:
    to_email: str
    subject: str
    html_body: str
    attachment_url: str | None = None
    attachment_name: str | None = None

@dataclass
class NotificationResult:
    success: bool
    message_id: str | None = None
    error: str | None = None

class WhatsAppProvider(ABC):
    @abstractmethod
    async def send_message(self, message: WhatsAppMessage) -> NotificationResult:
        pass

class SMSProvider(ABC):
    @abstractmethod
    async def send_message(self, message: SMSMessage) -> NotificationResult:
        pass

class EmailProvider(ABC):
    @abstractmethod
    async def send_email(self, message: EmailMessage) -> NotificationResult:
        pass
```

```python
# backend/app/interfaces/voice_provider.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class VoiceComplaintData:
    """Structured data extracted from a voice call."""
    raw_transcript: str
    language_detected: str
    location_text: str
    issue_description: str
    severity_signals: list[str]  # safety keywords detected
    caller_phone: str
    call_id: str

@dataclass
class IVRCallRequest:
    to_phone: str
    ticket_code: str
    issue_summary: str
    language: str

@dataclass
class IVRResponse:
    ticket_code: str
    digit_pressed: str   # "1" fixed | "2" partial | "3" not fixed | "timeout"
    call_id: str

class VoiceProvider(ABC):

    @abstractmethod
    async def handle_inbound_call(self, call_data: dict) -> VoiceComplaintData:
        """
        Handle an inbound citizen complaint call.
        Conduct multilingual conversation, extract structured data, return it.
        """
        pass

    @abstractmethod
    async def make_ivr_verification_call(self, request: IVRCallRequest) -> str:
        """
        Make an outbound IVR call to citizen for complaint verification.
        Returns call_id. Result comes via webhook to /api/webhooks/ivr/callback.
        """
        pass
```

```python
# backend/app/interfaces/scraper_provider.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ScrapedPost:
    """
    Anonymised scraped post. NO username, NO profile info. Ever.
    Only issue content + location hint + source traceability.
    """
    platform: str        # REDDIT | TWITTER | YOUTUBE | NEWS
    post_id: str         # platform-specific ID (for deduplication)
    text: str            # issue description text only
    location_hint: str   # location text if present in post
    source_url: str      # direct URL to original post
    scraped_at: datetime

class ScraperProvider(ABC):

    @abstractmethod
    async def scrape_recent(
        self, keywords: list[str], city: str, limit: int = 50
    ) -> list[ScrapedPost]:
        """
        Scrape public posts matching keywords for a city.
        Must strip all PII before returning.
        Must check post_id against DB before returning (deduplication).
        """
        pass
```

```python
# backend/app/interfaces/sentiment_provider.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class SentimentResult:
    positive_pct: float
    negative_pct: float
    neutral_pct: float
    total_analysed: int
    top_negative_keywords: list[str]

class SentimentProvider(ABC):
    @abstractmethod
    async def analyze(self, texts: list[str]) -> SentimentResult:
        pass
```

```python
# backend/app/interfaces/blockchain_provider.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class BlockchainRecord:
    hash: str
    transaction_id: str | None
    block_number: int | None
    recorded_at: str

class BlockchainProvider(ABC):
    @abstractmethod
    async def record_hash(self, data_hash: str, event_type: str) -> BlockchainRecord:
        """Write a hash to the blockchain. Returns transaction reference."""
        pass

    @abstractmethod
    async def verify_hash(self, data_hash: str) -> bool:
        """Verify a hash exists on chain."""
        pass
```

---

### 0D — Dependency Injection Container

This is how you swap providers. Change one line in config. Nothing else changes.

```python
# backend/app/core/container.py
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
```

```python
# backend/app/core/config.py
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
```

---

### 0E — All TypeScript Types (Frontend)

```typescript
// frontend/types/index.ts
// All API response shapes. Strict typing. No any.

export type TicketStatus =
  | "OPEN" | "ASSIGNED" | "IN_PROGRESS" | "PENDING_VERIFICATION"
  | "CLOSED" | "CLOSED_UNVERIFIED" | "REOPENED" | "REJECTED"

export type PriorityLabel = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"

export type UserRole =
  | "WARD_OFFICER" | "ZONAL_OFFICER" | "DEPT_HEAD"
  | "COMMISSIONER" | "COUNCILLOR" | "SUPER_ADMIN"

export type DeptId =
  | "D01" | "D02" | "D03" | "D04" | "D05" | "D06" | "D07"
  | "D08" | "D09" | "D10" | "D11" | "D12" | "D13" | "D14"

export interface Ticket {
  id: number
  ticket_code: string
  source: string
  description: string
  dept_id: DeptId
  dept_name: string
  ward_id: number
  ward_name: string
  priority_score: number
  priority_label: PriorityLabel
  status: TicketStatus
  ai_confidence: number
  reporter_phone?: string
  photo_url?: string
  before_photo_url?: string
  after_photo_url?: string
  language_detected: string
  requires_human_review: boolean
  sla_deadline: string         // ISO datetime
  created_at: string
  assigned_at?: string
  resolved_at?: string
  assigned_officer_name?: string
  report_count: number
}

export interface AuditEvent {
  id: number
  action: string
  old_value?: Record<string, unknown>
  new_value?: Record<string, unknown>
  actor_role: string
  created_at: string
}

export interface Department {
  dept_id: DeptId
  dept_name: string
  handles: string
  sla_days: number
  is_external: boolean
}

export interface WardStats {
  ward_id: number
  ward_name: string
  score: number
  rank: number
  sla_compliance_pct: number
  avg_resolution_days: number
  total_tickets_month: number
}

export interface CityStats {
  total_tickets: number
  resolved_pct: number
  avg_resolution_hours: number
  active_critical: number
  active_high: number
  last_updated: string
}

export interface ClassificationPreview {
  dept_id: DeptId
  dept_name: string
  issue_summary: string
  confidence: number
  needs_clarification: boolean
  clarification_question?: string
}

export interface ComplaintFormData {
  description: string
  location_text: string
  lat?: number
  lng?: number
  photo_base64?: string
  reporter_phone: string
  reporter_name?: string
  language?: string
  consent_given: true          // literal true — not optional
}

export interface SubmitComplaintResponse {
  ticket_code: string
  status: TicketStatus
  sla_deadline: string
  dept_name: string
  message: string
}

export interface OfficerUser {
  id: number
  name: string
  role: UserRole
  ward_id?: number
  zone_id?: number
  dept_id?: DeptId
  access_token: string
}

export interface SentimentSnapshot {
  ward_id: number
  positive_pct: number
  negative_pct: number
  neutral_pct: number
  total_posts: number
  spike_alert: boolean
  snapshot_at: string
}

export interface MisinformationFlag {
  id: string
  platform: string
  post_url: string
  claim_text: string
  evidence_tickets: number[]
  evidence_summary: string
  draft_rebuttal: string
  flagged_at: string
  status: "PENDING_REVIEW" | "APPROVED" | "DISMISSED"
}

export interface WardPrediction {
  ward_id: number
  ward_name: string
  current_score: number
  predicted_next_month_score: number
  risk_level: "HIGH_RISK" | "MODERATE_RISK" | "LOW_RISK"
  ai_recommendation: string
  computed_at: string
}

export interface ApiError {
  error: string
  message: string
  detail?: Record<string, unknown>
}
```

---

### 0F — FastAPI App Skeleton With Stub Routes

Every route defined here returns mock data. Frontend can build against this immediately without waiting for real implementations.

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import public, auth, officer, webhooks
from app.core.config import settings

app = FastAPI(title="CivicAI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(public.router, prefix="/api/public", tags=["public"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(officer.router, prefix="/api/officer", tags=["officer"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["webhooks"])

@app.get("/api/health")
async def health():
    return {"status": "ok", "environment": settings.ENVIRONMENT}
```

```python
# backend/app/api/public.py — stub responses, real shape
from fastapi import APIRouter

router = APIRouter()

@router.get("/stats")
async def get_stats():
    # Stub. Phase 1 replaces this with real DB query.
    return {
        "total_tickets": 0,
        "resolved_pct": 0.0,
        "avg_resolution_hours": 0.0,
        "active_critical": 0,
        "active_high": 0,
        "last_updated": "2025-01-01T00:00:00Z"
    }

@router.get("/wards/leaderboard")
async def get_leaderboard():
    return []

@router.get("/heatmap")
async def get_heatmap():
    return []

# ... all other public routes stubbed with correct return shapes
```

---

### 0G — Core Business Logic (Pure Python — No External Dependencies)

These functions never change regardless of what providers you use.

```python
# backend/app/core/priority.py

SEVERITY_MAP = {
    "street_light_out": 15, "multiple_lights_out": 22,
    "electrical_spark_hazard": 30,
    "small_pothole": 12, "large_pothole": 20,
    "road_collapse": 28, "bridge_crack": 30,
    "low_pressure": 14, "no_water_supply": 22,
    "dirty_water": 25, "burst_pipe_flooding": 30,
    "drain_blocked": 18, "sewage_overflow": 26, "open_manhole": 30,
    "missed_collection_once": 10, "overflowing_bin": 16,
    "dead_animal_carcass": 22, "illegal_dumping_large": 20,
    "mosquito_breeding": 18, "stray_dog_bite": 28,
    "disease_outbreak_concern": 30,
    "default": 15
}

SAFETY_KEYWORDS = [
    "accident", "danger", "hazard", "fire", "electric shock",
    "child fell", "injury", "death", "hospital", "emergency",
    "flood", "collapse", "snake", "rabies", "epidemic",
    "விபத்து", "ஆபத்து", "आग", "खतरा", "ప్రమాదం"
]

DEPT_SLA_DAYS = {
    "D01": 3, "D02": 14, "D03": 5, "D04": 3, "D05": 2,
    "D06": 7, "D07": 30, "D08": 5, "D09": 1, "D10": 1,
    "D11": 21, "D12": 7, "D13": 14, "D14": 1
}

def calculate_priority_score(
    subcategory: str,
    report_count: int,
    location_type: str,
    days_open: int,
    hours_until_sla_breach: float,
    social_media_mentions: int,
    description: str
) -> tuple[float, str]:
    """
    Returns (score: float 0-100, label: str CRITICAL/HIGH/MEDIUM/LOW)
    Pure function. No side effects. No DB calls. No external calls.
    """
    # Factor 1: Base severity (0-30)
    base = SEVERITY_MAP.get(subcategory, SEVERITY_MAP["default"])
    safety_bonus = 5 if any(kw.lower() in description.lower() for kw in SAFETY_KEYWORDS) else 0
    severity = min(30, base + safety_bonus)

    # Factor 2: Population impact (0-25)
    location_scores = {
        "main_road": 10, "hospital_vicinity": 10, "school_vicinity": 9,
        "market": 8, "residential": 5, "internal_street": 3, "unknown": 4
    }
    impact = min(15, report_count * 3) + location_scores.get(location_type, 4)

    # Factor 3: Time decay (0-20)
    if days_open <= 1: time_score = 0
    elif days_open <= 3: time_score = 5
    elif days_open <= 7: time_score = 10
    elif days_open <= 14: time_score = 15
    else: time_score = 20

    # Factor 4: SLA breach proximity (0-15)
    if hours_until_sla_breach <= 0: sla_score = 15
    elif hours_until_sla_breach <= 6: sla_score = 12
    elif hours_until_sla_breach <= 24: sla_score = 8
    elif hours_until_sla_breach <= 48: sla_score = 4
    else: sla_score = 0

    # Factor 5: Social amplification (0-10)
    if social_media_mentions > 100: social_score = 10
    elif social_media_mentions > 50: social_score = 7
    elif social_media_mentions > 10: social_score = 4
    else: social_score = 0

    score = min(100.0, severity + impact + time_score + sla_score + social_score)

    if score >= 80: label = "CRITICAL"
    elif score >= 60: label = "HIGH"
    elif score >= 35: label = "MEDIUM"
    else: label = "LOW"

    return round(score, 2), label
```

```python
# backend/app/core/ticket_codes.py
import random, string
from datetime import datetime

def generate_ticket_code() -> str:
    """CIV-2025-04872 format. Deterministic enough, not sequential."""
    year = datetime.now().year
    suffix = ''.join(random.choices(string.digits, k=5))
    return f"CIV-{year}-{suffix}"
```

```python
# backend/app/core/hashing.py
import hashlib, json

def hash_ticket_creation(ticket_id: int, dept_id: str,
                          ward_id: int, created_at: str) -> str:
    data = json.dumps({
        "ticket_id": ticket_id, "dept_id": dept_id,
        "ward_id": ward_id, "created_at": created_at
    }, sort_keys=True)
    return hashlib.sha256(data.encode()).hexdigest()

def hash_status_transition(ticket_id: int, old_status: str,
                            new_status: str, actor_id: int,
                            timestamp: str) -> str:
    data = json.dumps({
        "ticket_id": ticket_id, "old_status": old_status,
        "new_status": new_status, "actor_id": actor_id,
        "timestamp": timestamp
    }, sort_keys=True)
    return hashlib.sha256(data.encode()).hexdigest()

def hash_photo_evidence(before_bytes: bytes, after_bytes: bytes) -> str:
    before_hash = hashlib.sha256(before_bytes).hexdigest()
    after_hash = hashlib.sha256(after_bytes).hexdigest()
    return hashlib.sha256(f"{before_hash}{after_hash}".encode()).hexdigest()

def hash_citizen_verification(ticket_id: int, response: str,
                               timestamp: str) -> str:
    data = json.dumps({
        "ticket_id": ticket_id, "response": response,
        "timestamp": timestamp
    }, sort_keys=True)
    return hashlib.sha256(data.encode()).hexdigest()
```

```python
# backend/app/core/rbac.py
from app.models.user import UserRole

ROLE_PERMISSIONS = {
    UserRole.WARD_OFFICER: {
        "can_view_all_wards": False,
        "can_override_priority": False,
        "can_approve_budget_max": 10_000,
        "can_close_ticket": False,         # only via verification flow
        "can_approve_announcements": True,
        "can_view_predictions": False,
    },
    UserRole.ZONAL_OFFICER: {
        "can_view_all_wards": False,       # only their zone
        "can_override_priority": False,
        "can_approve_budget_max": 1_00_000,
        "can_close_ticket": False,
        "can_approve_announcements": True,
        "can_view_predictions": False,
    },
    UserRole.DEPT_HEAD: {
        "can_view_all_wards": True,        # but only own dept
        "can_override_priority": False,
        "can_approve_budget_max": 10_00_000,
        "can_close_ticket": False,
        "can_approve_announcements": True,
        "can_view_predictions": False,
    },
    UserRole.COMMISSIONER: {
        "can_view_all_wards": True,
        "can_override_priority": True,     # LOGGED IN AUDIT_LOG
        "can_approve_budget_max": None,    # no limit
        "can_close_ticket": False,
        "can_approve_announcements": True,
        "can_view_predictions": True,
    },
    UserRole.COUNCILLOR: {
        "can_view_all_wards": False,
        "can_override_priority": False,
        "can_approve_budget_max": 0,
        "can_close_ticket": False,
        "can_approve_announcements": False,
        "can_view_predictions": False,
    },
    UserRole.SUPER_ADMIN: {
        "can_view_all_wards": False,       # no civic data
        "can_override_priority": False,
        "can_approve_budget_max": 0,
        "can_close_ticket": False,
        "can_approve_announcements": False,
        "can_view_predictions": False,
    },
}

def can_view_ward(user_role: str, user_ward_id: int,
                  user_zone_id: int, requested_ward_id: int) -> bool:
    if user_role == UserRole.COMMISSIONER:
        return True
    if user_role == UserRole.DEPT_HEAD:
        return True   # but filtered by dept in query
    if user_role in (UserRole.ZONAL_OFFICER,):
        # Zone ward membership checked via DB — this is a placeholder
        return True   # actual check in service layer via DB
    if user_role in (UserRole.WARD_OFFICER, UserRole.COUNCILLOR):
        return user_ward_id == requested_ward_id
    return False
```

---

### 0H — Stub Adapters (so Phase 1 can run before real adapters are built)

```python
# backend/app/adapters/ai/stub_adapter.py
from app.interfaces.ai_provider import AIProvider, ClassificationResult, VisionResult, DraftResult

class StubAIAdapter(AIProvider):
    async def classify_complaint(self, text, image_url=None):
        return ClassificationResult(
            dept_id="D02", dept_name="Roads/Bridges",
            issue_summary=text[:100], location_extracted="",
            language_detected="en", confidence=0.9,
            needs_clarification=False, requires_human_review=False
        )
    async def verify_work_completion(self, before_url, after_url, issue_type):
        return VisionResult(work_completed=True, is_genuine_fix=True,
                            confidence=0.9, explanation="Stub", requires_human_review=False)
    async def draft_communication(self, context, communication_type, language):
        return DraftResult(content="Draft content placeholder", language=language)
    async def generate_ward_recommendation(self, ward_stats, risk_level):
        return "Stub recommendation"

# backend/app/adapters/storage/local_adapter.py
# Saves to local disk — good enough for development
import os, aiofiles
from app.interfaces.storage_provider import StorageProvider

class LocalStorageAdapter(StorageProvider):
    BASE_PATH = "./uploads"

    async def upload_file(self, file_bytes, destination_path, content_type="image/jpeg"):
        full_path = os.path.join(self.BASE_PATH, destination_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        async with aiofiles.open(full_path, 'wb') as f:
            await f.write(file_bytes)
        return f"http://localhost:8000/uploads/{destination_path}"

    async def get_presigned_upload_url(self, destination_path, content_type, expires_in_seconds=300):
        # For local dev: return a direct upload URL to our own endpoint
        return {"url": f"http://localhost:8000/api/uploads/{destination_path}", "fields": {}}

    async def get_file_url(self, file_path):
        return f"http://localhost:8000/uploads/{file_path}"

    async def delete_file(self, file_path):
        try:
            os.remove(os.path.join(self.BASE_PATH, file_path))
            return True
        except: return False

# backend/app/adapters/blockchain/stub_adapter.py
from app.interfaces.blockchain_provider import BlockchainProvider, BlockchainRecord
from datetime import datetime

class StubBlockchainAdapter(BlockchainProvider):
    async def record_hash(self, data_hash, event_type):
        # Just logs — no real blockchain
        return BlockchainRecord(
            hash=data_hash, transaction_id=None,
            block_number=None, recorded_at=datetime.utcnow().isoformat()
        )
    async def verify_hash(self, data_hash):
        return True  # Always true in stub

# backend/app/adapters/voice/stub_adapter.py
from app.interfaces.voice_provider import VoiceProvider, VoiceComplaintData, IVRCallRequest

class StubVoiceAdapter(VoiceProvider):
    async def handle_inbound_call(self, call_data):
        return VoiceComplaintData(
            raw_transcript="Stub transcript",
            language_detected="en",
            location_text="",
            issue_description="Stub complaint from voice call",
            severity_signals=[],
            caller_phone=call_data.get("From", ""),
            call_id=call_data.get("CallSid", "")
        )
    async def make_ivr_verification_call(self, request):
        return "stub_call_id"
```

---

**Phase 0 is done when:**

* `docker compose up` starts all 4 services with zero errors
* `alembic upgrade head` runs all migrations with zero errors
* `uvicorn app.main:app` starts with zero errors
* Every route in FastAPI returns the correct stub shape
* Every interface file exists with full docstrings
* Every stub adapter exists and works
* `npm run dev` starts Next.js with zero errors
* All TypeScript types are defined with zero type errors
* `.env.example` has every variable listed

**After Phase 0 is committed, the team rule is:** no one changes files in `interfaces/`, `core/`, `models/`, or `types/index.ts` without discussing it with everyone first. These are the bedrock.

---

## Phase 1 — Core Backend (Real Business Logic, No External Services)

**Depends on:** Phase 0 complete
**Anyone can pick any task from this list independently**
**No task in Phase 1 requires a real API key**

All tasks in this phase use only PostgreSQL (via SQLAlchemy), Redis (via aioredis), and the stub adapters from Phase 0.

---

### 1A — Auth System

**Files:** `backend/app/api/auth.py`, `backend/app/services/auth_service.py`

```
Build:
- POST /api/auth/login → verify password_hash → issue JWT → store in Redis
- POST /api/auth/refresh → verify httpOnly cookie → issue new access_token
- POST /api/auth/logout → delete Redis session
- JWT middleware: FastAPI dependency that validates token + fetches user
- Role injection: every protected route gets current_user injected
- Password hashing: bcrypt via passlib

Compliance note: JWT stored in memory on frontend, refresh token in httpOnly cookie.
Never return refresh token in response body.
Session invalidation must delete from Redis immediately.
```

---

### 1B — Ticket CRUD + Lifecycle

**Files:** `backend/app/api/public.py`, `backend/app/api/officer.py`, `backend/app/services/ticket_service.py`

```
Build:
- POST /api/public/complaints
  → validate consent_given = True (reject if False — DPDP)
  → call get_ai_provider().classify_complaint() (uses stub in Phase 1)
  → if confidence < 0.75: return clarification question, do not create ticket
  → calculate priority_score using core/priority.py
  → generate ticket_code
  → set sla_deadline = NOW() + dept.sla_days
  → insert ticket
  → write audit_log: TICKET_CREATED
  → call get_blockchain_provider().record_hash() (uses stub)
  → call get_sms_provider().send_message() (uses stub)
  → call get_whatsapp_provider().send_message() (uses stub — officer alert)
  → return ticket_code

- PATCH /api/officer/tickets/{id}/status
  Actions:
    ACCEPT → ASSIGNED, set assigned_officer_id, assigned_at
    REROUTE → change dept_id, reset SLA, stays OPEN
    ESCALATE → notify Zonal Officer
    MARK_COMPLETE → PENDING_VERIFICATION, trigger verification flow
    REJECT → REJECTED (social media tickets only)
  Every action → write audit_log entry. No exceptions.

- GET /api/officer/tickets → filtered by JWT role/ward/zone/dept
  Ward Officer: WHERE ward_id = user.ward_id
  Dept Head: WHERE dept_id = user.dept_id
  Commissioner: no filter
  Councillor: WHERE ward_id = user.ward_id (read-only)

- GET /api/public/track → by ticket_code or phone
  If phone: require OTP verification before returning (DPDP)
```

---

### 1C — SLA Engine (Celery Beat)

**Files:** `backend/app/services/sla_service.py`, `backend/app/tasks/sla_tasks.py`

```
Build:
- Celery Beat job runs every 5 minutes
- For every ticket WHERE status NOT IN (CLOSED, CLOSED_UNVERIFIED, REJECTED):
    → Recalculate priority_score (time_decay + sla_proximity factors update)
    → If sla_deadline < NOW() and not yet flagged:
        → Write audit_log: SLA_BREACHED
        → Send WhatsApp to Ward Officer (stub)
        → Send WhatsApp to Zonal Officer (stub)
    → If status = OPEN and sla_deadline < NOW() - 24hrs:
        → Auto-escalate: assign to Zonal Officer
        → Write audit_log: AUTO_ESCALATED_SLA_BREACH

Separate job every hour:
- Find OPEN tickets with no action in 24 hours
- Auto-escalate to Zonal Officer
- Write audit_log: AUTO_ESCALATED_NO_ACTION
```

---

### 1D — RBAC Middleware

**Files:** `backend/app/core/dependencies.py`

```python
# FastAPI dependencies — inject these into every protected route
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from app.core.rbac import ROLE_PERMISSIONS, can_view_ward

security = HTTPBearer()

async def get_current_user(token = Depends(security)) -> User:
    """Validates JWT, fetches user from Redis cache or DB."""
    ...

async def require_ward_officer(user = Depends(get_current_user)) -> User:
    if user.role not in ["WARD_OFFICER", "ZONAL_OFFICER", "DEPT_HEAD",
                          "COMMISSIONER", "SUPER_ADMIN"]:
        raise HTTPException(status_code=403, detail="INSUFFICIENT_ROLE")
    return user

async def require_commissioner(user = Depends(get_current_user)) -> User:
    if user.role != "COMMISSIONER":
        raise HTTPException(status_code=403)
    return user

# Use in routes:
# @router.patch("/tickets/{id}/status")
# async def update_status(id: int, user = Depends(require_ward_officer)):
```

---

### 1E — Public Dashboard Data Queries

**Files:** `backend/app/services/stats_service.py`

```
Build real DB queries for:
- City-wide stats (with Redis caching)
- Ward leaderboard (with Redis caching)
- Heatmap coordinates
- Department performance breakdown
- Recent resolutions feed
- Announcements (only approved=TRUE)

Cache invalidation: Celery Beat job refreshes each cache key on its TTL.
WebSocket: when a ticket status changes, push update to all connected clients.
```

---

### 1F — Approval Chain

**Files:** `backend/app/services/approval_service.py`

```
Build:
- POST /api/officer/tickets/{id}/approve-budget
  → Check approval_rules table: does caller's role cover this amount?
  → If yes: approve, write audit_log: BUDGET_APPROVED
  → If no: return 403 INSUFFICIENT_ROLE

- POST /api/officer/tickets/{id}/override-priority (Commissioner only)
  → Validate role = COMMISSIONER
  → Update priority_score
  → Write audit_log: PRIORITY_OVERRIDDEN with old_value + new_value + reason
  → This is the one case where Commissioner can modify the score.

- Approval chain display:
  → GET /api/officer/tickets/{id} includes approval_chain showing current stage
```

---

### 1G — Audit Log Service

**Files:** `backend/app/services/audit_service.py`

```python
# Single function used everywhere. Never query audit_log directly in routes.
async def write_audit(
    db,
    ticket_id: int,
    action: str,
    actor_id: int,
    actor_role: str,
    old_value: dict | None = None,
    new_value: dict | None = None,
    ip_address: str | None = None
):
    """
    Write-only. No update. No delete. No exceptions.
    If this fails, the entire parent transaction should fail.
    Log every: TICKET_CREATED, STATUS_CHANGED, BUDGET_APPROVED,
    PRIORITY_OVERRIDDEN, SLA_BREACHED, AUTO_ESCALATED, CITIZEN_CONFIRMED_FIXED,
    CITIZEN_DISPUTED, ANNOUNCEMENT_DRAFTED, ANNOUNCEMENT_APPROVED
    """
```

---

### 1H — Seed Data

**Files:** `backend/app/scripts/seed.py`

```
Run once after migrations:
- All 14 departments with correct SLA days and descriptions
- Approval rules (4 rows)
- Demo ward-dept-officer mapping for Ward 12 (Chennai demo ward)
- Demo user accounts for each of the 6 roles
- 20 sample tickets in various states for demo purposes
- 5 sample before/after photos (placeholder images)
```

---

**Phase 1 is done when:**

* Full ticket lifecycle works end-to-end via API (curl or Postman)
* Auth works: login, JWT-protected routes, role enforcement
* SLA engine runs and escalates correctly
* All public endpoints return real data from PostgreSQL
* Audit log is written on every state change
* Stub adapters mean everything works without a single real API key

---

## Phase 2 — AI Module

**Depends on:** Phase 0 only (runs parallel to Phase 1)
**Change config `AI_PROVIDER=gemini` to activate. Revert to `stub` to deactivate.**

**Files owned by this phase:** `backend/app/adapters/ai/`

---

### 2A — Gemini Classification Adapter

**File:** `backend/app/adapters/ai/gemini_adapter.py`

Implements `AIProvider` interface exactly. No other file changes.

```python
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.exceptions import OutputParserException
from app.interfaces.ai_provider import AIProvider, ClassificationResult

class GeminiAdapter(AIProvider):

    def __init__(self):
        self.llm_flash = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash", temperature=0,
            google_api_key=settings.GEMINI_API_KEY
        )
        self.llm_pro = ChatGoogleGenerativeAI(
            model="gemini-1.5-pro", temperature=0,
            google_api_key=settings.GEMINI_API_KEY
        )
        self._setup_chains()

    def _setup_chains(self):
        from pydantic import BaseModel, Field

        class ClassificationOutput(BaseModel):
            dept_id: str = Field(description="D01 to D14 only")
            dept_name: str
            issue_summary: str
            location_extracted: str
            language_detected: str
            confidence: float = Field(ge=0.0, le=1.0)
            needs_clarification: bool
            clarification_question: str | None = None

        parser = PydanticOutputParser(pydantic_object=ClassificationOutput)
        prompt = ChatPromptTemplate.from_messages([
            ("system", ROUTING_SYSTEM_PROMPT + "\n\n{format_instructions}"),
            ("human", "{complaint_text}")
        ])
        self.classify_chain = prompt | self.llm_flash | parser
        self._parser = parser

    async def classify_complaint(self, text, image_url=None) -> ClassificationResult:
        try:
            result = await self.classify_chain.ainvoke({
                "complaint_text": text,
                "format_instructions": self._parser.get_format_instructions()
            })
            return ClassificationResult(
                dept_id=result.dept_id,
                dept_name=result.dept_name,
                issue_summary=result.issue_summary,
                location_extracted=result.location_extracted,
                language_detected=result.language_detected,
                confidence=result.confidence,
                needs_clarification=result.needs_clarification,
                clarification_question=result.clarification_question,
                requires_human_review=result.confidence < 0.75
            )
        except OutputParserException:
            # Retry once with stricter prompt
            try:
                # retry logic
                pass
            except Exception:
                pass
        except Exception:
            pass

        # Safe fallback — always return something
        return ClassificationResult(
            dept_id="D01", dept_name="Unknown",
            issue_summary=text[:100], location_extracted="",
            language_detected="en", confidence=0.0,
            needs_clarification=False, requires_human_review=True
        )

    # verify_work_completion → uses llm_pro + vision
    # draft_communication → uses llm_flash or llm_pro based on type
    # generate_ward_recommendation → uses llm_pro
```

---

### 2B — Sentiment Adapter

**File:** `backend/app/adapters/sentiment/huggingface_adapter.py`

```python
from transformers import pipeline as hf_pipeline
from app.interfaces.sentiment_provider import SentimentProvider, SentimentResult

class HuggingFaceAdapter(SentimentProvider):

    def __init__(self):
        # Load once at startup. CPU inference.
        self._pipeline = hf_pipeline(
            "sentiment-analysis",
            model="cardiffnlp/twitter-roberta-base-sentiment",
            device=-1
        )

    async def analyze(self, texts: list[str]) -> SentimentResult:
        if not texts:
            return SentimentResult(0, 0, 0, 0, [])

        import asyncio
        results = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._pipeline(texts, truncation=True, max_length=512)
        )

        pos = sum(1 for r in results if r["label"] == "POSITIVE")
        neg = sum(1 for r in results if r["label"] == "NEGATIVE")
        neu = len(results) - pos - neg
        total = len(results)

        return SentimentResult(
            positive_pct=round(pos/total*100, 1),
            negative_pct=round(neg/total*100, 1),
            neutral_pct=round(neu/total*100, 1),
            total_analysed=total,
            top_negative_keywords=[]  # extracted separately via keyword analysis
        )
```

---

**Phase 2 is done when:**

* `AI_PROVIDER=gemini` in `.env` → real classification works
* `AI_PROVIDER=stub` → stub classification works
* No other file changed. Only the adapter file and config value.

---

## Phase 3 — File Storage Module

**Depends on:** Phase 0 only
**Change `STORAGE_PROVIDER` in config to swap. Nothing else changes.**

---

### 3A — MinIO Adapter (default local + self-hosted prod)

**File:** `backend/app/adapters/storage/minio_adapter.py`

```python
from miniopy_async import Minio
from app.interfaces.storage_provider import StorageProvider

class MinIOAdapter(StorageProvider):
    def __init__(self):
        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_USE_SSL
        )
        self.bucket = settings.MINIO_BUCKET

    async def upload_file(self, file_bytes, destination_path, content_type="image/jpeg"):
        import io
        data = io.BytesIO(file_bytes)
        await self.client.put_object(
            self.bucket, destination_path, data, len(file_bytes),
            content_type=content_type
        )
        return await self.get_file_url(destination_path)

    async def get_presigned_upload_url(self, destination_path, content_type, expires_in_seconds=300):
        from datetime import timedelta
        url = await self.client.presigned_put_object(
            self.bucket, destination_path,
            expires=timedelta(seconds=expires_in_seconds)
        )
        return {"url": url, "fields": {}}

    async def get_file_url(self, file_path):
        base = "https" if settings.MINIO_USE_SSL else "http"
        return f"{base}://{settings.MINIO_ENDPOINT}/{self.bucket}/{file_path}"

    async def delete_file(self, file_path):
        await self.client.remove_object(self.bucket, file_path)
        return True
```

### 3B — AWS S3 Adapter (swap-in for production or preference)

**File:** `backend/app/adapters/storage/s3_adapter.py`

```python
import aioboto3
from app.interfaces.storage_provider import StorageProvider

class S3Adapter(StorageProvider):
    # Implements same interface as MinIOAdapter
    # Drop-in swap: STORAGE_PROVIDER=s3 in .env
    # Uses AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_S3_BUCKET, AWS_REGION
    ...
```

---

**Phase 3 is done when:**

* Photo upload works end-to-end: frontend uploads to presigned URL, URL stored in ticket
* `STORAGE_PROVIDER=minio` → MinIO stores it
* `STORAGE_PROVIDER=s3` → S3 stores it
* `STORAGE_PROVIDER=local` → local disk stores it
* No other file changed

---

## Phase 4 — Notifications Module

**Depends on:** Phase 0 only. Runs fully parallel.
**Each provider independently swappable.**

---

### 4A — Twilio WhatsApp Adapter

**File:** `backend/app/adapters/notifications/twilio_whatsapp.py`

```python
from twilio.rest import Client
from app.interfaces.notification_provider import WhatsAppProvider, WhatsAppMessage, NotificationResult

class TwilioWhatsAppAdapter(WhatsAppProvider):

    def __init__(self):
        self.client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        self.from_number = f"whatsapp:{settings.TWILIO_WHATSAPP_NUMBER}"

    async def send_message(self, message: WhatsAppMessage) -> NotificationResult:
        import asyncio
        try:
            msg = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.messages.create(
                    from_=self.from_number,
                    to=f"whatsapp:{message.to_phone}",
                    body=message.body
                )
            )
            return NotificationResult(success=True, message_id=msg.sid)
        except Exception as e:
            return NotificationResult(success=False, error=str(e))
```

### 4B — MSG91 SMS Adapter

**File:** `backend/app/adapters/notifications/msg91_sms.py`

### 4C — SendGrid Email Adapter

**File:** `backend/app/adapters/notifications/sendgrid_email.py`

### 4D — Notification Service (orchestration layer)

**File:** `backend/app/services/notification_service.py`

```python
# This is what ticket_service.py calls. It never imports adapters directly.
from app.core.container import get_whatsapp_provider, get_sms_provider, get_email_provider
from app.interfaces.notification_provider import WhatsAppMessage, SMSMessage

class NotificationService:

    async def notify_officer_new_ticket(self, ticket, officer):
        provider = get_whatsapp_provider()
        await provider.send_message(WhatsAppMessage(
            to_phone=officer.phone,
            body=self._format_new_ticket_alert(ticket)
        ))

    async def confirm_ticket_to_citizen(self, ticket):
        provider = get_sms_provider()
        await provider.send_message(SMSMessage(
            to_phone=ticket.reporter_phone,
            body=f"Complaint {ticket.ticket_code} registered. Dept: {ticket.dept_name}. "
                 f"Track at civic.gov.in/track"
        ))

    def _format_new_ticket_alert(self, ticket) -> str:
        return (
            f"🔴 NEW [{ticket.priority_label}]\n"
            f"Code: {ticket.ticket_code}\n"
            f"Issue: {ticket.ai_summary}\n"
            f"Ward: {ticket.ward_name}\n"
            f"Score: {ticket.priority_score}/100\n"
            f"SLA: {ticket.sla_deadline.strftime('%d %b %H:%M')}\n"
            f"Reply: ACCEPT {ticket.ticket_code} | REROUTE {ticket.ticket_code} D0X"
        )
```

---

## Phase 5 — Voice Module

**Depends on:** Phase 0, Phase 1 (needs ticket creation API)
**Currently: `VOICE_PROVIDER=stub` in config**
**When Vomyra is figured out: build `vomyra_adapter.py`. Set `VOICE_PROVIDER=vomyra`. Done.**

---

### 5A — Stub Voice (already exists from Phase 0)

Provision is already in place. Webhook endpoint exists. Returns empty TwiML.

### 5B — Twilio IVR Verification (this part IS ready to build)

Even before voice intake is figured out, the outbound IVR verification call (after ticket closure) can be built with Twilio now.

**File:** `backend/app/adapters/voice/twilio_ivr_adapter.py`

```python
from twilio.twiml.voice_response import VoiceResponse, Gather
# This is only the outbound verification call — not the intake call
# Intake call = Vomyra (pending). Verification call = Twilio IVR (buildable now).

class TwilioIVRAdapter:

    def make_verification_call(self, to_phone: str, ticket_code: str,
                                issue_summary: str, language: str) -> str:
        """Make outbound call. Return call_id."""
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        call = client.calls.create(
            to=to_phone,
            from_=settings.TWILIO_PHONE_NUMBER,
            url=f"https://yourdomain.com/api/webhooks/ivr/twiml/{ticket_code}/{language}"
        )
        return call.sid

    def generate_twiml(self, ticket_code: str, language: str) -> str:
        """Generate TwiML for the IVR call flow."""
        response = VoiceResponse()
        gather = Gather(
            num_digits=1,
            action=f"/api/webhooks/ivr/callback?ticket_code={ticket_code}",
            timeout=10
        )
        # Use Sarvam TTS for Indian language audio
        gather.say(self._get_ivr_script(language), language=self._twiml_lang(language))
        response.append(gather)
        response.say("No input received. Closing.")
        return str(response)
```

### 5C — Vomyra Adapter (provision — build when ready)

**File:** `backend/app/adapters/voice/vomyra_adapter.py`

```python
# TODO: Research Vomyra API. Document here when ready.
# Must implement: VoiceProvider interface from interfaces/voice_provider.py
# Key things to figure out:
#   1. How does Vomyra handle inbound call webhooks?
#   2. What format does Vomyra return transcription in?
#   3. Does Vomyra support Tamil/Telugu natively?
#   4. How to configure multi-turn conversation flow?
# Once figured out: implement this class, set VOICE_PROVIDER=vomyra in .env
# No other file changes required.

from app.interfaces.voice_provider import VoiceProvider

class VomyraAdapter(VoiceProvider):
    async def handle_inbound_call(self, call_data: dict):
        raise NotImplementedError("Vomyra integration pending research")

    async def make_ivr_verification_call(self, request):
        raise NotImplementedError("Use Twilio IVR for verification calls for now")
```

---

## Phase 6 — Public Dashboard (Next.js)

**Depends on:** Phase 1 (real data) but can build against stubs from Phase 0
**Files owned:** `frontend/app/(public)/`, `frontend/components/public/`

---

### 6A — Setup & Shared Infrastructure

```
- Next.js 14 App Router configured
- Tailwind CSS configured
- React Query provider in root layout
- API client (frontend/lib/api-client.ts) with all methods
- All TypeScript types from types/index.ts
- i18next setup: Tamil, Hindi, Telugu, English
- Google Maps provider component
- Environment variables configured
```

### 6B — Home Page (/)

```
Components:
- CityStatsBanner: live stats via React Query, WebSocket update every 5 min
- ComplaintSubmitCTA: sticky button, opens submit form
- IssueHeatmap: Google Maps with ticket heat layer
- WardLeaderboardPreview: top 5 wards
- RecentResolutionsFeed: last 10 closed tickets
- AnnouncementsSidebar: official announcements

Compliance: No data collected on this page. Fully public.
```

### 6C — Submit Complaint (/submit)

```
Components:
- ComplaintForm:
  - Language selector (first field — determines rest of form language)
  - Description textarea with live classify-preview call
  - ClassificationPreview: shows dept, confidence badge while typing
  - PhotoUpload: direct S3/MinIO presigned upload
  - LocationPicker: text input + Google Maps pin drop
  - PhoneInput: required, for tracking updates
  - ConsentCheckbox: MANDATORY — form does not submit without it
    Text: "I consent to my contact details being used for
    resolution updates for this complaint only."
  - Submit → shows ticket_code + SLA date on success

Compliance:
- Consent checkbox: required=true, blocks submit
- Log consent_timestamp server-side
- No account creation. Phone only.
```

### 6D — Track Complaint (/track)

```
- Search by ticket_code → immediate result
- Search by phone → OTP verification first (DPDP)
- TicketTimeline: full audit_log rendered as timeline
- Before/after photo comparison
- SLA countdown timer
- Assigned department + officer name (not officer phone)
- Reopen button if resolved_at < 48hrs
```

### 6E — Ward Leaderboard (/wards)

```
- WardRankingTable: sortable, all wards
- WardScoreBreakdown: click ward → see component scores
- PerformanceTrendChart: Recharts line chart, 6-month trend per ward
- FilterBar: zone filter, month selector
```

### 6F — Department Breakdown (/departments)

```
- DeptCard for each D01–D14
- Metrics: tickets this month, resolved%, avg resolution days
- BestWorstWard: which ward has best/worst score for each dept
- DeptComparisonChart: Recharts bar chart, all depts side by side
```

### 6G — Resolutions Feed (/resolutions)

```
- InfiniteScroll list of closed tickets
- BeforeAfterPhotoCard: side-by-side images
- Filter by dept, ward, date range
- No login required
```

### 6H — Announcements (/announcements)

```
- Cards rendered from Markdown body
- Badge for announcement_type (FACT_CHECK, ADVISORY, etc.)
- Read-only. No login.
- Only approved=TRUE announcements from API
```

---

## Phase 7 — Officer Dashboard (Next.js)

**Depends on:** Phase 1 (auth + real ticket data)
**Files owned:** `frontend/app/(govt)/`, `frontend/components/govt/`

---

### 7A — Auth + Route Protection

```
- /officer/login → JWT login form
- Next.js middleware.ts: protect all /officer/* routes
- JWT stored in React Query cache (memory)
- Refresh token in httpOnly cookie
- Role-based redirect: Ward Officer → /officer/queue
                       Commissioner → /officer/overview
- LogoutButton: clears cache, clears cookie, redirects
```

### 7B — Priority Queue (/officer/queue)

```
- TicketQueue: sorted by priority_score DESC
- GroupedBySeverity: CRITICAL collapsed to top, always visible
- TicketRow: code, issue summary, ward, dept, score badge, SLA countdown
- QuickActions: ACCEPT / REROUTE / CLARIFY without opening detail
- WebSocket: new ticket appears at top automatically
- Cannot manually reorder — display only
- WhatsApp Workflow badge: shows tickets pending WA reply
```

### 7C — Ticket Detail (/officer/ticket/[id])

```
- Full description + AI classification + confidence bar
- Google Maps embed: ticket location pin
- PhotoViewer: before/after photo comparison
- AuditTimeline: every event in order
- DependencyPanel: blocked_by + requires_approval items
- ActionPanel (role-gated):
  - Ward Officer: Accept, Reroute, Clarify, Escalate, Mark Complete
  - Zonal Officer: Approve budget, Reassign
  - Commissioner: Override priority (with mandatory reason field)
- BudgetApprovalChain: shows current stage in chain
```

### 7D — Cross-Dept Workflow (/officer/workflow)

```
- BlockedTicketsPanel: your tickets blocked by another dept
- PendingApprovalsPanel: tickets needing your approval
- AwaitingOthersPanel: tickets where you're waiting for another dept
- RaiseSubtaskForm: create dependency between two tickets
```

### 7E — SLA Dashboard (/officer/sla)

```
- BreachedTickets: red alert list with hours overdue
- AtRiskTickets: orange list with countdown
- OnTrackTickets: green list
- WardRankingTable: your ward vs other wards (Ward Officer view)
- SLATrendChart: Recharts area chart, 30-day SLA compliance
```

### 7F — Sentiment Monitor (/officer/sentiment)

```
- WardMoodChart: Recharts area chart, 7-day positive/negative/neutral
- SpikeAlert: red banner if negative >+60% vs last week
- TrendingIssuesList: top negative keywords from social posts
- WardComparisonMood: Commissioner sees all wards
```

### 7G — Misinformation Panel (/officer/misinformation)

```
- FlaggedPostCard:
  - Post URL + claim text
  - EvidenceTable: ticket IDs that contradict the claim
  - DraftRebuttalEditor: editable AI draft
  - ApproveButton (writes to DB, does NOT post anywhere)
  - DismissButton (with reason)
- ApprovedList: previously approved rebuttals (for officer to post manually)
- Compliance note visible in UI: "Approved content must be posted manually
  by an authorised officer. This system never auto-posts."
```

### 7H — Report Generator (/officer/reports)

```
- Four buttons: Ward Committee | Standing Committee | Commissioner | CAG Audit
- Month + Year picker
- Generate → loading state → download link when Celery task completes
- HistoryTable: previously generated reports with download links
- Role-gated: Ward Officer sees only Ward Committee button
               Commissioner sees all four
```

### 7I — Announcements Draft (/officer/announcements)

```
- DraftForm: title, body (Markdown), type selector, related ticket (optional)
- DraftList: your drafted but unapproved announcements
- ApprovalQueue (Zonal Officer+): all pending drafts, approve/edit/reject
- PublishedList: already approved announcements
- Compliance: approve button only enabled for role that has permission
  Approved announcements appear on public portal immediately
```

### 7J — Predictions (/officer/predictions) — Commissioner only

```
- WardRiskTable: all wards, current vs predicted score, risk badge
- AtRiskWarnings: HIGH_RISK wards expanded with AI recommendation
- PredictionTrendChart: city health score over 12 months
- Route protected: 403 redirect if not Commissioner
```

---

## Phase 8 — Real-time (WebSocket)

**Depends on:** Phase 1 + Phase 6/7 (frontend exists)
**Files:** `backend/app/api/websocket.py`, `frontend/hooks/useWebSocket.ts`

```
Backend:
- ws://host/ws/public/stats → push city stats every 5 min
- ws://host/ws/officer/queue/{ward_id} → push new ticket event on creation
- ws://host/ws/officer/sla → push SLA breach events

Frontend:
- usePublicStatsSocket(): connects public dashboard, updates CityStatsBanner
- useOfficerQueueSocket(): connects officer queue, prepends new tickets
- Auto-reconnect on disconnect
- Graceful degradation: if WebSocket unavailable, React Query polls every 60s
```

---

## Phase 9 — Social Intelligence / Scraping

**Depends on:** Phase 2 (AI classification), Phase 1 (ticket creation)
**`ACTIVE_SCRAPERS=[]` in config until ready. Add platform names to enable.**
**Swap scrapers by adding new adapter files. Nothing else changes.**

---

### 9A — Scraper Framework (build this first)

**File:** `backend/app/services/scraper_orchestrator.py`

```python
# This calls whatever scrapers are active. Never changes.
from app.core.container import get_scraper_providers, get_ai_provider
from app.core.config import settings

async def run_scrape_cycle():
    """Called by Celery Beat. Runs all active scrapers."""
    providers = get_scraper_providers()   # empty list if ACTIVE_SCRAPERS=[]
    if not providers:
        return

    ai = get_ai_provider()

    for provider in providers:
        posts = await provider.scrape_recent(
            keywords=["pothole", "water", "garbage", "light", "drain",
                      "குழி", "தண்ணீர்", "குப்பை"],   # multilingual
            city=settings.CITY_NAME,
            limit=50
        )
        for post in posts:
            # Check if already processed
            if await is_duplicate_post(post.post_id, post.platform):
                continue

            # Store raw in MongoDB
            await store_raw_post(post)

            # Classify
            result = await ai.classify_complaint(post.text)

            # Apply same confidence thresholds as web portal
            if result.confidence >= 0.75:
                await create_ticket_from_social(post, result)
            # If < 0.75: store in MongoDB as unprocessed, do not create ticket
```

### 9B — Reddit Adapter (when ready)

**File:** `backend/app/adapters/scrapers/reddit_adapter.py`

```python
import praw
from app.interfaces.scraper_provider import ScraperProvider, ScrapedPost

class RedditAdapter(ScraperProvider):
    # Set ACTIVE_SCRAPERS=["reddit"] in .env to enable
    # Subreddits: r/Chennai, r/mumbai, r/bangalore, r/hyderabad, r/india

    async def scrape_recent(self, keywords, city, limit=50) -> list[ScrapedPost]:
        # PRAW → filter by keyword → strip all user info → return ScrapedPost list
        ...
```

### 9C — Other Platform Adapters (provision, build when decided)

```
backend/app/adapters/scrapers/twitter_adapter.py    → when provider decided
backend/app/adapters/scrapers/youtube_adapter.py    → YouTube Data API v3
backend/app/adapters/scrapers/news_adapter.py       → Google News RSS + feedparser
```

### 9D — Sentiment Jobs (Celery Beat)

```
- Every 15 min: pull recent posts from MongoDB, run sentiment, update Redis
- Spike detection: compare current negative_pct vs 7-day average
  If current > average * 1.6 → set spike_alert flag → officer dashboard alert
- Store snapshot in MongoDB: sentiment_snapshots collection
```

### 9E — Misinformation Detector

```
- Runs on every new social post after classification
- If post contains claim that contradicts existing closed tickets:
    → Cross-reference: claim location + claim dept + resolved tickets
    → If contradiction found: insert into MongoDB misinformation_flags
    → Generate draft rebuttal via AI provider
    → Flag appears in officer dashboard for human approval
- NEVER auto-post. Draft only. Human approval mandatory.
```

---

## Phase 10 — Reports & ML

**Depends on:** Phase 1 (sufficient ticket data), Phase 2 (AI for recommendations)

---

### 10A — PDF Report Generator

**Files:** `backend/app/services/report_service.py`, `backend/app/templates/reports/`

```
Build Jinja2 HTML templates for all 4 report types.
WeasyPrint converts to PDF.
Store PDF in file storage (via StorageProvider interface).
Return download URL.

Report generation is a Celery task (async) — frontend polls for completion.
Same template, different data = different report type.
Recharts-style data rendered server-side as SVG tables (no JS in PDF).
```

### 10B — RandomForest Ward Predictor

**Files:** `backend/app/ml/ward_predictor.py`

```python
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
import pandas as pd, joblib

class WardPredictor:
    """
    Predicts next month's ward performance score.
    Features: 12-month historical metrics per ward.
    Target: next month's composite score.
    """

    FEATURES = [
        "sla_compliance_pct_3m", "resolution_speed_avg_3m",
        "citizen_satisfaction_avg_3m", "open_critical_count",
        "social_sentiment_avg_3m", "report_count_growth_rate",
        "budget_utilisation_pct", "escalation_rate_3m",
        "seasonal_month",   # cyclical encoding for month
        "ward_population_density"
    ]

    def train(self, df: pd.DataFrame):
        X = df[self.FEATURES]
        y = df["next_month_score"]
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
        self.model = RandomForestRegressor(n_estimators=100, random_state=42)
        self.model.fit(X_train, y_train)
        joblib.dump(self.model, "ward_predictor_v1.pkl")

    def predict(self, ward_features: dict) -> dict:
        import numpy as np
        X = pd.DataFrame([ward_features])[self.FEATURES]
        score = self.model.predict(X)[0]
        if score < 40: risk = "HIGH_RISK"
        elif score < 65: risk = "MODERATE_RISK"
        else: risk = "LOW_RISK"
        return {"predicted_score": round(float(score), 2), "risk_level": risk}
```

---

## Phase 11 — Blockchain Audit

**Depends on:** Phase 0 (stub already exists), Phase 1 (tickets being created)
**Currently running on stub — blockchain_hash stored as raw SHA-256 only**
**When ready: set `BLOCKCHAIN_PROVIDER=polygon` in config. Nothing else changes.**

---

### 11A — Polygon Adapter

**File:** `backend/app/adapters/blockchain/polygon_adapter.py`

```python
from web3 import Web3
from app.interfaces.blockchain_provider import BlockchainProvider, BlockchainRecord
from app.core.config import settings

class PolygonAdapter(BlockchainProvider):

    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(settings.POLYGON_RPC_URL))
        # Load smart contract ABI
        self.contract = self.w3.eth.contract(
            address=settings.POLYGON_CONTRACT_ADDRESS,
            abi=AUDIT_CONTRACT_ABI
        )
        self.account = self.w3.eth.account.from_key(settings.POLYGON_PRIVATE_KEY)

    async def record_hash(self, data_hash: str, event_type: str) -> BlockchainRecord:
        import asyncio
        tx_hash = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._send_transaction(data_hash, event_type)
        )
        return BlockchainRecord(
            hash=data_hash,
            transaction_id=tx_hash,
            block_number=None,   # fetch in background
            recorded_at=...
        )

    def _send_transaction(self, data_hash: str, event_type: str) -> str:
        tx = self.contract.functions.recordHash(
            data_hash, event_type
        ).build_transaction({
            "from": self.account.address,
            "nonce": self.w3.eth.get_transaction_count(self.account.address),
            "gas": 100000,
            "gasPrice": self.w3.eth.gas_price
        })
        signed = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
        return tx_hash.hex()

    async def verify_hash(self, data_hash: str) -> bool:
        result = self.contract.functions.verifyHash(data_hash).call()
        return result
```

---

## Phase 12 — Compliance Hardening

**Depends on:** All other phases complete
**Anyone can pick any item independently**

```
□ DPDP — CITIZEN DATA RIGHTS
  - Build GET /api/citizen/my-data (OTP-verified, returns all their tickets)
  - Build DELETE /api/citizen/my-data (OTP-verified, anonymises their records)
  - Test: consent_given = False → 422 error from POST /api/public/complaints

□ IT ACT — SECURITY
  - HTTPS enforcement: 301 redirect HTTP → HTTPS (Nginx config)
  - HSTS header: Strict-Transport-Security: max-age=31536000
  - Rate limiting: 100 req/min per IP (FastAPI middleware)
  - AES-256 for PII fields at rest (SQLAlchemy field encryption)

□ CERT-In — LOGS
  - Log retention: verify 180-day retention on all log files
  - Incident alert: if HTTP 500 rate > 5% in 5 min → immediate alert
  - Test: generate a 500 error, verify alert fires

□ IMMUTABILITY
  - PostgreSQL rule on audit_log: block DELETE
  - Test: try DELETE FROM audit_log → verify exception
  - No DELETE endpoint exists for audit_log → verify in route list

□ SOCIAL MEDIA GUARDRAIL
  - Code audit: grep codebase for any call that could post to social media
  - Verify: zero such calls exist outside the manual officer approval path
  - announcements.approved must be TRUE for public endpoint to return it
  - Test: create draft, verify it does NOT appear on /api/public/announcements

□ ACCESSIBILITY
  - Install axe-core: npm install @axe-core/react
  - Run on both dashboards in development mode
  - Fix all critical and serious violations
  - Verify keyboard nav: Tab through entire public dashboard without mouse
  - Verify screen reader: test with macOS VoiceOver or NVDA

□ FRONTEND SECURITY
  - Verify: no JWT in localStorage anywhere in codebase
  - Verify: no API key in any NEXT_PUBLIC_ variable
  - Verify: RBAC on both frontend routing AND backend API

□ PII IN MONGODB
  - Audit: every MongoDB insert in scrapers passes through PII stripper
  - Verify: no username, no user_id, no profile_url in any raw_social_posts document
  - Verify: only text + location_hint + source_url + scraped_at stored
```

---

## Summary View

```
PHASE 0   Foundation               Bedrock. Never changes.
          └─ Schema, interfaces, DI container, stubs, types, core logic

PHASE 1   Core Backend             Real business logic. No API keys needed.
          ├─ 1A Auth
          ├─ 1B Ticket lifecycle
          ├─ 1C SLA engine
          ├─ 1D RBAC middleware
          ├─ 1E Dashboard queries
          ├─ 1F Approval chain
          ├─ 1G Audit log service
          └─ 1H Seed data

PHASE 2   AI Module                Swap: AI_PROVIDER=gemini/openai/stub
          ├─ 2A Gemini adapter
          └─ 2B HuggingFace sentiment adapter

PHASE 3   File Storage             Swap: STORAGE_PROVIDER=minio/s3/local
          ├─ 3A MinIO adapter
          └─ 3B S3 adapter

PHASE 4   Notifications            Each independently swappable
          ├─ 4A WhatsApp (Twilio)
          ├─ 4B SMS (MSG91)
          ├─ 4C Email (SendGrid)
          └─ 4D Notification orchestration service

PHASE 5   Voice Module             Swap: VOICE_PROVIDER=vomyra/twilio/stub
          ├─ 5A Stub (already done in Phase 0)
          ├─ 5B Twilio IVR verification (buildable now)
          └─ 5C Vomyra adapter (when researched)

PHASE 6   Public Dashboard         All 8 public pages. No auth.

PHASE 7   Officer Dashboard        All 10 officer pages. Full RBAC.

PHASE 8   Real-time                WebSocket for queue + stats

PHASE 9   Social Intelligence      Swap: ACTIVE_SCRAPERS=[reddit,twitter,...]
          ├─ 9A Scraper framework
          ├─ 9B Reddit adapter
          ├─ 9C Other platform adapters
          ├─ 9D Sentiment jobs
          └─ 9E Misinformation detector

PHASE 10  Reports & ML             PDF generation + RandomForest predictor

PHASE 11  Blockchain               Swap: BLOCKCHAIN_PROVIDER=polygon/stub

PHASE 12  Compliance Hardening     Checklists. Anyone picks any item.
```

---

## The Swap Table — Quick Reference

When you want to change a service, this is all you do:

| What you want to change          | Config variable                          | Files to write                             | Files that change |
| -------------------------------- | ---------------------------------------- | ------------------------------------------ | ----------------- |
| AI from Gemini to OpenAI         | `AI_PROVIDER=openai`                   | `adapters/ai/openai_adapter.py`          | Nothing else      |
| Storage from MinIO to S3         | `STORAGE_PROVIDER=s3`                  | `adapters/storage/s3_adapter.py`         | Nothing else      |
| WhatsApp from Twilio to anything | `WHATSAPP_PROVIDER=new`                | `adapters/notifications/new_whatsapp.py` | Nothing else      |
| SMS from MSG91 to Twilio         | `SMS_PROVIDER=twilio`                  | Already exists                             | Nothing else      |
| Voice from stub to Vomyra        | `VOICE_PROVIDER=vomyra`                | `adapters/voice/vomyra_adapter.py`       | Nothing else      |
| Add Reddit scraping              | `ACTIVE_SCRAPERS=["reddit"]`           | Already exists                             | Nothing else      |
| Add Twitter scraping             | `ACTIVE_SCRAPERS=["reddit","twitter"]` | `adapters/scrapers/twitter_adapter.py`   | Nothing else      |
| Blockchain from stub to Polygon  | `BLOCKCHAIN_PROVIDER=polygon`          | Already exists                             | Nothing else      |
| Add new AI model (keep Gemini)   | Edit gemini_adapter.py only              | —                                         | Nothing else      |

The answer to "what if we want to change X?" is always the same: write one adapter file, change one config value.
