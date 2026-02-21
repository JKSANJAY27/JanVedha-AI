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
