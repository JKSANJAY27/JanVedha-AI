import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.main import app
from app.core.dependencies import get_current_user
from app.mongodb.models.user import UserMongo
from app.enums import UserRole
from app.services.intelligence_service import IntelligenceService

# Mock the current user dependency
async def override_get_current_user():
    user = UserMongo(
        email="test_councillor@janvedha.com",
        name="Test Councillor",
        role=UserRole.COUNCILLOR,
        ward_id=1,
        is_active=True,
        hashed_password="fake"
    )
    user.id = "60a7c9f9f9b5c2a1f4e1d1a1"
    return user

app.dependency_overrides[get_current_user] = override_get_current_user

client = TestClient(app)

# Mock IntelligenceService to avoid expensive LLM calls if needed, but we WANT to test them
# Actually, let's just call the endpoints directly with the TestClient
# Let's print the outputs

def test_intelligence_endpoints():
    with TestClient(app) as client:
        print("Testing /api/councillor/intelligence/briefing")
        response = client.get("/api/councillor/intelligence/briefing?ward_id=1")
        print(f"Status: {response.status_code}")
        print(f"Body: {response.json()}\n")
        assert response.status_code == 200

        print("Testing /api/councillor/intelligence/root-causes")
        response = client.get("/api/councillor/intelligence/root-causes?ward_id=1")
        print(f"Status: {response.status_code}")
        print(f"Body: {response.json()}\n")
        assert response.status_code == 200

        print("Testing /api/councillor/intelligence/predictions")
        response = client.get("/api/councillor/intelligence/predictions?ward_id=1")
        print(f"Status: {response.status_code}")
        print(f"Body: {response.json()}\n")
        assert response.status_code == 200


if __name__ == "__main__":
    test_intelligence_endpoints()
