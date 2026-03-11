import asyncio
from app.mongodb.database import init_mongodb, close_mongodb
from app.mongodb.models.ticket import TicketMongo
from app.mongodb.models.user import UserMongo
from app.mongodb.models.department import DepartmentMongo
from app.enums import UserRole
from app.services.auth_service import AuthService

async def run():
    await init_mongodb()
    
    print("Deleting all tickets...")
    await TicketMongo.find_all().delete()
    print("Tickets deleted.")
    
    print("Deleting existing junior engineers and field staff logs...")
    await UserMongo.find(
        {"role": {"$in": [UserRole.JUNIOR_ENGINEER, UserRole.FIELD_STAFF]}}
    ).delete()
    print("Cleaned up old staff.")
    
    departments = await DepartmentMongo.find_all().to_list()
    
    je_logins = []
    
    for dept in departments:
        # Create JE
        je_email = f"je.{dept.dept_id.lower()}@janvedha.ai"
        je_name = f"JE {dept.dept_name}"
        je_password = "Password123"
        
        je = UserMongo(
            name=je_name,
            email=je_email,
            phone=f"900000{dept.dept_id[-2:]}",  # e.g. 90000001
            password_hash=AuthService.get_password_hash(je_password),
            role=UserRole.JUNIOR_ENGINEER,
            ward_id=1,
            dept_id=dept.dept_id
        )
        await je.insert()
        je_logins.append({"dept": dept.dept_name, "email": je_email, "password": je_password})
        
        # Create 2 Field Staffs
        for i in range(1, 3):
            fs_email = f"tech{i}.{dept.dept_id.lower()}@janvedha.ai"
            fs_name = f"Tech {i} {dept.dept_name}"
            
            fs = UserMongo(
                name=fs_name,
                email=fs_email,
                phone=f"8000{i}0{dept.dept_id[-2:]}", 
                password_hash=AuthService.get_password_hash("Password123"),
                role=UserRole.FIELD_STAFF,
                ward_id=1,
                dept_id=dept.dept_id
            )
            await fs.insert()

    print("\n--- Junior Engineer Logins ---")
    for login in je_logins:
        print(f"Dept: {login['dept']}")
        print(f"Email: {login['email']} | Password: {login['password']}")
        print("-" * 30)
        
    await close_mongodb()

if __name__ == "__main__":
    asyncio.run(run())
