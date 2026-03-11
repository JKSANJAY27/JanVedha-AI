import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from app.mongodb.database import init_mongodb
from app.mongodb.models.ticket import TicketMongo

async def main():
    await init_mongodb()
    tickets = await TicketMongo.find_all().to_list()
    if not tickets:
        print('No tickets found!')
    for t in tickets[-5:]:
        print(f'CODE: {t.ticket_code}, DEPT_ID: {t.dept_id}, STATUS: {t.status}, WARD: {t.ward_id}')

if __name__ == '__main__':
    asyncio.run(main())
