import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.mongodb.database import init_mongodb
from app.services.intelligence_service import IntelligenceService
from app.mongodb.models.ticket import TicketMongo

async def main():
    await init_mongodb()
    
    print("Fetching past 14 days tickets")
    from datetime import datetime, timedelta
    since = datetime.utcnow() - timedelta(days=14)
    tickets = await TicketMongo.find(
        TicketMongo.ward_id == 1
    ).to_list()
    print(len(tickets), "tickets found")
    
    loc_tickets = [
        t for t in tickets 
        if t.location and "coordinates" in t.location and t.issue_category
    ]
    print(f"{len(loc_tickets)} have location and category")
    
    # Let's print the potholes
    potholes = [t for t in loc_tickets if t.issue_category == 'pothole']
    print("\n--- Potholes ---")
    for p in potholes:
        print(p.ticket_code, p.location['coordinates'])
        
    from app.services.intelligence_service import haversine_distance
    print("\n--- Distances between first pothole and others ---")
    if potholes:
        p0 = potholes[0]
        lon1, lat1 = p0.location['coordinates']
        for p in potholes[1:]:
            lon2, lat2 = p.location['coordinates']
            dist = haversine_distance(lat1, lon1, lat2, lon2)
            print(f"Dist to {p.ticket_code}: {dist} meters")
    
    print("\nTesting Radar")
    res = await IntelligenceService.get_root_cause_radar(1)
    
    print("RADAR RESULT:")
    import json
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
