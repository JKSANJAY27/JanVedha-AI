import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.mongodb.database import init_mongodb
from app.mongodb.models.ticket import TicketMongo
from app.mongodb.models.user import UserMongo

async def main():
    await init_mongodb()
    
    # Let's see all tickets sorted by newest
    tickets = await TicketMongo.find_all().to_list()
    # sort manually
    tickets = sorted(tickets, key=lambda x: str(x.created_at), reverse=True)
    print('--- Latest 5 Tickets ---')
    for t in tickets[:5]:
        print(f'{t.ticket_code} (status: {t.status}), dept: {t.dept_id}, ward: {t.ward_id}')
        
    print('\n--- ALL JEs ---')
    from app.enums import UserRole
    jes = await UserMongo.find(UserMongo.role == UserRole.JUNIOR_ENGINEER).to_list()
    for je in jes:
        print(f'{je.email}: dept={je.dept_id}, name={je.name}')

if __name__ == '__main__':
    asyncio.run(main())
