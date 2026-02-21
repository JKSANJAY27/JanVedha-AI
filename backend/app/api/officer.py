from fastapi import APIRouter

router = APIRouter()

@router.get("/tickets")
async def get_tickets():
    return []

@router.get("/tickets/{id}")
async def get_ticket(id: int):
    return {"id": id, "status": "OPEN", "priority_score": 0.0}

@router.patch("/tickets/{id}/status")
async def update_status(id: int):
    return {"id": id, "status": "ASSIGNED"}

@router.post("/tickets/{id}/approve-budget")
async def approve_budget(id: int):
    return {"id": id, "budget_approved": True}

@router.post("/tickets/{id}/override-priority")
async def override_priority(id: int):
    return {"id": id, "priority_score": 90.0}
