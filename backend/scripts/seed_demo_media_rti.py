import asyncio
from datetime import datetime
from uuid import uuid4

from app.mongodb.database import init_mongodb
from app.mongodb.models.media_rti_response import MediaRtiResponseMongo, AnalysisResult

async def seed_media_rti_data():
    await init_mongodb()
    
    # Check if data already exists to avoid duplicates
    existing = await MediaRtiResponseMongo.find_one()
    if existing:
        print("Media & RTI seed data already exists. Skipping.")
        return

    ward_id = "75"
    councillor_id = "councillor75"
    councillor_name = "Karthik Subramanian"
    ward_name = "Ward 75"

    demo_responses = [
        # Demo 1: Media Response (Data-forward)
        MediaRtiResponseMongo(
            response_id=str(uuid4()),
            ward_id=ward_id,
            councillor_id=councillor_id,
            councillor_name=councillor_name,
            ward_name=ward_name,
            type="media",
            query_text="How many potholes were reported and fixed in your ward last month? Residents claim nothing is being done.",
            query_source="The Daily Chronicle",
            tone_preference="data_forward",
            data_analysis=AnalysisResult(
                query_intent="Media is inquiring about pothole repair rates and challenging the effectiveness of the response.",
                is_answerable=True,
                data_points=[{
                    "description": "Road and Pothole tickets in the last 30 days",
                    "data": {
                        "total_count": 45,
                        "resolved_count": 38,
                        "resolution_rate_pct": 84.4,
                        "avg_resolution_days": 2.1
                    }
                }],
                outside_scope=["Specific resident testimonials"],
                sensitivity_flag=False,
                sensitivity_note=""
            ),
            output={
                "quotable_statement": "The data speaks for itself: in the last 30 days, we received 45 pothole complaints and resolved 38 of them—an 84% resolution rate, with most fixed within 48 hours.",
                "supporting_data_points": [
                    "45 total pothole reports in the last month.",
                    "38 of those have already been resolved (84.4%).",
                    "The average time to repair a reported pothole is exactly 2.1 days."
                ],
                "full_response_letter": "Dear Reporter,\n\nThank you for reaching out regarding the state of the roads in our ward. I understand residents' concerns, however, the claims that 'nothing is being done' are factually incorrect and easily disproven by our transparent tracking data.\n\nIn the last 30 days alone, we received a total of 45 complaints regarding potholes. Our roads engineering team immediately prioritized these, successfully resolving 38 of them to date. This represents an 84.4% resolution rate.\n\nFurthermore, when a pothole is reported, our average time to complete the repair is just 2.1 days. We are committed to maintaining safe infrastructure and the data shows our department is working efficiently to address these exact issues.\n\nBest regards,\nKarthik Subramanian\nCouncillor, Ward 75",
                "data_gaps_note": "You may want to mention the specific streets where the remaining 7 repairs are scheduled."
            },
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        ),

        # Demo 2: RTI Response
        MediaRtiResponseMongo(
            response_id=str(uuid4()),
            ward_id=ward_id,
            councillor_id=councillor_id,
            councillor_name=councillor_name,
            ward_name=ward_name,
            type="rti",
            query_text="Provide the total number of street light repair requests made in Ward 75 between Jan 1 and March 1, and the average time taken to resolve them.",
            query_source="Mr. Ramesh Kumar",
            rti_application_number="RTI/2026/0441",
            date_received="2026-03-01T00:00:00Z",
            data_analysis=AnalysisResult(
                query_intent="Applicant is requesting specific statistics regarding streetlight repairs and their resolution times.",
                is_answerable=True,
                data_points=[{
                    "description": "Streetlight complaints (Jan 1 - Mar 1)",
                    "data": {
                        "total_count": 112,
                        "resolved_count": 105,
                        "resolution_rate_pct": 93.7,
                        "avg_resolution_days": 3.4
                    }
                }],
                outside_scope=[],
                sensitivity_flag=False,
                sensitivity_note=""
            ),
            output={
                "rti_response_document": {
                    "header": {
                        "office_name": "Office of the Ward Councillor, Ward 75",
                        "application_number": "RTI/2026/0441",
                        "date_of_receipt": "01 March 2026",
                        "date_of_response": "18 March 2026",
                        "response_deadline": "31 March 2026"
                    },
                    "applicant_reference": "To,\nMr. Ramesh Kumar",
                    "acknowledgment_paragraph": "This is with reference to your application filed under the Right to Information Act, 2005, bearing registration number RTI/2026/0441 dated 01 March 2026.",
                    "information_provided": [
                        {
                            "query_item": "Total number of street light repair requests made in Ward 75 between Jan 1 and March 1",
                            "response": "According to the civic management system, a total of 112 street light repair requests were registered in Ward 75 during the specified period.",
                            "data_basis": "Ticket database (Department: Streetlights)"
                        },
                        {
                            "query_item": "The average time taken to resolve them",
                            "response": "The average time taken to resolve these street light repair requests during this period was 3.4 days.",
                            "data_basis": "Ticket database analytics"
                        }
                    ],
                    "information_not_held": [],
                    "closing_paragraph": "If you are not satisfied with this reply, you may file an appeal to the First Appellate Authority within 30 days of receipt of this letter.",
                    "signature_block": {
                        "name": "Karthik Subramanian",
                        "designation": "Councillor",
                        "ward": "Ward 75",
                        "date": "18 March 2026"
                    }
                },
                "internal_note": "All requested data was found. Response drafted well within the 30-day statutory limit."
            },
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
    ]

    for doc in demo_responses:
        await doc.insert()
        
    print(f"Successfully inserted {len(demo_responses)} Media/RTI demo responses.")

if __name__ == "__main__":
    asyncio.run(seed_media_rti_data())
