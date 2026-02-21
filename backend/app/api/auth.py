from fastapi import APIRouter

router = APIRouter()

@router.post("/login")
async def login():
    return {"token": "stub"}

@router.post("/refresh")
async def refresh():
    return {"token": "stub"}

@router.post("/logout")
async def logout():
    return {"status": "ok"}
