import asyncio
import httpx
from datetime import datetime

async def test_je_flow():
    # 1. Login as JE
    print("1. Logging in as JE...")
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        resp = await client.post("/auth/login", data={"username": "je@janvedha.ai", "password": "Password123"})
        if resp.status_code != 200:
            print("Login failed!", resp.json())
            return
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Get tickets
        print("2. Getting tickets...")
        resp = await client.get("/officer/tickets", headers=headers)
        tickets = resp.json()
        je_tickets = [t for t in tickets if t.get("status") == "ASSIGNED"]
        if not je_tickets:
            print("No assigned tickets found for JE.")
            return
        
        ticket_id = je_tickets[0]["id"]
        print(f"   Selected ticket {ticket_id}")

        # 3. Get Field Staff
        print("3. Getting available field staff...")
        resp = await client.get("/officer/staff/field", headers=headers)
        staff = resp.json()
        if not staff:
            print("No field staff found.")
            return
        fs_id = staff[0]["id"]
        print(f"   Selected Field Staff {fs_id}")

        # 4. Assign Field Staff
        print("4. Assigning Field Staff...")
        payload = {"technician_id": fs_id, "scheduled_date": "2026-03-10"}
        resp = await client.post(f"/officer/tickets/{ticket_id}/assign-field", json=payload, headers=headers)
        print("   Status:", resp.status_code)

        # 5. Start Work
        print("5. Starting Work...")
        resp = await client.post(f"/officer/tickets/{ticket_id}/status", params={"status": "IN_PROGRESS"}, headers=headers)
        print("   Status:", resp.status_code)

        # 6. Upload Proof
        print("6. Uploading Proof...")
        resp = await client.post(f"/officer/tickets/{ticket_id}/proof", json={"after_photo_url": "https://picsum.photos/400"}, headers=headers)
        print("   Status:", resp.status_code)

        # 7. Complete Work
        print("7. Moving to Pending Verification...")
        resp = await client.post(f"/officer/tickets/{ticket_id}/status", params={"status": "PENDING_VERIFICATION"}, headers=headers)
        print("   Status:", resp.status_code)

        # 8. Verify
        resp = await client.get(f"/officer/tickets/{ticket_id}", headers=headers)
        t = resp.json()
        print("\nFinal Ticket State:")
        print(f"Status: {t['status']}")
        print(f"Technician: {t.get('technician_id')}")
        print(f"Scheduled: {t.get('scheduled_date')}")
        print(f"Proof URL: {t.get('after_photo_url')}")
        print("Test Passed!" if t['status'] == 'PENDING_VERIFICATION' and 'after_photo_url' in t else "Test Failed!")

if __name__ == "__main__":
    asyncio.run(test_je_flow())
