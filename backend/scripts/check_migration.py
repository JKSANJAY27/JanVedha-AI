import asyncio
import os
import sys

# Ensure the backend directory is in the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.mongodb.database import init_mongodb  # type: ignore
from app.mongodb.models.ticket import TicketMongo  # type: ignore

from typing import List

async def check_tickets():
    await init_mongodb()
    tickets: List[TicketMongo] = await TicketMongo.find_all().to_list()
    print(f"Total tickets: {len(tickets)}")
    
    count = 0
    for t in tickets:
        if count >= 5:
            break
        print(f"Code: {t.ticket_code}, Ward: {t.ward_id}, Dept: {t.dept_id}")
        count += 1

if __name__ == "__main__":
    asyncio.run(check_tickets())
