import asyncio
import os
import sys

# Ensure the backend directory is in the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.mongodb.database import init_mongodb  # type: ignore
from app.mongodb.models.user import UserMongo  # type: ignore
from app.enums import UserRole  # type: ignore

from typing import List

async def check_jes():
    await init_mongodb()
    jes: List[UserMongo] = await UserMongo.find(UserMongo.role == UserRole.JUNIOR_ENGINEER).to_list()
    print(f"Total Junior Engineers: {len(jes)}")
    for j in jes:
        print(f"Name: {j.name}, Ward: {j.ward_id}, Dept: {j.dept_id}")

if __name__ == "__main__":
    asyncio.run(check_jes())
