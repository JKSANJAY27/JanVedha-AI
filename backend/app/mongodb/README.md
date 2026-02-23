# MongoDB Module — Integration Guide

This folder (`backend/app/mongodb/`) is a **fully isolated**, **non-breaking** MongoDB layer that mirrors the existing SQLite/SQLAlchemy schema. Nothing in this folder is imported by the running application until you explicitly wire it up.

## Tech Stack

| Layer | Library | Purpose |
|-------|---------|---------|
| Driver | [Motor](https://motor.readthedocs.io/) | Async MongoDB driver (built on PyMongo) |
| ODM | [Beanie](https://beanie-odm.dev/) | Pydantic-based async ODM on top of Motor |
| Config | Existing `app/core/config.py` | `MONGODB_URI` already defined there |

---

## Folder Structure

```
mongodb/
├── __init__.py
├── database.py              ← Motor client + Beanie initialisation
├── README.md                ← this file
├── models/
│   ├── __init__.py
│   ├── user.py              ← UserMongo       (mirrors User)
│   ├── ticket.py            ← TicketMongo     (mirrors Ticket)
│   ├── department.py        ← DepartmentMongo (mirrors Department)
│   ├── announcement.py      ← AnnouncementMongo
│   ├── audit_log.py         ← AuditLogMongo   (append-only)
│   ├── ward_dept_officer.py ← WardDeptOfficerMongo
│   └── ward_prediction.py   ← WardPredictionMongo
├── repositories/
│   ├── __init__.py
│   ├── ticket_repo.py       ← TicketRepo
│   ├── user_repo.py         ← UserRepo
│   ├── department_repo.py   ← DepartmentRepo
│   ├── announcement_repo.py ← AnnouncementRepo
│   └── audit_repo.py        ← AuditRepo (write-only)
└── services/
    ├── __init__.py
    ├── ticket_service.py    ← MongoTicketService
    ├── auth_service.py      ← MongoAuthService
    └── stats_service.py     ← MongoStatsService
```

---

## Step-by-Step Integration

### 1. Install dependencies

```bash
pip install motor beanie
```

Add to `requirements.txt`:
```
motor>=3.3.0
beanie>=1.24.0
```

### 2. Set MongoDB URI in `.env`

The variable already exists in `config.py`. Just set it in your `.env`:

```env
MONGODB_URI=mongodb://localhost:27017/civicai
# or for Atlas:
# MONGODB_URI=mongodb+srv://<user>:<pass>@cluster.mongodb.net/civicai
```

### 3. Initialise Beanie at app startup

In `backend/app/main.py`, add the lifespan hook:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.mongodb.database import init_mongodb, close_mongodb

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_mongodb()   # ← connects Motor + registers Beanie documents
    yield
    await close_mongodb()  # ← closes connection pool on shutdown

app = FastAPI(lifespan=lifespan)
```

### 4. Swap dependencies in your API routes

Replace the SQLAlchemy `Depends(get_db)` pattern with the MongoDB services:

**Before (SQLite):**
```python
from app.services.ticket_service import TicketService
from app.core.database import get_db

@router.post("/tickets")
async def create_ticket(payload: ..., db: AsyncSession = Depends(get_db)):
    return await TicketService.create_ticket(db, ...)
```

**After (MongoDB):**
```python
from app.mongodb.services.ticket_service import MongoTicketService

@router.post("/tickets")
async def create_ticket(payload: ...):
    return await MongoTicketService.create_ticket(...)
```

### 5. Swap the auth dependency

Replace `app/core/dependencies.get_current_user` with:

```python
from app.mongodb.services.auth_service import MongoAuthService

async def get_current_user_mongo(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UserMongo:
    return await MongoAuthService.get_current_user(credentials.credentials)
```

---

## Key Design Decisions

### IDs
- SQLite used integer auto-increment PKs → MongoDB uses `PydanticObjectId` (`_id`)
- When referencing related documents (e.g. `assigned_officer_id`) the field stores the ObjectId **as a string** for simplicity and JSON compatibility

### Geospatial
- `TicketMongo.location` stores a **GeoJSON Point** `{"type":"Point","coordinates":[lng,lat]}`
- A `2dsphere` index is declared — enables `$near`, `$geoWithin` queries out of the box
- `coordinates` (raw string) is kept for backwards parity if needed

### Audit Log Immutability
- `AuditRepo` intentionally exposes **no `update` or `delete` methods**
- This mirrors the `# NO update. NO delete. Ever.` comment in the SQLite model

### Department ID
- `DepartmentMongo.dept_id` is a string natural key (e.g. `"PWD"`) indexed as unique
- Stored as a regular field (NOT as `_id`) so Beanie's ObjectId `_id` remains consistent

### WardDeptOfficer
- SQLite used a composite PK `(ward_id, dept_id)` — replicated as a **compound unique index** in MongoDB

---

## Running MongoDB Locally

Using Docker (quickest):

```bash
docker run -d -p 27017:27017 --name civicai-mongo mongo:7
```

Or install [MongoDB Community Edition](https://www.mongodb.com/try/download/community) directly.
