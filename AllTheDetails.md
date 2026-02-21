# JanVedha-AI — FULL PROJECT CONTEXT

# Paste this as the persistent system/context prompt in Antigravity IDE.

# Every team member uses this exact same prompt.

# Do not modify individually. Discuss changes as a team before updating.

---

## WHAT WE ARE BUILDING

An AI-powered civic grievance intelligence system for Indian municipal governance.
The system collects citizen complaints from multiple input channels, classifies them
using AI, routes them to the correct government department, tracks the full resolution
lifecycle, verifies completion with tamper-proof evidence, and provides real-time
dashboards for both citizens and government officers.

This is essentially a production-grade NextGen CPGRAMS — the system the Indian
government is actively tendering to procure. We are building the prototype.

Two portals:

1. PUBLIC DASHBOARD — citizen-facing, zero login required for viewing
2. GOVT OFFICER DASHBOARD — JWT auth required, 6-role RBAC

---

## WHAT WE ARE NOT DOING (read this first to avoid wasted effort)

- NO mobile app (technician app removed from scope)
- NO AWS services of any kind
- NO graph database (Neo4j or similar) — pure relational + document + cache
- NO Zustand — use React Query + component state only
- NO MCP protocol for anything
- NO Xpoz — webscraping approach to be decided later (see provision section)
- NO branches in git — everyone commits to main directly
- NO auto-posting to social media under any circumstance (compliance hard rule)
- Voice AI provider is Vomyra — integration approach still being researched,
  do not implement yet, just keep the provision in architecture

---

## REPO STRUCTURE

JanVedha-AI/
├── backend/
│   ├── app/
│   │   ├── api/              → FastAPI route handlers
│   │   ├── models/           → SQLAlchemy ORM models
│   │   ├── services/         → Business logic (no direct DB queries here)
│   │   ├── ai/               → LangChain + Gemini chains, classification, vision
│   │   ├── scrapers/         → PROVISION ONLY — webscraping to be decided later
│   │   │                       File: scrapers/README.md explaining the placeholder
│   │   │                       Do not implement scrapers yet. Keep folder + readme.
│   │   ├── notifications/    → Twilio (WhatsApp + SMS + IVR), SendGrid
│   │   ├── voice/            → PROVISION ONLY — Vomyra integration to be researched
│   │   │                       File: voice/README.md explaining placeholder
│   │   │                       Do not implement yet. Keep folder + readme.
│   │   ├── reports/          → PDF generation (WeasyPrint + Jinja2)
│   │   └── ml/               → scikit-learn RandomForest ward predictor
│   ├── migrations/           → Alembic DB migrations
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── (public)/         → Public citizen dashboard pages
│   │   └── (govt)/           → Officer dashboard pages (auth-gated)
│   ├── components/
│   │   ├── public/           → Components used only in public dashboard
│   │   ├── govt/             → Components used only in officer dashboard
│   │   └── shared/           → Components used in both
│   ├── lib/                  → API clients, utilities, constants
│   ├── hooks/                → Custom React hooks (data fetching etc.)
│   ├── types/                → TypeScript type definitions
│   └── public/
├── infra/
│   └── docker-compose.yml    → PostgreSQL + Redis + MongoDB local setup
└── compliance/               → Consent templates, audit documentation

---

## TECH STACK — COMPLETE

### Frontend

- Next.js 14 (App Router)
- TypeScript — strict mode enabled, no `any` types
- Tailwind CSS — utility-first styling
- React Query (TanStack Query v5) — all server state, caching, refetch
- Google Maps JavaScript API — heatmap, ticket pins, GPS pin-drop, ward boundaries
- Recharts — charts where needed: SLA trend lines, ward rankings,
  sentiment area chart, dept performance donut, resolution speed bars
- i18next + next-i18next — multilingual: Tamil, Hindi, Telugu, English
- WebSocket (native browser API) — real-time ticket queue, live city stats
- axe-core — WCAG 2.1 AA accessibility testing during development
- No Zustand. Use React Query for server state. Use useState/useReducer
  for local UI state. Keep it simple.

### Backend

- Python 3.11
- FastAPI — REST API + WebSocket endpoints
- Uvicorn — ASGI server
- Pydantic v2 — request/response validation, structured LLM output parsing
- SQLAlchemy (async) — PostgreSQL ORM
- Alembic — DB schema migrations
- Celery — background task queue
- Celery Beat — scheduled jobs (SLA checks, ML predictions, future: scraping)
- httpx — async HTTP client for external API calls
- BeautifulSoup — HTML parsing (provision for future scraping)

### AI / LLM Layer

- LangChain (langchain, langchain-google-genai, langchain-core, langchain-community)
- Google Gemini 1.5 Flash → issue classification, voice dialogue, announcement drafts
  (use Flash for anything that needs speed or runs frequently)
- Google Gemini 1.5 Pro → vision analysis, before/after photo verification,
  complex report drafting (use Pro only where accuracy matters more than speed)
- HuggingFace: cardiffnlp/twitter-roberta-base-sentiment → sentiment analysis
  DO NOT use Gemini for sentiment. The fine-tuned Twitter model is more accurate
  for social media text than any general-purpose LLM.
- IndicBERT (AI4Bharat, HuggingFace) → multilingual Indian language NLP
- OpenAI Whisper (local, offline) → speech-to-text fallback
- Sarvam AI → primary STT + TTS for voice (Indian language specialist)
- langdetect → language detection
- DBSCAN (scikit-learn) → geo-clustering for duplicate complaint detection
- scikit-learn RandomForest → ward performance prediction (tabular data)
- joblib → ML model serialisation

### Voice AI

- Provider: Vomyra (vomyra.com)
- Status: PROVISION ONLY — integration approach still being researched
- Vomyra is currently the best free Indian-language voice AI option available
- When ready to implement: refer to voice/README.md for what needs to be built
- Do not wire anything to Vomyra yet. Keep voice/README.md as a spec document.
- What Vomyra needs to do when implemented:
  → Receive inbound citizen call
  → Conduct multilingual conversation (Tamil, Hindi, Telugu, English)
  → Extract: issue type, location, severity from conversation
  → Return structured data to our backend
  → Our backend creates the ticket

### Social Media / Web Scraping

- Status: PROVISION ONLY — scraping approach to be decided later
- Platforms to eventually cover: Reddit, Twitter/X, YouTube, local news sites
- Do not implement scrapers yet
- Keep scrapers/README.md as a spec document for future implementation
- What scrapers need to eventually do when implemented:
  → Run on a schedule (every 15–30 min depending on platform)
  → Extract public posts mentioning civic issues in Indian cities
  → Pass raw text to AI classification pipeline
  → Store raw data in MongoDB
  → Create tickets for posts with confidence >= 0.75
- For now: all ticket data comes from web portal, WhatsApp, and voice call only

### Databases

1. PostgreSQL 15 — PRIMARY relational DB
   → All structured data: tickets, users, departments, audit logs
   → PostGIS extension for geo queries (ward boundary from lat/long)
   → Hosted locally via Docker for dev. Self-hosted VPS for prod.
   → Driver: SQLAlchemy async + asyncpg
2. MongoDB — raw / flexible schema data
   → Raw scraped social media posts (when scraping is implemented)
   → Sentiment snapshots
   → Misinformation flags + draft rebuttals
   → Hosted locally via Docker for dev
   → Driver: motor (async Python)
3. Redis 7 — cache + session + real-time
   → Dashboard stats cache (5-min TTL)
   → Ward sentiment cache (15-min TTL)
   → Officer JWT session tokens (8-hr TTL)
   → API rate limiting per IP
   → WhatsApp conversation state (30-min TTL)
   → Ward ticket queue cache (1-min TTL)
   → Hosted locally via Docker for dev
   → Driver: aioredis
4. File Storage — self-hosted or simple VPS object storage
   → Before photos, after photos, citizen uploads
   → Generated PDF reports
   → Serialised ML model files
   → Use presigned-style URLs for direct upload from frontend
   → No AWS S3. Use MinIO (S3-compatible, self-hosted) or similar.
5. Polygon Blockchain (testnet for demo, mainnet for prod)
   → Stores ONLY SHA-256 hashes for tamper-proof audit trail
   → NO PII ever on-chain. Hashes only. Always.
   → Driver: web3.py
   → Hash on: ticket creation, every status transition, photo evidence, citizen verification

### Communication & Notifications

- Twilio WhatsApp Business API → officer notifications + citizen complaint bot
- Twilio Voice API → outbound IVR verification calls to citizens on ticket closure
- MSG91 → SMS (primary for India — better deliverability on Jio/Airtel/BSNL)
- Twilio SMS → SMS backup
- SendGrid → email delivery for monthly PDF reports to officers/councillors

### Infrastructure (local + simple VPS)

- Docker + Docker Compose → local development (PostgreSQL + Redis + MongoDB)
- VPS (DigitalOcean / Hetzner / any) → production deployment
- Nginx → reverse proxy, SSL termination, HTTPS enforcement
- Let's Encrypt (Certbot) → free SSL certificates
- GitHub → version control (single main branch, no branch strategy)
- GitHub Actions → CI: run tests on push, nothing more complex
- ngrok → local webhook exposure during development (Twilio webhooks etc.)

---

## DATABASE SCHEMA — POSTGRESQL

```sql
-- TICKETS (core lifecycle)
CREATE TABLE tickets (
    id SERIAL PRIMARY KEY,
    ticket_code VARCHAR(20) UNIQUE,        -- e.g. CIV-2025-04872
    source VARCHAR(20) NOT NULL,
    -- VOICE_CALL | WEB_PORTAL | WHATSAPP | SOCIAL_MEDIA | NEWS | CPGRAMS
    source_url TEXT,                       -- for social media source posts
    description TEXT NOT NULL,
    dept_id VARCHAR(5) NOT NULL,           -- D01 to D14
    ward_id INT,
    zone_id INT,
    coordinates GEOGRAPHY(POINT, 4326),    -- PostGIS
    photo_url TEXT,                        -- citizen submitted photo
    before_photo_url TEXT,                 -- technician before-work photo
    after_photo_url TEXT,                  -- technician after-work photo
    reporter_phone VARCHAR(15),
    reporter_name VARCHAR(100),
    language_detected VARCHAR(20),
    ai_confidence FLOAT,
    priority_score FLOAT,                  -- 0–100, auto-calculated always
    priority_label VARCHAR(10),            -- CRITICAL | HIGH | MEDIUM | LOW
    status VARCHAR(30) DEFAULT 'OPEN',
    -- OPEN | ASSIGNED | IN_PROGRESS | PENDING_VERIFICATION | CLOSED
    -- REJECTED | CLOSED_UNVERIFIED | REOPENED
    report_count INT DEFAULT 1,            -- duplicate reports increment this
    requires_human_review BOOLEAN DEFAULT FALSE,
    estimated_cost DECIMAL(12,2),
    citizen_satisfaction INT,              -- 1–5 stars from IVR callback
    sla_deadline TIMESTAMP,               -- auto-set from dept.sla_days
    social_media_mentions INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    assigned_at TIMESTAMP,
    resolved_at TIMESTAMP,
    assigned_officer_id INT REFERENCES users(id)
);

-- DEPARTMENTS (D01–D14 hardcoded routing table)
CREATE TABLE departments (
    dept_id VARCHAR(5) PRIMARY KEY,
    dept_name VARCHAR(100) NOT NULL,
    handles TEXT,                          -- plain text description of what it covers
    sla_days INT NOT NULL,
    is_external BOOLEAN DEFAULT FALSE,     -- TRUE for D10 (DISCOM/TANGEDCO)
    parent_body VARCHAR(100),
    escalation_role VARCHAR(50)
);

-- SEED DATA (run once — never let AI determine these mappings)
INSERT INTO departments VALUES
('D01','Electrical/Lighting',
 'Street lights, public electrical fixtures. NOT area power cuts.',3,FALSE,'Municipal Corporation','WARD_OFFICER'),
('D02','Roads/Bridges',
 'Potholes, road damage, footpath, bridge cracks, speed bumps.',14,FALSE,'Municipal Corporation','WARD_OFFICER'),
('D03','Water Supply',
 'Water not coming, dirty water, burst pipe, low pressure, tanker request.',5,FALSE,'Municipal Corporation','WARD_OFFICER'),
('D04','Sewerage/Drainage',
 'Sewage overflow, blocked drain, open manhole, flooding.',3,FALSE,'Municipal Corporation','WARD_OFFICER'),
('D05','Solid Waste/Sanitation',
 'Garbage not collected, overflowing bin, illegal dumping, dead animal.',2,FALSE,'Municipal Corporation','WARD_OFFICER'),
('D06','Health/Vector Control',
 'Mosquito breeding, stray dog bite, disease outbreak concern.',7,FALSE,'Municipal Corporation','WARD_OFFICER'),
('D07','Town Planning/Buildings',
 'Illegal construction, encroachment on footpath or road.',30,FALSE,'Municipal Corporation','ZONAL_OFFICER'),
('D08','Parks/Horticulture',
 'Tree fallen, park damaged, tree pruning needed, public garden neglected.',5,FALSE,'Municipal Corporation','WARD_OFFICER'),
('D09','Police',
 'Noise complaint, traffic signal fault, public disturbance.',1,FALSE,'Local Police','WARD_OFFICER'),
('D10','DISCOM/Electricity Board',
 'AREA-WIDE power cut, transformer fault, high-tension wire danger. NOT single street light.',1,TRUE,'TANGEDCO/BESCOM/BSES','WARD_OFFICER'),
('D11','Revenue/Encroachment',
 'Land encroachment, illegal hawker, illegal parking on govt land.',21,FALSE,'Municipal Corporation','ZONAL_OFFICER'),
('D12','Education',
 'Corporation school building damage, no teacher, mid-day meal issues.',7,FALSE,'Municipal Corporation','WARD_OFFICER'),
('D13','Slum Improvement',
 'Slum infrastructure, lack of basic amenities in notified slums.',14,FALSE,'Municipal Corporation','ZONAL_OFFICER'),
('D14','Fire Services',
 'Fire hazard, blocked fire access roads, fire safety inspection request.',1,FALSE,'Municipal Corporation','WARD_OFFICER');

-- CRITICAL ROUTING DISTINCTION (burn this into memory):
-- 'Single street light not working' → D01 (Municipal Electrical)
-- 'Whole street / area has no power' → D10 (DISCOM — external body)

-- USERS
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    phone VARCHAR(15) UNIQUE,
    email VARCHAR(100) UNIQUE,
    password_hash VARCHAR(255),
    role VARCHAR(30) NOT NULL,
    -- WARD_OFFICER | ZONAL_OFFICER | DEPT_HEAD | COMMISSIONER
    -- COUNCILLOR | SUPER_ADMIN | TECHNICIAN
    ward_id INT,
    zone_id INT,
    dept_id VARCHAR(5) REFERENCES departments(dept_id),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- WARD OFFICER ROUTING (who handles which ward + dept combination)
CREATE TABLE ward_dept_officers (
    ward_id INT,
    dept_id VARCHAR(5) REFERENCES departments(dept_id),
    officer_id INT REFERENCES users(id),
    PRIMARY KEY (ward_id, dept_id)
);

-- TICKET DEPENDENCIES (cross-dept workflows)
CREATE TABLE ticket_dependencies (
    id SERIAL PRIMARY KEY,
    ticket_id INT REFERENCES tickets(id),
    depends_on_ticket_id INT REFERENCES tickets(id),
    dependency_type VARCHAR(30),
    -- BLOCKED_BY | REQUIRES_APPROVAL | NOTIFIES
    status VARCHAR(20) DEFAULT 'PENDING',
    -- PENDING | RESOLVED
    created_at TIMESTAMP DEFAULT NOW()
);

-- BUDGET APPROVAL RULES
CREATE TABLE approval_rules (
    id SERIAL PRIMARY KEY,
    dept_id VARCHAR(5),                   -- NULL = applies to all departments
    min_cost DECIMAL(12,2),
    max_cost DECIMAL(12,2),               -- NULL = no upper limit
    approver_role VARCHAR(50),
    auto_approve BOOLEAN DEFAULT FALSE
);
-- SEED:
INSERT INTO approval_rules VALUES
(DEFAULT,NULL,0,10000,'WARD_OFFICER',TRUE),
(DEFAULT,NULL,10001,100000,'ZONAL_OFFICER',FALSE),
(DEFAULT,NULL,100001,1000000,'DEPT_HEAD',FALSE),
(DEFAULT,NULL,1000001,NULL,'COMMISSIONER',FALSE);

-- AUDIT LOG (IMMUTABLE — no UPDATE, no DELETE, ever)
CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    ticket_id INT REFERENCES tickets(id),
    action VARCHAR(100) NOT NULL,
    old_value JSONB,
    new_value JSONB,
    actor_id INT REFERENCES users(id),
    actor_role VARCHAR(50),
    ip_address INET,
    created_at TIMESTAMP DEFAULT NOW()
);
-- Add trigger after creating this table:
-- CREATE RULE no_delete_audit AS ON DELETE TO audit_log DO INSTEAD NOTHING;
-- This makes audit_log physically undeletable. CERT-In compliance.

-- ANNOUNCEMENTS (officer-drafted, must be approved before going public)
CREATE TABLE announcements (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200),
    body TEXT NOT NULL,
    drafted_by INT REFERENCES users(id),
    approved_by INT REFERENCES users(id),
    approved BOOLEAN DEFAULT FALSE,       -- NEVER show to public until TRUE
    related_ticket_id INT REFERENCES tickets(id),
    announcement_type VARCHAR(50),
    -- WORK_UPDATE | RESOLUTION | FACT_CHECK | ADVISORY | EMERGENCY
    created_at TIMESTAMP DEFAULT NOW(),
    published_at TIMESTAMP
);

-- WARD PREDICTIONS (ML output stored daily)
CREATE TABLE ward_predictions (
    id SERIAL PRIMARY KEY,
    ward_id INT NOT NULL,
    current_score FLOAT,
    predicted_next_month_score FLOAT,
    risk_level VARCHAR(20),              -- HIGH_RISK | MODERATE_RISK | LOW_RISK
    ai_recommendation TEXT,
    computed_at TIMESTAMP DEFAULT NOW()
);

-- CLASSIFIER CORRECTIONS (rerouted tickets feed back as training data)
CREATE TABLE classifier_corrections (
    id SERIAL PRIMARY KEY,
    ticket_id INT REFERENCES tickets(id),
    complaint_text TEXT,
    original_dept_id VARCHAR(5),
    corrected_dept_id VARCHAR(5),
    corrected_by INT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## AI LAYER — LANGCHAIN + GEMINI

### LLM Initialisation (use these exact model choices everywhere)

```python
from langchain_google_genai import ChatGoogleGenerativeAI

# Flash — fast and cheap. Use for: classification, voice dialogue, drafts
llm_flash = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    temperature=0,
    google_api_key=settings.GEMINI_API_KEY
)

# Pro — slower but accurate. Use for: vision, before/after verify, complex writing
llm_pro = ChatGoogleGenerativeAI(
    model="gemini-1.5-pro",
    temperature=0,
    google_api_key=settings.GEMINI_API_KEY
)
```

### Classification Chain Pattern

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

class TicketClassification(BaseModel):
    dept_id: str = Field(description="D01 to D14 only")
    dept_name: str
    issue_summary: str
    location_extracted: str
    language_detected: str
    confidence: float = Field(ge=0.0, le=1.0)
    needs_clarification: bool
    clarification_question: str | None = None

parser = PydanticOutputParser(pydantic_object=TicketClassification)

classify_chain = (
    ChatPromptTemplate.from_messages([
        ("system", ROUTING_SYSTEM_PROMPT + "\n\n{format_instructions}"),
        ("human", "{complaint_text}")
    ])
    | llm_flash
    | parser
)

# Confidence threshold rules (enforce everywhere, no exceptions):
# >= 0.85 → auto-create ticket, status OPEN
# 0.75–0.84 → create ticket, set requires_human_review = TRUE
# < 0.75 → do not create ticket, return clarification_question to user
```

### Routing System Prompt (never change dept list without full team discussion)

```python
ROUTING_SYSTEM_PROMPT = """
You are a civic issue classifier for an Indian municipal corporation.
Classify the citizen complaint into ONLY one of these departments:

D01 - Electrical/Lighting: street lights, public electrical fixtures (NOT area power cuts)
D02 - Roads/Bridges: potholes, road damage, footpath broken, bridge issues
D03 - Water Supply: water not coming, dirty water, burst pipe, low pressure
D04 - Sewerage/Drainage: sewage overflow, blocked drain, open/uncovered manhole
D05 - Solid Waste/Sanitation: garbage not collected, overflowing bin, illegal dumping
D06 - Health/Vector Control: mosquito breeding, stray dog bite, disease concern
D07 - Town Planning/Buildings: illegal construction, encroachment on public land
D08 - Parks/Horticulture: fallen tree blocking road, park damage, pruning needed
D09 - Police: noise complaint, traffic signal not working, public disturbance
D10 - DISCOM (External Body): AREA-WIDE power cut, transformer fault
D11 - Revenue/Encroachment: land encroachment, illegal hawkers, unauthorised parking
D12 - Education: corporation school building damage, mid-day meal issues
D13 - Slum Improvement: slum infrastructure, basic amenities in notified slums
D14 - Fire Services: fire hazard, blocked fire access road

CRITICAL RULE: Single street light not working = D01. Whole area has no power = D10.

Detect the language of the complaint automatically.
Supported: Tamil, Hindi, Telugu, Kannada, Marathi, Bengali, English.
If asking a clarification question, ask in the same language as the complaint.

Output ONLY valid JSON matching the exact schema provided. No extra text.
"""
```

### Priority Score Formula (do not modify without team consensus)

```python
def calculate_priority_score(ticket) -> float:
    """
    Returns 0–100. Higher = more urgent. Run on ticket create and update.
    Officers cannot manually change this score.
    Only COMMISSIONER can override — and every override is logged in audit_log.
  
    Factor 1: Base Severity (0–30 pts)
      → From hardcoded SEVERITY_MAP per subcategory
      → Safety keywords in description add up to +5 bonus
  
    Factor 2: Population Impact (0–25 pts)
      → report_count * 3 (max 15) + location_type score (max 10)
      → location types: main_road=10, hospital/school vicinity=9-10, market=8,
        residential=5, internal_street=3
    
    Factor 3: Time Decay (0–20 pts)
      → Days open: 0-1d=0pts, 2-3d=5pts, 4-7d=10pts, 8-14d=15pts, >14d=20pts
  
    Factor 4: SLA Breach Proximity (0–15 pts)
      → Already breached=15, <6hrs=12, <24hrs=8, <48hrs=4, else=0
  
    Factor 5: Social Media Amplification (0–10 pts)
      → social_media_mentions: >100=10, >50=7, >10=4, else=0
  
    Labels: CRITICAL>=80, HIGH>=60, MEDIUM>=35, LOW<35
    """
```

### Vision Analysis (before/after verification)

```python
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
import base64, httpx

async def verify_work_completion(
    before_url: str, after_url: str, issue_type: str
) -> dict:
    before_b64 = base64.b64encode(httpx.get(before_url).content).decode()
    after_b64 = base64.b64encode(httpx.get(after_url).content).decode()

    message = HumanMessage(content=[
        {"type": "text", "text": f"""
        Issue type: {issue_type}
        Image 1 = BEFORE work. Image 2 = AFTER work.
        Compare them. Return JSON only:
        {{
          "work_completed": true/false,
          "is_genuine_fix": true/false,
          "confidence": 0.0-1.0,
          "explanation": "1-2 sentences",
          "requires_human_review": true/false
        }}
        If confidence < 0.85, set requires_human_review to true.
        """},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{before_b64}"}},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{after_b64}"}},
    ])

    response = await llm_pro.ainvoke([message])
    # Parse JSON from response.content
    # If confidence >= 0.85 and work_completed: proceed to citizen IVR call
    # Else: flag for officer human review
```

### Sentiment Analysis (always use HuggingFace, not Gemini)

```python
from transformers import pipeline

sentiment_pipeline = pipeline(
    "sentiment-analysis",
    model="cardiffnlp/twitter-roberta-base-sentiment",
    device=-1  # CPU
)

def analyze_ward_sentiment(posts: list[str]) -> dict:
    results = sentiment_pipeline(posts, truncation=True, max_length=512)
    pos = sum(1 for r in results if r["label"] == "POSITIVE")
    neg = sum(1 for r in results if r["label"] == "NEGATIVE")
    neu = sum(1 for r in results if r["label"] == "NEUTRAL")
    total = len(results)
    return {
        "positive_pct": round(pos/total*100, 1) if total else 0,
        "negative_pct": round(neg/total*100, 1) if total else 0,
        "neutral_pct": round(neu/total*100, 1) if total else 0,
        "total_posts_analysed": total
    }
# Spike alert: if negative_pct > (last_week_negative_pct * 1.6) → send alert
```

---

## GOVERNMENT HIERARCHY

### 3-Level Structure

LEVEL 1 — CITY APEX
├── Municipal Commissioner (IAS)
│   → Full city view, all wards, all depts
│   → Approves budgets > ₹10,00,000
│   → Only role that can override priority score (logged)
│   → Receives ML predictive alerts and executive reports
│
├── Standing Committee (18 councillors)
│   → Highest policy/budget decision body
│   → Receives auto-generated monthly Standing Committee Report
│   → Approves large budget sanctions
│
└── Ward Councillors (elected representatives)
→ READ-ONLY view of their ward
→ Can flag 1 ticket/week for political priority
→ Sees constituent sentiment + ward ranking
→ NO executive action. Monitor only.

LEVEL 2 — ZONE / DEPARTMENT
├── Zonal Officer (Assistant Engineer)
│   → All wards within their zone (e.g. Wards 15–21)
│   → Handles escalations from Ward Officers
│   → Approves ₹10,001 – ₹1,00,000 repairs
│   → Can reassign technicians across wards in zone
│
└── Department Heads (Chief Engineers per dept)
→ All tickets for their dept (e.g. D02 Roads) across all wards citywide
→ Approves ₹1,00,001 – ₹10,00,000 repairs
→ Sees dept ranking vs other depts
→ NO access to other dept's tickets

LEVEL 3 — WARD / FIELD
├── Ward Officer (Junior Engineer)
│   → Their ward ONLY. Cannot see other wards.
│   → Receives every ticket for their ward
│   → Accepts, reroutes, assigns to technician
│   → Auto-approves repairs ≤ ₹10,000
│   → Primary user of WhatsApp notification workflow
│
└── Super Admin (system admin)
→ System configuration only. No civic data access.
→ Manages ward-dept-officer mapping
→ Creates/deactivates user accounts
→ Updates department routing table

```

### Budget Approval Chain
```

₹0 – ₹10,000          → Ward Officer (auto-approve, no manual step required)
₹10,001 – ₹1,00,000   → Zonal Officer (must manually approve in dashboard)
₹1,00,001 – ₹10,00,000 → Department Head (must manually approve)

> ₹10,00,000           → Commissioner + Standing Committee

```

### Ticket Lifecycle
```

OPEN
→ (Ward Officer accepts) → ASSIGNED
→ (24hr no response) → auto-escalate to Zonal Officer

ASSIGNED
→ (Technician dispatched) → IN_PROGRESS
→ (SLA deadline approaching) → flag to Dept Head

IN_PROGRESS
→ (Technician marks complete + uploads photo) → PENDING_VERIFICATION

PENDING_VERIFICATION
→ (AI photo check ≥0.85 confidence) AND (citizen IVR confirms) → CLOSED
→ (Citizen says not fixed) → REOPENED → back to ASSIGNED
→ (No IVR response within timeout) → CLOSED_UNVERIFIED

CLOSED
→ (Citizen rates 1–2 stars within 48hrs) → REOPENED

REJECTED
→ Only for social media tickets that fail human review

```

---

## RBAC — ROLE-BASED ACCESS CONTROL

Enforce on BOTH Next.js route level AND FastAPI middleware.
Never trust only the frontend. Backend always re-validates.
```

WARD_OFFICER
Can view:   own ward tickets only, own ward sentiment, own ward reports
Can do:     accept/reroute ticket, assign technician, approve ≤₹10K,
request cross-dept subtask, approve announcement draft,
generate ward committee PDF report
Cannot:     view other wards, close ticket without verification,
override priority score

ZONAL_OFFICER
Can view:   all wards in their zone, escalated tickets
Can do:     approve ₹10K–₹1L repairs, reassign cross-ward technicians,
view zone-wide SLA dashboard
Cannot:     access wards outside their zone

DEPT_HEAD
Can view:   all tickets in their dept across all wards citywide
Can do:     approve ₹1L–₹10L repairs, view dept ranking,
reassign crew, identify recurring hotspots
Cannot:     access other departments' data

COMMISSIONER
Can view:   everything, all wards, all depts, city-wide analytics
Can do:     override priority score (logged in audit_log),
approve >₹10L budgets, generate all report types,
export to CPGRAMS, view ML predictions
Cannot:     close individual tickets directly (ward-level function)

COUNCILLOR
Can view:   own ward read-only, own ward sentiment
Can do:     flag 1 ticket/week for political priority
Cannot:     any executive action, mark tickets complete

SUPER_ADMIN
Can view:   system configuration only
Can do:     manage users, update dept routing table, manage SLA rules
Cannot:     access any civic ticket data

```

---

## FRONTEND — NEXT.JS STRUCTURE

### Public Dashboard Pages
```

/                          → Landing: city stats + heatmap + submit CTA
/track                     → Track my complaint (ticket# or phone)
/wards                     → Ward leaderboard + performance rankings
/departments               → D01–D14 dept performance breakdown
/resolutions               → Recent closed tickets feed with before/after photos
/announcements             → Official announcements feed
/submit                    → Complaint submission form

```

### Government Dashboard Pages (all under /officer — auth required)
```

/officer/login             → JWT login
/officer/queue             → Priority ticket queue (main view)
/officer/ticket/[id]       → Ticket detail + action panel
/officer/workflow          → Cross-dept dependencies + pending approvals
/officer/sentiment         → Ward sentiment monitor
/officer/misinformation    → Flagged posts + draft rebuttals
/officer/reports           → Report generator (4 types)
/officer/performance       → Officer + ward performance dashboard
/officer/predictions       → ML predictions (Commissioner only)
/officer/announcements     → Draft + approve announcements

### Component Patterns

```typescript
// All data fetching via React Query. No data fetching inside components directly.
// Wrong:
const [data, setData] = useState(null)
useEffect(() => { fetch('/api/tickets').then(...) }, [])

// Right:
const { data, isLoading, error } = useQuery({
  queryKey: ['tickets', wardId],
  queryFn: () => apiClient.getTickets(wardId),
  staleTime: 60_000, // 1 min
})

// Type all API responses strictly. No 'any'.
// Put all TypeScript interfaces in /types/

// Environment variables in Next.js:
// Server-side only (API keys): process.env.GEMINI_API_KEY
// Client-safe (public): process.env.NEXT_PUBLIC_GOOGLE_MAPS_KEY
// Never expose API keys to client bundle.
```

### Auth Pattern (Next.js)

```typescript
// JWT stored in memory (React state / React Query cache)
// Refresh token in httpOnly cookie only (prevents XSS)
// Never localStorage for JWT — DPDP + security requirement

// Route protection in Next.js App Router:
// Use middleware.ts to check auth on /officer/* routes
// Role-based page access enforced in layout components
```

---

## COMPLIANCE REQUIREMENTS (non-negotiable)

### DPDP Act 2023

- Consent checkbox on complaint form BEFORE collecting phone number.
  Exact text: "I consent to my contact details being used for tracking
  and resolution updates for this complaint only."
  Log: consent_given=TRUE and consent_timestamp in tickets table.
- Voice call verbal disclosure (when Vomyra is implemented):
  "This call is recorded for complaint logging only."
- Citizens have right to access and erase their data.
  Build: GET /my-data and DELETE /my-data endpoints.
- Data minimisation: collect only what is needed for resolution.
  Phone for tracking. Location for ward routing. Nothing else.
- Social media scraping (when implemented):
  NEVER store usernames, profile photos, or any identifying info.
  Store only: issue_text + location_hint + source_url + scraped_at.

### IT Act 2000 + CERT-In 2022

- TLS 1.3 minimum on all endpoints. Enforce HTTPS redirect. HSTS header.
- AES-256 encryption at rest for sensitive fields.
- Logs retained for minimum 180 days.
- Cybersecurity incidents reported to CERT-In within 6 hours.
- All API keys in environment variables. Never committed to git. Ever.

### IT (Intermediary) Rules 2021

- NEVER auto-post anything to social media. Zero exceptions.
- Every announcement goes: draft → officer approves → then and only then public.
- The approved field on announcements table must be TRUE before any
  public endpoint returns that announcement. Enforce at query level.
- Audit log entry on every draft and every approval action.

### DoPT Grievance Guidelines 2014

- Acknowledge complaints within 3 days.
  (SMS with ticket_code on creation counts as acknowledgment.)
- 30-day resolution target minimum. Our SLAs are stricter — this is the legal floor.
- Every ticket must have a unique reference number (ticket_code).

### RPwD Act 2016 (Accessibility)

- WCAG 2.1 AA compliance on both Next.js dashboards.
- Run axe-core during development and fix all critical/serious violations.
- High contrast mode toggle on public dashboard.
- Keyboard navigation fully functional on all interactive elements.
- All images have descriptive alt text.

### Audit Log Immutability

- audit_log table: no UPDATE endpoint, no DELETE endpoint. Write-only.
- Add PostgreSQL rule to physically block DELETE on audit_log.
- This is the tamper-proof accountability trail.
- Every ticket status change, every priority override, every approval,
  every announcement approval must write to audit_log.

---

## WHAT NOT TO DO

- DO NOT use 'any' type in TypeScript. Ever.
- DO NOT fetch data directly in components. Use React Query hooks.
- DO NOT store JWT in localStorage. Memory + httpOnly cookie only.
- DO NOT use Zustand. React Query for server state, useState for local UI state.
- DO NOT let AI auto-post anything to social media. Always human approval.
- DO NOT use Gemini for sentiment analysis. Use HuggingFace RoBERTa.
- DO NOT store social media usernames or personal profiles from scraping.
- DO NOT skip confidence threshold check. < 0.75 must trigger clarification.
- DO NOT allow Ward Officers to query other wards' data. Enforce at SQL level.
- DO NOT add a DELETE endpoint to audit_log. It is write-only by design.
- DO NOT let the Commissioner override priority without logging to audit_log.
- DO NOT implement Vomyra or any scraper yet. Keep as provision only.
- DO NOT use MCP protocol for anything in this project.
- DO NOT commit API keys or .env files to git. Use .gitignore strictly.
- DO NOT implement branches. Commit to main. Keep it simple.
- DO NOT use graph database. All relationships via PostgreSQL junction tables.

---

## PROVISION STUBS (things not implemented yet — keep folders and READMEs)

### Voice AI — Vomyra (backend/app/voice/README.md)

When implemented, this module must:

- Receive an inbound phone call from a citizen
- Conduct a multilingual conversation (Tamil, Hindi, Telugu, English minimum)
- Ask: what is the issue, where is it located, how long has it been a problem,
  is there a safety risk
- Extract structured data: issue_type, location_text, severity_signals, language
- POST to our internal /api/complaints/create-from-voice endpoint
- Confirm to the caller: ticket number + expected response time
- Currently researching: vomyra.com — Indian language voice AI, free tier

### Social Media Scraping (backend/app/scrapers/README.md)

When implemented, scraping must cover:

- Reddit (r/Chennai, r/mumbai, r/bangalore, r/hyderabad, r/india)
- Twitter/X (city + civic keywords)
- YouTube (civic complaint videos in Indian cities)
- Local news websites (Times of India, The Hindu, local municipal news)
  Run on schedule: every 15–30 min depending on platform.
  All raw data → MongoDB. Classified tickets → PostgreSQL.
  Only public posts. No PII. Confidence threshold applies same as other sources.
  Scraping library and approach to be decided — do not start implementing.

---

## QUICK REFERENCE — ALL EXTERNAL SERVICES

| Service           | Purpose                  | Free Tier              | Env Variable                                                                       |
| ----------------- | ------------------------ | ---------------------- | ---------------------------------------------------------------------------------- |
| Google Gemini API | LLM (Flash + Pro models) | Free with limits       | GEMINI_API_KEY                                                                     |
| Sarvam AI         | Indian STT + TTS (voice) | Free trial             | SARVAM_API_KEY                                                                     |
| Vomyra            | AI voice call agent      | Free tier (TBD)        | VOMYRA_API_KEY                                                                     |
| Twilio            | WhatsApp + Voice + SMS   | $15 trial credit       | TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER, TWILIO_WHATSAPP_NUMBER |
| Google Maps API   | Geocoding + maps         | $200/month free credit | GOOGLE_MAPS_API_KEY, NEXT_PUBLIC_GOOGLE_MAPS_KEY                                   |
| MSG91             | Indian SMS delivery      | Free tier              | MSG91_API_KEY                                                                      |
| SendGrid          | Email reports            | 100 emails/day free    | SENDGRID_API_KEY                                                                   |
| Polygon           | Blockchain audit hashes  | Free testnet           | POLYGON_RPC_URL, POLYGON_PRIVATE_<br />KEY, POLYGON_CONTRACT_ADDRESS               |

### Local .env Template

# LLM

GEMINI_API_KEY=

# Voice

SARVAM_API_KEY=
VOMYRA_API_KEY=

# Comms

TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=
TWILIO_WHATSAPP_NUMBER=
MSG91_API_KEY=
SENDGRID_API_KEY=

# Maps

GOOGLE_MAPS_API_KEY=
NEXT_PUBLIC_GOOGLE_MAPS_KEY=

# Databases

DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/civicai
MONGODB_URI=mongodb://localhost:27017/civicai
REDIS_URL=redis://localhost:6379

# Blockchain

POLYGON_RPC_URL=
POLYGON_PRIVATE_KEY=
POLYGON_CONTRACT_ADDRESS=

# Auth

JWT_SECRET_KEY=
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=480

# App

ENVIRONMENT=development





**---

## API CONTRACTS — ALL ENDPOINTS

These are the agreed interfaces between frontend and backend.

If you need to change any signature, update this section and tell the team first.

Frontend builds against these. Backend implements these. No surprises.

### Public Endpoints (no auth required)

GET  /api/public/stats

    → { total_tickets, resolved_pct, avg_resolution_hours, active_critical,

    active_high, last_updated }

    Cache: Redis dashboard_stats, 5-min TTL

GET  /api/public/wards/leaderboard

    → [{ ward_id, ward_name, score, rank, sla_compliance_pct,

    avg_resolution_days, total_tickets_month }]

    Cache: Redis ticket_leaderboard, 15-min TTL

GET  /api/public/heatmap

    → [{ ticket_id, lat, lng, dept_id, priority_label, status }]

    Query params: dept_id (optional), status (optional), days (default 30)

    Cache: Redis heatmap_data, 10-min TTL

GET  /api/public/track

    Query params: ticket_code OR phone (one required)

    → { ticket_code, status, dept_name, priority_label, created_at,

    sla_deadline, assigned_officer_name, before_photo_url,

    after_photo_url, audit_timeline: [{ action, timestamp }] }

    Note: phone lookup shows ALL tickets for that phone. Verify via OTP

    before returning (DPDP — only show citizen their own data).

    No cache — must be live.

GET  /api/public/resolutions

    → [{ ticket_code, ward_name, dept_name, description_summary,

    before_photo_url, after_photo_url, resolved_at, resolution_hours }]

    Query params: page, limit (default 20)

    Cache: Redis recent_resolutions, 5-min TTL

GET  /api/public/departments

    → [{ dept_id, dept_name, tickets_this_month, resolved_pct,

    avg_resolution_days, best_ward, worst_ward }]

    Cache: Redis dept_performance, 15-min TTL

GET  /api/public/announcements

    → [{ id, title, body, announcement_type, published_at }]

    WHERE approved = TRUE only. Never return unapproved.

    Cache: Redis announcements, 10-min TTL

POST /api/public/complaints

    Body: { description, dept_id (optional), location_text, lat (optional),

    lng (optional), photo_base64 (optional), reporter_phone,

    reporter_name (optional), language (optional),

    consent_given: true }

    → { ticket_code, status, sla_deadline, dept_name, message }

    Note: consent_given must be TRUE. Reject if FALSE. No exceptions.

    Triggers: AI classify → DB insert → SMS confirm → WhatsApp officer alert

POST /api/public/complaints/classify-preview

    Body: { description, language (optional) }

    → { dept_id, dept_name, issue_summary, confidence, needs_clarification,

    clarification_question }

    Use this for live preview while citizen is typing before submit.

GET  /api/public/wards/{ward_id}/details

    → { ward_name, councillor_name, ward_officer_name, stats, top_issues[] }

### Officer Auth Endpoints

POST /api/auth/login

    Body: { phone OR email, password }

    → { access_token, role, ward_id, zone_id, dept_id, name }

    Sets httpOnly refresh_token cookie.

POST /api/auth/refresh

    Reads httpOnly cookie.

    → { access_token }

POST /api/auth/logout

    Invalidates session in Redis.

    Clears httpOnly cookie.

### Officer Ticket Endpoints (auth required — all)

GET  /api/officer/tickets

    → paginated list filtered by caller's role + ward/zone/dept automatically

    Query params: status, priority_label, dept_id, page, limit, sort

    Sort options: priority_score (default), created_at, sla_deadline

    Note: backend applies ward/zone/dept filter from JWT claims — no

    frontend filter param needed for scoping. Security enforced at SQL level.

GET  /api/officer/tickets/{id}

    → full ticket detail + audit_log timeline + dependencies + photos

PATCH /api/officer/tickets/{id}/status

    Body: { action, target_dept_id (if rerouting), note }

    Actions: ACCEPT | REROUTE | CLARIFY | ESCALATE | MARK_COMPLETE

    Every action writes to audit_log. No exceptions.

POST /api/officer/tickets/{id}/depends-on

    Body: { depends_on_ticket_id, dependency_type }

    → creates ticket_dependencies record

POST /api/officer/tickets/{id}/approve-budget

    Body: { estimated_cost, approval_note }

    Validates caller role against approval_rules table.

    Writes to audit_log.

POST /api/officer/tickets/{id}/override-priority

    Body: { new_priority_score, override_reason }

    COMMISSIONER role only. Enforced at API level.

    Writes to audit_log with old_value and new_value.

GET  /api/officer/queue

    → same as GET /tickets but pre-sorted by priority_score DESC

    WebSocket version: ws://host/ws/officer/queue/{ward_id}

    Sends new ticket events as they arrive.

### Officer Dashboard Endpoints

GET  /api/officer/sentiment/{ward_id}

    → { ward_id, last_7_days: [{ date, positive_pct, negative_pct,

    neutral_pct, total_posts }], current_mood, spike_alert: bool,

    top_issues: [] }

GET  /api/officer/misinformation

    → [{ id, post_url, platform, claim_text, evidence_tickets[],

    draft_rebuttal, flagged_at, status }]

    Where status = PENDING_REVIEW

POST /api/officer/misinformation/{id}/approve

    Body: { edited_rebuttal (optional) }

    Sets approved = TRUE. Writes to audit_log.

    Does NOT auto-post. Just marks as approved for officer to post manually.

POST /api/officer/misinformation/{id}/dismiss

    Body: { dismiss_reason }

GET  /api/officer/sla/dashboard

    → { breached: [], at_risk: [], on_track: [], ward_ranking: [] }

GET  /api/officer/performance

    Role-aware: Ward Officer sees their stats.

    Zonal sees zone. Dept Head sees dept. Commissioner sees all.

    → { sla_compliance_pct, avg_resolution_hours, satisfaction_avg,

    tickets_resolved_month, tickets_overdue }

GET  /api/officer/predictions

    COMMISSIONER only.

    → [{ ward_id, ward_name, current_score, predicted_score,

    risk_level, ai_recommendation, computed_at }]

### Report Generation

POST /api/officer/reports/generate

    Body: { report_type, ward_id (if ward report), month, year }

    report_type: WARD_COMMITTEE | STANDING_COMMITTEE | COMMISSIONER | CAG_AUDIT

    → { report_url, generated_at }

    Async — Celery task. Poll status or use WebSocket for completion.

GET  /api/officer/reports/history

    → [{ report_type, ward_id, month, year, url, generated_at }]

### Announcements

GET  /api/officer/announcements/drafts

    → all unapproved announcements (for approvers)

POST /api/officer/announcements

    Body: { title, body, announcement_type, related_ticket_id (optional) }

    Creates draft. Does NOT publish.

POST /api/officer/announcements/{id}/approve

    Requires role: ZONAL_OFFICER or above.

    Sets approved = TRUE, published_at = NOW().

    Writes to audit_log.

    Only now does GET /api/public/announcements return this item.

### Webhook Endpoints (Twilio — no user auth, validate Twilio signature)

POST /api/webhooks/whatsapp/inbound

    Receives citizen complaint via WhatsApp.

    Runs classification → creates ticket → sends confirmation reply.

POST /api/webhooks/voice/inbound

    Provision stub. Returns TwiML for now.

    Full implementation when Vomyra integration is figured out.

POST /api/webhooks/ivr/callback

    Receives citizen button press after ticket closure.

    Body (from Twilio): { ticket_code, Digits }

    Digits: 1 = fixed, 2 = partially fixed, 3 = not fixed

    1 → CLOSED + satisfaction=5 + blockchain hash

    2 → CLOSED_UNVERIFIED + flag for officer review

    3 → REOPENED + escalate to Zonal Officer

---

## CELERY SCHEDULED JOBS

All jobs defined in backend/app/celery_schedule.py.

```python

CELERYBEAT_SCHEDULE = {


    # SLA ENGINE — every 5 minutes

    # Checks all open tickets against sla_deadline

    # Recalculates priority_score for time-decay factor

    # Triggers escalation if SLA breached and status still OPEN

    # Sends WhatsApp alert to Zonal Officer on breach

    'sla_check': {

        'task': 'app.services.sla.run_sla_check',

        'schedule': crontab(minute='*/5'),

    },


    # SENTIMENT REFRESH — every 15 minutes

    # Pulls recent posts from MongoDB

    # Runs HuggingFace RoBERTa sentiment pipeline

    # Updates Redis ward_sentiment_cache

    # Checks for negative spike vs last week — sets alert flag

    'sentiment_refresh': {

        'task': 'app.services.sentiment.refresh_all_wards',

        'schedule': crontab(minute='*/15'),

    },


    # DASHBOARD STATS REFRESH — every 5 minutes

    # Recomputes city-wide stats from PostgreSQL

    # Writes to Redis dashboard_stats

    # Pushes update to WebSocket subscribers

    'dashboard_stats_refresh': {

        'task': 'app.services.stats.refresh_city_stats',

        'schedule': crontab(minute='*/5'),

    },


    # WARD LEADERBOARD REFRESH — every 15 minutes

    # Recomputes ward performance scores

    # Writes to Redis ticket_leaderboard

    'leaderboard_refresh': {

        'task': 'app.services.leaderboard.refresh_rankings',

        'schedule': crontab(minute='*/15'),

    },


    # ML PREDICTION — daily at midnight

    # Loads RandomForest model from file storage

    # Runs prediction on all active wards

    # Writes to ward_predictions table

    # Generates AI recommendation text via Gemini Flash

    'ml_prediction': {

        'task': 'app.ml.predictor.run_daily_prediction',

        'schedule': crontab(hour=0, minute=0),

    },


    # UNRESPONDED TICKET ESCALATION — every hour

    # Finds tickets in OPEN status for more than 24 hours with no action

    # Auto-escalates to Zonal Officer

    # Writes escalation event to audit_log

    'auto_escalation': {

        'task': 'app.services.escalation.run_auto_escalation',

        'schedule': crontab(minute=0),

    },


    # SCRAPER PROVISION — schedule defined, tasks not implemented yet

    # Do not remove these — they are placeholders for future implementation

    # 'reddit_scraper': {

    #     'task': 'app.scrapers.reddit.run_scrape',

    #     'schedule': crontab(minute='*/15'),

    # },

    # 'youtube_scraper': {

    #     'task': 'app.scrapers.youtube.run_scrape',

    #     'schedule': crontab(minute='*/30'),

    # },

    # 'news_scraper': {

    #     'task': 'app.scrapers.news.run_scrape',

    #     'schedule': crontab(minute='*/30'),

    # },

}

```

---

## REDIS CACHE KEYS — FULL REFERENCE

All cache keys follow pattern: {scope}:{identifier}

All TTLs are set explicitly on write. Never rely on Redis default.

dashboard_stats → dict, TTL 300s (5 min) ticket_leaderboard → list of ward dicts, TTL 900s (15 min) heatmap_data → list of coordinate dicts, TTL 600s (10 min) recent_resolutions → list of closed ticket summaries, TTL 300s dept_performance → list of dept stats, TTL 900s announcements → list of approved announcements, TTL 600s

ward_sentiment_cache:{ward_id} → sentiment dict, TTL 900s (15 min) ward_queue:{ward_id} → sorted ticket list for officer queue, TTL 60s ward_predictions:{ward_id} → ML prediction dict, TTL 86400s (24 hrs) pending_approvals:{officer_id} → list, TTL 300s

officer_session:{token_hash} → user dict, TTL 28800s (8 hrs) rate_limit:{ip_address} → request count, TTL 60s (1 min window) rate_limit:officer:{user_id} → request count, TTL 60s

whatsapp_state:{phone_number} → conversation context dict, TTL 1800s (30 min) otp:{phone_number} → 6-digit code, TTL 300s (5 min, single-use)

---

## MONGODB COLLECTIONS

### raw_social_posts (when scraping is implemented)

```json

{

  "_id": "ObjectId",

  "platform": "REDDIT | TWITTER | YOUTUBE | NEWS",

  "post_id": "platform-specific ID for deduplication",

  "text": "issue description text only",

  "location_hint": "location text extracted from post",

  "source_url": "direct URL to original post",

  "scraped_at": "ISODate",

  "processed": false,

  "processing_result": {

    "dept_id": "D04",

    "confidence": 0.88,

    "ticket_created": true,

    "ticket_id": 4827,

    "processed_at": "ISODate"

  }

}

// NEVER store: username, profile_url, avatar, follower_count, user_id

// Strip all PII before insert. Store issue content + source URL only.

```

### sentiment_snapshots

```json

{

  "_id": "ObjectId",

  "ward_id": 12,

  "snapshot_at": "ISODate",

  "positive_pct": 42.1,

  "negative_pct": 38.6,

  "neutral_pct": 19.3,

  "total_posts_analysed": 87,

  "top_negative_keywords": ["waterlogging", "no light", "garbage"],

  "spike_alert": true,

  "spike_vs_last_week_pct": 23.4

}

```

### misinformation_flags

```json

{

  "_id": "ObjectId",

  "platform": "TWITTER",

  "post_url": "https://...",

  "claim_text": "Corporation has done nothing about the sewer for 3 months",

  "evidence_ticket_ids": [4821, 4822],

  "evidence_summary": "Ticket D04-Ward12 created 6 days ago, assigned within 2 hrs, in progress",

  "draft_rebuttal": "The drainage issue on Anna Salai was reported on Nov 14...",

  "flagged_at": "ISODate",

  "status": "PENDING_REVIEW | APPROVED | DISMISSED",

  "reviewed_by_officer_id": null,

  "reviewed_at": null

}

```

---

## NOTIFICATION FLOWS — COMPLETE

### Flow 1: Citizen submits complaint (web portal or WhatsApp)

1. POST /api/public/complaints received
2. AI classifies → dept_id, confidence, priority_score
3. Insert into tickets table → ticket_code generated
4. Write blockchain hash: SHA256(ticket_id + dept_id + ward_id + created_at)
5. Write audit_log: action=TICKET_CREATED
6. SMS to citizen (MSG91): "Your complaint [ticket_code] has been registered. Dept: {dept_name}. Expected resolution: {sla_deadline}. Track at civic.gov.in/track"
7. WhatsApp to Ward Officer (Twilio): "🔴 NEW TICKET [{priority_label}] Code: {ticket_code} Issue: {issue_summary} Ward: {ward_name} Dept: {dept_name} Priority Score: {priority_score}/100 SLA Deadline: {sla_deadline} Reply: ACCEPT {ticket_code} | REROUTE {ticket_code} {new_dept_id}"
8. Push new ticket event via WebSocket to officer dashboard queue

### Flow 2: Officer accepts via WhatsApp

1. Officer replies: "ACCEPT CIV-2025-04872"
2. POST /api/webhooks/whatsapp/inbound received
3. Parse command → find ticket by code → validate officer's ward matches
4. Update ticket status: OPEN → ASSIGNED, assigned_officer_id, assigned_at
5. Write audit_log: action=TICKET_ACCEPTED, actor_id=officer
6. SMS to citizen: "Your complaint {ticket_code} has been accepted by {dept_name} team. Work will begin within {sla_days} days."
7. WhatsApp confirmation to officer: "✅ Ticket {ticket_code} accepted. Remember to assign a technician before {sla_deadline}."

### Flow 3: Ticket marked complete → dual verification

1. Officer marks complete via dashboard: PATCH /tickets/{id}/status Body: { action: MARK_COMPLETE }
2. Status → PENDING_VERIFICATION
3. Before photo + after photo must be present. Reject if missing.
4. Celery task: run Claude Vision verify_work_completion(before, after, issue_type) 5a. If AI confidence >= 0.85 and work_completed = true: → Trigger outbound IVR call to citizen via Twilio Voice → TTS: "Your complaint {ticket_code} about {issue_summary} has been marked resolved. Press 1 if the issue is fixed. Press 2 if partially fixed. Press 3 if not fixed." 5b. If AI confidence < 0.85 or work_completed = false: → Flag for officer human review → WhatsApp to Zonal Officer: "Photo verification inconclusive for {ticket_code}. Please review manually."

### Flow 4: Citizen IVR response

POST /api/webhooks/ivr/callback Twilio sends: ticket_code (from URL param) + Digits (1, 2, or 3)

Digit 1 (Fixed): → status = CLOSED, citizen_satisfaction = 5 → Blockchain hash: SHA256(ticket_id + CLOSED + citizen_confirmed + timestamp) → Write audit_log: action=CITIZEN_CONFIRMED_FIXED → SMS to citizen: "Thank you! We're glad the issue is resolved. Rate us at civic.gov.in/track"

Digit 2 (Partially fixed): → status = CLOSED_UNVERIFIED → Flag for officer review → WhatsApp to Ward Officer: "Citizen reports partial fix for {ticket_code}"

Digit 3 (Not fixed): → status = REOPENED → priority_score += 10 (escalate urgency) → Escalate to Zonal Officer automatically → WhatsApp to Zonal Officer: "🚨 Citizen disputes resolution for {ticket_code}. Was assigned to {officer_name}. Needs immediate review." → Write audit_log: action=CITIZEN_DISPUTED_RESOLUTION

No response within 48 hours: → status = CLOSED_UNVERIFIED → Write audit_log: action=IVR_TIMEOUT_CLOSED

### Flow 5: SLA breach

Celery SLA check job runs every 5 minutes. If ticket.sla_deadline < NOW() and status not in (CLOSED, CLOSED_UNVERIFIED): → Write audit_log: action=SLA_BREACHED → WhatsApp to Ward Officer: "⚠️ SLA BREACHED: {ticket_code} was due {hours}hrs ago" → WhatsApp to Zonal Officer: "SLA breach in your zone: {ticket_code}, Ward {ward_name}" → priority_score recalculated (SLA factor now maxes at 15 pts) → If status = OPEN (not even accepted) and breached > 24hrs: → Auto-escalate: status = ASSIGNED, assigned to Zonal Officer → Write audit_log: action=AUTO_ESCALATED_SLA_BREACH

---

## PDF REPORTS — SPECS

All reports generated by WeasyPrint from Jinja2 HTML templates.

Stored in file storage. Emailed via SendGrid.

One-click generation from officer dashboard.

### Ward Committee Monthly Report

Generated for: Ward Officer, Councillor Sections:

1. Ward summary: total tickets, resolved%, pending, SLA compliance
2. Category breakdown: D01–D14 ticket count + resolution rate table
3. Top 10 resolved issues this month (with before/after photos, dates)
4. Top 5 pending high-priority issues (with ticket code, days pending)
5. Citizen satisfaction avg (from IVR responses)
6. Comparison vs last month (arrows: up/down/same)
7. Ward ranking among all wards this month
8. Officer signature block

### Standing Committee Comparative Report

Generated for: Commissioner, Standing Committee members Sections:

1. City-wide overview: all KPIs
2. All ward performance comparison table (ranked)
3. Department performance comparison table
4. Budget utilisation by dept and zone
5. Escalations this month: list with reasons
6. Red flags: wards/depts in critical underperformance
7. Top 5 resolved projects (impact summary)
8. Pending work >30 days: full list with responsible officer

### Commissioner Executive Summary

Generated for: Commissioner Sections:

1. City health score: single composite index (0–100)
2. Week-over-week trend spark line
3. Predictive alerts: wards at risk next month (from ML)
4. AI-generated strategic recommendations (Gemini Pro)
5. Inter-departmental bottlenecks identified
6. Citizen sentiment citywide (trend chart)
7. CPGRAMS escalation status

### CAG Annual Audit Report

Generated for: Audit purposes, state government Sections:

1. Full 12-month ticket data summary
2. SLA compliance proof (month-by-month table)
3. Budget sanction and utilisation audit trail
4. Blockchain hash verification table (sample audit entries)
5. Grievance redressal effectiveness metrics
6. Citizen satisfaction data
7. All escalation records with resolutions
8. Appendix: data extraction methodology, tamper-proof evidence explanation Note: every figure in this report must have a direct query reference so auditors can independently verify from the database.

---

## DOCKER COMPOSE — LOCAL DEVELOPMENT

```yaml

# infra/docker-compose.yml

version: '3.9'


services:

  postgres:

    image: postgis/postgis:15-3.4

    environment:

      POSTGRES_USER: civicai

      POSTGRES_PASSWORD: civicai_local

      POSTGRES_DB: civicai

    ports:

      - "5432:5432"

    volumes:

      - postgres_data:/var/lib/postgresql/data


  redis:

    image: redis:7-alpine

    ports:

      - "6379:6379"

    command: redis-server --save 60 1


  mongodb:

    image: mongo:7

    ports:

      - "27017:27017"

    volumes:

      - mongo_data:/data/db


  backend:

    build: ./backend

    ports:

      - "8000:8000"

    env_file: ./backend/.env

    depends_on:

      - postgres

      - redis

      - mongodb

    volumes:

      - ./backend:/app

    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload


  celery_worker:

    build: ./backend

    env_file: ./backend/.env

    depends_on:

      - postgres

      - redis

      - mongodb

    volumes:

      - ./backend:/app

    command: celery -A app.celery_app worker --loglevel=info


  celery_beat:

    build: ./backend

    env_file: ./backend/.env

    depends_on:

      - postgres

      - redis

    volumes:

      - ./backend:/app

    command: celery -A app.celery_app beat --loglevel=info


  frontend:

    build: ./frontend

    ports:

      - "3000:3000"

    env_file: ./frontend/.env.local

    volumes:

      - ./frontend:/app

      - /app/node_modules

    command: npm run dev


volumes:

  postgres_data:

  mongo_data:

```

### How to run locally

```bash

# First time setup

cp backend/.env.example backend/.env       # fill in your API keys

cp frontend/.env.example frontend/.env.local


# Start everything

docker compose -f infra/docker-compose.yml up -d


# Run DB migrations

docker compose exec backend alembic upgrade head


# Seed department data

docker compose exec backend python -m app.scripts.seed_departments


# Expose local backend for Twilio webhooks

ngrok http 8000

# Copy the ngrok HTTPS URL → set in Twilio console as webhook URL


# View logs

docker compose logs -f backend

docker compose logs -f celery_worker


# Stop everything

docker compose -f infra/docker-compose.yml down

```

---

## ERROR HANDLING PATTERNS

### Backend (FastAPI)

```python

# Use custom exception classes, not raw HTTPException everywhere

# backend/app/core/exceptions.py


class TicketNotFoundError(Exception): pass

class InsufficientRoleError(Exception): pass

class ClassificationConfidenceTooLow(Exception): pass

class ConsentNotGiven(Exception): pass

class DuplicateTicketDetected(Exception): pass


# Global exception handler in main.py:

@app.exception_handler(InsufficientRoleError)

async def role_error_handler(request, exc):

    return JSONResponse(status_code=403,

        content={"error": "INSUFFICIENT_ROLE", "message": str(exc)})


@app.exception_handler(ConsentNotGiven)

async def consent_error_handler(request, exc):

    return JSONResponse(status_code=422,

        content={"error": "CONSENT_REQUIRED",

                 "message": "Consent must be given before submitting."})


# All errors must return:

# { "error": "ERROR_CODE", "message": "human readable", "detail": {} }

# Never expose stack traces to client in production.

```

### Frontend (Next.js)

```typescript

// All API calls wrapped in React Query.

// Error states handled in UI — never silent failures.


// Pattern for mutation with error toast:

const submitComplaint = useMutation({

  mutationFn: (data: ComplaintFormData) => api.submitComplaint(data),

  onSuccess: (response) => {

    // Show ticket code to citizen

    setSubmittedTicketCode(response.ticket_code)

  },

  onError: (error: ApiError) => {

    if (error.code === 'CONSENT_REQUIRED') {

      // Scroll to consent checkbox, highlight it

    } else if (error.code === 'CLASSIFICATION_LOW_CONFIDENCE') {

      // Show clarification question from error.detail.clarification_question

    } else {

      // Generic error toast

      toast.error('Something went wrong. Please try again.')

    }

  }

})


// TypeScript error type:

interface ApiError {

  error: string      // error code

  message: string    // human readable

  detail?: Record<string, unknown>

}

```

### AI Chain Error Handling

```python

# LangChain chains can fail — always wrap in try/except with fallback

async def classify_complaint_safe(text: str) -> TicketClassification:

    try:

        result = await classify_chain.ainvoke({

            "complaint_text": text,

            "format_instructions": parser.get_format_instructions()

        })

        return result

    except OutputParserException:

        # Gemini returned malformed JSON — retry once with more explicit prompt

        try:

            result = await classify_chain_strict.ainvoke({"complaint_text": text, ...})

            return result

        except Exception:

            # Both attempts failed — flag for human review

            return TicketClassification(

                dept_id="D01",           # safe default

                confidence=0.0,

                needs_clarification=False,

                requires_human_review=True,  # always set True on failure

                issue_summary=text[:200]

            )

    except Exception as e:

        logger.error(f"Classification failed: {e}")

        raise ClassificationServiceError(str(e))

```

---

## BLOCKCHAIN AUDIT — WHAT GETS HASHED

Using web3.py + Polygon. Only SHA-256 hashes. No PII ever on-chain.

```python

import hashlib, json

from web3 import Web3


w3 = Web3(Web3.HTTPProvider(settings.POLYGON_RPC_URL))


def create_ticket_hash(ticket_id: int, dept_id: str,

                        ward_id: int, created_at: str) -> str:

    data = json.dumps({

        "ticket_id": ticket_id,

        "dept_id": dept_id,

        "ward_id": ward_id,

        "created_at": created_at

    }, sort_keys=True)

    return hashlib.sha256(data.encode()).hexdigest()


def create_status_transition_hash(ticket_id: int, old_status: str,

                                   new_status: str, actor_id: int,

                                   timestamp: str) -> str:

    data = json.dumps({

        "ticket_id": ticket_id,

        "old_status": old_status,

        "new_status": new_status,

        "actor_id": actor_id,

        "timestamp": timestamp

    }, sort_keys=True)

    return hashlib.sha256(data.encode()).hexdigest()


def create_photo_evidence_hash(before_photo_bytes: bytes,

                                after_photo_bytes: bytes) -> str:

    before_hash = hashlib.sha256(before_photo_bytes).hexdigest()

    after_hash = hashlib.sha256(after_photo_bytes).hexdigest()

    combined = hashlib.sha256(f"{before_hash}{after_hash}".encode()).hexdigest()

    return combined


def create_citizen_verification_hash(ticket_id: int,

                                      citizen_response: str,

                                      call_timestamp: str) -> str:

    data = json.dumps({

        "ticket_id": ticket_id,

        "response": citizen_response,   # "FIXED" | "PARTIAL" | "NOT_FIXED"

        "timestamp": call_timestamp

    }, sort_keys=True)

    return hashlib.sha256(data.encode()).hexdigest()


# Hash is stored in: audit_log.new_value as { "blockchain_hash": "0x..." }

# Also written to Polygon smart contract (one transaction per hash)

# Smart contract stores: hash + block_number + timestamp

# Verifiable independently by anyone with the hash

```

---

## PRIORITY SCORING — SEVERITY MAP

```python

# Hardcoded severity base scores by issue subcategory

# Do not let AI determine these. Fixed values only.


SEVERITY_MAP = {

    # D01 Electrical

    "street_light_out": 15,

    "multiple_lights_out": 22,

    "electrical_spark_hazard": 30,      # safety → max severity


    # D02 Roads

    "small_pothole": 12,

    "large_pothole": 20,

    "road_collapse": 28,

    "bridge_crack": 30,


    # D03 Water

    "low_pressure": 14,

    "no_water_supply": 22,

    "dirty_water": 25,

    "burst_pipe_flooding": 30,


    # D04 Sewerage

    "drain_blocked": 18,

    "sewage_overflow": 26,

    "open_manhole": 30,                 # safety → max severity


    # D05 Waste

    "missed_collection_once": 10,

    "overflowing_bin": 16,

    "dead_animal_carcass": 22,

    "illegal_dumping_large": 20,


    # D06 Health

    "mosquito_breeding": 18,

    "stray_dog_bite": 28,

    "disease_outbreak_concern": 30,


    # Default if subcategory not matched

    "default": 15,

}


# Safety keywords that add +5 bonus to severity base (max 30 total):

SAFETY_KEYWORDS = [

    "accident", "danger", "hazard", "fire", "electric shock",

    "child fell", "injury", "death", "hospital", "emergency",

    "flood", "collapse", "snake", "rabies", "epidemic"

]

```

---

## NEXT.JS ENVIRONMENT SETUP

```bash

# frontend/.env.local

NEXT_PUBLIC_API_URL=http://localhost:8000

NEXT_PUBLIC_GOOGLE_MAPS_KEY=          # safe to expose — domain-restricted in Maps console

NEXT_PUBLIC_APP_NAME=CivicAI

NEXT_PUBLIC_CITY_NAME=Chennai         # change per city deployment

NEXT_PUBLIC_WS_URL=ws://localhost:8000


# Never prefix with NEXT_PUBLIC_ if it's a secret:

# These are server-side only (used in API routes or server components):

GEMINI_API_KEY=                        # only if calling Gemini from Next.js server side

```

```typescript

// frontend/lib/api-client.ts

// All API calls go through this single client. Never use fetch() directly in components.


const API_BASE = process.env.NEXT_PUBLIC_API_URL


export const apiClient = {

  // Public

  getStats: () => fetch(`${API_BASE}/api/public/stats`).then(r => r.json()),

  getLeaderboard: () => fetch(`${API_BASE}/api/public/wards/leaderboard`).then(r => r.json()),

  trackComplaint: (code: string) =>

    fetch(`${API_BASE}/api/public/track?ticket_code=${code}`).then(r => r.json()),

  submitComplaint: (data: ComplaintFormData) =>

    fetch(`${API_BASE}/api/public/complaints`, {

      method: 'POST',

      headers: { 'Content-Type': 'application/json' },

      body: JSON.stringify(data)

    }).then(r => r.json()),


  // Officer (auth)

  getQueue: (token: string) =>

    fetch(`${API_BASE}/api/officer/queue`, {

      headers: { Authorization: `Bearer ${token}` }

    }).then(r => r.json()),


  updateTicketStatus: (id: number, action: string, token: string, extra = {}) =>

    fetch(`${API_BASE}/api/officer/tickets/${id}/status`, {

      method: 'PATCH',

      headers: {

        'Content-Type': 'application/json',

        Authorization: `Bearer ${token}`

      },

      body: JSON.stringify({ action, ...extra })

    }).then(r => r.json()),

}


// TypeScript interfaces in frontend/types/index.ts

// Define every API response shape. No unknown or any types.

```

---

## FINAL CHECKLIST BEFORE ANY FEATURE IS CALLED DONE

Before marking any feature complete, verify all of the following:

FUNCTIONALITY □ Does it work for the happy path? □ Does it handle the main error cases gracefully? □ Does the API return the correct HTTP status codes?

DATA INTEGRITY □ Is every state change written to audit_log? □ Is priority_score recalculated after any ticket field change? □ Are SLA deadlines set correctly on ticket creation?

COMPLIANCE □ Is consent checked before any PII is collected? □ Is RBAC enforced at the backend SQL query level (not just frontend)? □ Is there any path that could auto-post to social media? (Must be zero) □ Is PII excluded from any blockchain or MongoDB social collection? □ Are all API keys coming from environment variables, never hardcoded?

FRONTEND □ Is the loading state handled? (React Query isLoading) □ Is the error state handled and shown to user? □ Does it work on mobile screen size? □ Does it work without JavaScript disabled? (critical for public dashboard) □ Are all interactive elements keyboard-accessible?

NOTIFICATIONS □ Does the citizen get an SMS confirmation? □ Does the officer get a WhatsApp alert? □ Is the Twilio webhook response fast enough? (<3 seconds)

**
