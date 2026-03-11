import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from app.mongodb.database import init_mongodb
from app.mongodb.models.ticket import TicketMongo
from app.mongodb.models.user import UserMongo

async def main():
    await init_mongodb()
    je = await UserMongo.find_one(UserMongo.email == 'je.d01@janvedha.ai')
    if not je:
        print('JE not found!')
        return
    print('JE Dept ID:', je.dept_id)
    
    # Try the exact beanie query from officer.py
    tickets = await TicketMongo.find(
        TicketMongo.dept_id == je.dept_id
    ).sort(-TicketMongo.priority_score).to_list()
    
    print('Beanie query found', len(tickets), 'tickets')
    for t in tickets:
        print(f'{t.ticket_code} (status: {t.status})')

if __name__ == '__main__':
    asyncio.run(main())
