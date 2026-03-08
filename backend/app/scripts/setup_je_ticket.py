import asyncio
from app.mongodb.database import init_mongodb, close_mongodb
from app.mongodb.models.ticket import TicketMongo
from app.mongodb.models.user import UserMongo

async def run():
    await init_mongodb()
    je = await UserMongo.find_one(UserMongo.email == "je@janvedha.ai")
    if not je:
        print("je not found")
        await close_mongodb()
        return

    tickets = await TicketMongo.find(TicketMongo.status == "OPEN").to_list()
    if not tickets:
        print("no open tickets")
    else:
        ticket = tickets[0]
        ticket.assigned_officer_id = str(je.id)
        ticket.status = "ASSIGNED"
        ticket.is_validated = True
        await ticket.save()
        print(f"Assigned ticket {ticket.ticket_code} to JE")

    await close_mongodb()

if __name__ == "__main__":
    asyncio.run(run())
