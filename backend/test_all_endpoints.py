import sys
import logging
import random
import string
import time

try:
    from fastapi.testclient import TestClient
except ImportError:
    print("FastAPI TestClient not available. Installing required packages...")
    sys.exit(2)

from app.main import app

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def random_string(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def run_tests():
    logger.info("Starting test sequence...")
    test_failed = False
    user_id = None
    
    with TestClient(app) as client:
        # 1. Health Endpoint
        logger.info("1. Testing /api/health...")
        try:
            response = client.get("/api/health")
            assert response.status_code == 200, f"Health failed: {response.text}"
            logger.info("   ✓ Health check passed. Response: " + str(response.json()))
        except Exception as e:
            logger.error(f"   ✗ Health check failed: {e}")
            test_failed = True

        # 2. Register Public User
        logger.info("\n2. Testing /api/auth/register/public...")
        unique_email = f"test_{random_string()}@example.com"
        unique_phone = f"99{random_string(8)}"
        register_payload = {
            "name": "Test User",
            "email": unique_email,
            "phone": unique_phone,
            "password": "testpassword123"
        }
        try:
            response = client.post("/api/auth/register/public", json=register_payload)
            assert response.status_code == 201, f"Register failed: {response.text}"
            user_id = response.json().get("user_id")
            logger.info(f"   ✓ Register passed. user_id: {user_id}")
        except Exception as e:
            logger.error(f"   ✗ Register failed: {e}")
            test_failed = True

        # 3. Login
        logger.info("\n3. Testing /api/auth/login...")
        login_payload = {
            "username": unique_email,
            "password": "testpassword123"
        }
        token = None
        try:
            response = client.post("/api/auth/login", data=login_payload)
            assert response.status_code == 200, f"Login failed: {response.text}"
            token = response.json().get("access_token")
            assert token, "No token returned"
            logger.info("   ✓ Login passed. Token received.")
        except Exception as e:
            logger.error(f"   ✗ Login failed: {e}")
            test_failed = True

        # 4. Create Complaint
        logger.info("\n4. Testing /api/public/complaints...")
        complaint_payload = {
            "description": "The street light is broken and it is very dark at night.",
            "location_text": "Anna Nagar, Zone 2",
            "reporter_phone": unique_phone,
            "consent_given": True,
            "reporter_name": "Test User",
            "reporter_user_id": user_id,
            "ward_id": 1
        }
        ticket_code = None
        try:
            response = client.post("/api/public/complaints", json=complaint_payload)
            assert response.status_code == 200, f"Complaint creation failed: {response.text}"
            ticket_code = response.json().get("ticket_code")
            assert ticket_code, "No ticket_code returned"
            logger.info(f"   ✓ Complaint creation passed. ticket_code: {ticket_code}")
            logger.info(f"   Details: {response.json()}")
        except Exception as e:
            logger.error(f"   ✗ Complaint creation failed: {e}")
            test_failed = True

        # 5. Track Complaint
        if ticket_code:
            logger.info(f"\n5. Testing /api/public/track/{ticket_code}...")
            try:
                response = client.get(f"/api/public/track/{ticket_code}")
                assert response.status_code == 200, f"Track complaint failed: {response.text}"
                logger.info("   ✓ Track complaint passed.")
            except Exception as e:
                logger.error(f"   ✗ Track complaint failed: {e}")
                test_failed = True

        # 6. Public Stats
        logger.info("\n6. Testing /api/public/stats...")
        try:
            response = client.get("/api/public/stats")
            assert response.status_code == 200, f"Stats failed: {response.text}"
            logger.info("   ✓ Stats passed.")
        except Exception as e:
            logger.error(f"   ✗ Stats failed: {e}")
            test_failed = True

        # 7. Officer Tickets
        if token:
            logger.info("\n7. Testing /api/officer/tickets...")
            headers = {"Authorization": f"Bearer {token}"}
            try:
                response = client.get("/api/officer/tickets", headers=headers)
                assert response.status_code == 200, f"Officer tickets failed: {response.text}"
                logger.info(f"   ✓ Officer tickets passed. Found {len(response.json())} tickets.")
            except Exception as e:
                logger.error(f"   ✗ Officer tickets failed: {e}")
                test_failed = True

    if test_failed:
        logger.error("\nSome tests failed. Check the logs above.")
        sys.exit(1)
    else:
        logger.info("\n🎉 All endpoints tested successfully!")
        sys.exit(0)

if __name__ == "__main__":
    run_tests()
