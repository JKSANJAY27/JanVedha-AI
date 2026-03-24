"""
CPGRAMS Mock Scraper for JanVedha AI — Grievance Ingestion

Since CPGRAMS API access requires restricted data.gov.in keys
(which are unavailable), this scraper generates realistic synthetic
grievance data based on actual Chennai civic issues patterns.

The mock data mirrors the structure and content of real CPGRAMS
complaints for demonstration and testing of the full pipeline.
"""
from __future__ import annotations

import hashlib
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import List

from app.services.scrapers.base import BaseScraper, ScrapedItem

logger = logging.getLogger(__name__)

# Realistic Chennai civic complaint templates based on actual grievance patterns
COMPLAINT_TEMPLATES = [
    {
        "category": "Water Supply",
        "templates": [
            "No water supply in {area} for the past {days} days. Residents are suffering badly.",
            "Low water pressure in {area}. Bore well water is contaminated. Request immediate action.",
            "Water pipe burst near {area}, wasting thousands of litres daily. MJK valve not working.",
            "Irregular water supply in ward {ward}. We receive water only once in 3 days.",
            "Pipeline leak at {area} junction, road getting waterlogged due to drain mixing.",
        ],
    },
    {
        "category": "Roads & Infrastructure",
        "templates": [
            "Massive pothole on {area} main road causing accidents daily. Two wheelers damaged.",
            "Road completely damaged in {area}. No one has repaired it since {months} months.",
            "Street light not working in {area} for past {weeks} weeks. Area is very unsafe at night.",
            "Footpath encroachment near {area} bus stop. Pedestrians forced to walk on road.",
            "Open manhole cover near {area}. Very dangerous for children and elderly.",
        ],
    },
    {
        "category": "Sanitation",
        "templates": [
            "Garbage not collected in {area} for {days} days. Stench is unbearable.",
            "Open dumping of construction debris near {area}. Corporation not taking action.",
            "Sewage overflow on {area} main road. Health hazard for residents.",
            "Dead animal (stray dog) lying on road near {area}. Not removed for 2 days.",
            "Community dustbin overflowing at {area}. No regular collection by conservancy workers.",
        ],
    },
    {
        "category": "Drainage",
        "templates": [
            "Blocked drain in {area} causing waterlogging even in light rain. Mosquito breeding.",
            "Storm water drain clogged with plastic waste near {area}.",
            "Drainage overflow flooding {area} streets during monsoon. Urgent desilting needed.",
            "Underground drainage burst near {area}. Sewage water flowing on main road.",
            "Stagnant water breeding mosquitoes in {area}. Danger of dengue outbreak.",
        ],
    },
    {
        "category": "Health",
        "templates": [
            "Dengue cases increasing in {area}. No fogging done by corporation in {weeks} weeks.",
            "Stray dog menace in {area}. Multiple residents bitten. Children at risk.",
            "Mosquito problem severe in {area} due to stagnant water. Corporation not spraying.",
            "Food poisoning cases reported from street vendors near {area}. Need health inspection.",
            "Open sewage near school in {area} causing health issues among students.",
        ],
    },
    {
        "category": "Electricity",
        "templates": [
            "Frequent power cuts in {area}, lasting {hours} hours daily. Transformer overloaded.",
            "Dangling electric wire near {area}. Extremely dangerous. Life-threatening.",
            "Street lights not working in entire {area} colony. Criminal activities increasing.",
            "Transformer explosion in {area}. No repairs for {days} days.",
            "Mercury vapor lamp damaged at {area} junction. Accidents happening at night.",
        ],
    },
]

CHENNAI_AREAS = [
    "T. Nagar", "Mylapore", "Adyar", "Anna Nagar", "Besant Nagar",
    "Velachery", "Tambaram", "Porur", "Chromepet", "Pallavaram",
    "Medavakkam", "Sholinganallur", "Perungudi", "Thiruvanmiyur",
    "Kodambakkam", "Nungambakkam", "Royapettah", "Triplicane",
    "Tondiarpet", "Washermanpet", "Perambur", "Kolathur",
    "Ambattur", "Madhavaram", "Villivakkam", "Manali",
    "KK Nagar", "Ashok Nagar", "Virugambakkam", "Vadapalani",
]

MINISTRIES = [
    "Ministry of Housing and Urban Affairs",
    "Ministry of Jal Shakti (Water Resources)",
    "Ministry of Health & Family Welfare",
    "Ministry of Road Transport & Highways",
    "Ministry of Environment, Forest & Climate Change",
]


class CPGRAMSScraper(BaseScraper):
    """
    Mock CPGRAMS scraper that generates realistic synthetic grievance data.
    Produces data structured identically to real CPGRAMS API responses.
    """

    platform = "cpgrams"

    def is_configured(self) -> bool:
        return True  # Always available (mock data)

    async def scrape(self, keywords: List[str], max_results: int = 20) -> List[ScrapedItem]:
        items: List[ScrapedItem] = []
        count = min(max_results, random.randint(5, 10))

        for _ in range(count):
            cat_data = random.choice(COMPLAINT_TEMPLATES)
            template = random.choice(cat_data["templates"])

            area = random.choice(CHENNAI_AREAS)
            ward = random.randint(1, 200)
            days = random.randint(2, 15)
            weeks = random.randint(1, 4)
            months = random.randint(2, 8)
            hours = random.randint(2, 8)

            content = template.format(
                area=area, ward=ward, days=days,
                weeks=weeks, months=months, hours=hours
            )

            # Generate a deterministic ID for dedup
            source_id = hashlib.sha256(
                f"cpgrams-{content}-{area}".encode()
            ).hexdigest()[:12]

            # Random timestamp in the last 7 days
            ts = datetime.now(timezone.utc) - timedelta(
                hours=random.randint(1, 168)
            )

            items.append(ScrapedItem(
                platform="cpgrams",
                content=content,
                author=random.choice(MINISTRIES),
                source_url=f"https://pgportal.gov.in/GrievanceNew/GrievanceDetail/{source_id}",
                location=area,
                post_timestamp=ts,
                keywords=[k for k in keywords if k.lower() in content.lower()] or [cat_data["category"].lower()],
                metadata={
                    "source": "cpgrams_mock",
                    "category": cat_data["category"],
                    "ward": ward,
                    "area": area,
                    "grievance_id": f"CPGRM/{ts.year}/{source_id[:8].upper()}",
                    "ministry": random.choice(MINISTRIES),
                    "status": random.choice(["PENDING", "UNDER_PROCESS", "DISPOSED"]),
                },
            ))

        self.logger.info("CPGRAMS mock: generated %d synthetic grievances", len(items))
        return items[:max_results]
