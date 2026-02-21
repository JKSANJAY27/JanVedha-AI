from fastapi import APIRouter

router = APIRouter()

@router.post("/ivr/callback")
async def ivr_callback():
    return {"status": "received"}

@router.post("/whatsapp/incoming")
async def whatsapp_incoming():
    return {"status": "received"}
