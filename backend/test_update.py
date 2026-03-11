import asyncio
from app.mongodb.database import init_mongodb
from app.mongodb.models.ticket import TicketMongo

async def update_ticket():
    await init_mongodb()
    t = await TicketMongo.find_one(TicketMongo.ticket_code == 'CIV-2026-64057')
    if t:
        t.ward_id = 1
        await t.save()
        print('Updated CIV-2026-64057 to ward_id=1')
    
    t2 = await TicketMongo.find_one(TicketMongo.ticket_code == 'CIV-2026-59457')
    if t2:
        t2.ward_id = 1
        await t2.save()
        print('Updated CIV-2026-59457 to ward_id=1')

if __name__ == '__main__':
    asyncio.run(update_ticket())
