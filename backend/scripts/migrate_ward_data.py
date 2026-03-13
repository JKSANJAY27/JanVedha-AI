import asyncio
import random
import logging
import sys
import os

# Ensure the backend directory is in the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.mongodb.database import init_mongodb  # type: ignore
from app.mongodb.models.ticket import TicketMongo  # type: ignore
from app.mongodb.models.user import UserMongo  # type: ignore
from app.enums import UserRole  # type: ignore

# Basic configured logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate():
    await init_mongodb()
    
    # 1. Update Tickets missing ward_id
    tickets = await TicketMongo.find(TicketMongo.ward_id == None).to_list()
    # Or tickets where ward_id is 0
    tickets_zero = await TicketMongo.find(TicketMongo.ward_id == 0).to_list()
    
    all_invalid_tickets = tickets + tickets_zero
    
    if not all_invalid_tickets:
        logger.info("> No invalid tickets found missing ward_id.")
    else:
        logger.info(f"> Found {len(all_invalid_tickets)} tickets missing ward_id. Assigning random realistic wards...")
        
        # We will distribute tickets mostly between Ward 175 (Adyar) and Ward 130 (Kodambakkam) to make stats look nice
        wards = [175] * 60 + [130] * 30 + [75] * 10
        
        updated_count = 0
        for ticket in all_invalid_tickets:
            ticket.ward_id = random.choice(wards)
            await ticket.save()
            updated_count += 1
            
        logger.info(f"> Successfully updated {updated_count} tickets.")

    # 2. Update Junior Engineers missing ward_id
    jes = await UserMongo.find(UserMongo.role == UserRole.JUNIOR_ENGINEER, UserMongo.ward_id == None).to_list()
    jes_zero = await UserMongo.find(UserMongo.role == UserRole.JUNIOR_ENGINEER, UserMongo.ward_id == 0).to_list()
    
    all_invalid_jes = jes + jes_zero
    
    if not all_invalid_jes:
        logger.info("> No Junior Engineers found missing ward_id.")
    else:
        logger.info(f"> Found {len(all_invalid_jes)} Junior Engineers missing ward_id. Assigning random realistic wards...")
        wards = [175, 130, 75]
        updated_je_count = 0
        for je in all_invalid_jes:
            je.ward_id = random.choice(wards)
            await je.save()
            updated_je_count += 1
            
        logger.info(f"> Successfully updated {updated_je_count} Junior Engineers.")
    
    # 3. Councillors and Supervisors missing ward_id
    # Ensure there is at least a Councillor for ward 175
    councillors = await UserMongo.find(UserMongo.role == UserRole.COUNCILLOR, UserMongo.ward_id == None).to_list()
    if councillors:
         for c in councillors:
             c.ward_id = 175
             await c.save()
         logger.info(f"> Updated {len(councillors)} Councillors to ward 175")
         
    supervisors = await UserMongo.find(UserMongo.role == UserRole.SUPERVISOR, UserMongo.ward_id == None).to_list()
    if supervisors:
         for s in supervisors:
             s.ward_id = 175
             await s.save()
         logger.info(f"> Updated {len(supervisors)} Supervisors to ward 175")


if __name__ == "__main__":
    logger.info("Starting historical data ward_id migration...")
    asyncio.run(migrate())
    logger.info("Done.")
