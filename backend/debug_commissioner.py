import asyncio, sys, re
sys.path.insert(0, ".")

async def check():
    from datetime import datetime
    import motor.motor_asyncio
    from app.core.config import settings

    client = motor.motor_asyncio.AsyncIOMotorClient(settings.MONGODB_URI)
    m = re.search(r"/([^/?]+)(\?|$)", settings.MONGODB_URI)
    db_name = m.group(1) if m else "janvedha"
    db = client[db_name]

    now = datetime.utcnow()
    print("Now (UTC):", now)

    col = db["intelligence_alerts"]
    all_docs = await col.find({}).to_list(None)
    print("Total docs:", len(all_docs))
    for d in all_docs:
        print("  Document:", d.get('status'), d.get('expires_at'), type(d.get('expires_at')))

    status_list = ["new", "acknowledged"]
    
    q1 = {"status": {"$in": status_list}}
    q2 = {"$or": [{"expires_at": {"$gt": now}}, {"expires_at": None}]}
    q3 = {"status": {"$in": status_list}, "$or": [{"expires_at": {"$gt": now}}, {"expires_at": None}]}

    print("\nQ1 (status only):", len(await col.find(q1).to_list(None)))
    print("Q2 (expires only):", len(await col.find(q2).to_list(None)))
    print("Q3 (combined):", len(await col.find(q3).to_list(None)))

    # For escalations
    col_esc = db["escalations"]
    print("\nEscalations:")
    q_esc1 = {"status": {"$nin": ["closed"]}}
    print("Open escalations:", len(await col_esc.find(q_esc1).to_list(None)))

asyncio.run(check())
