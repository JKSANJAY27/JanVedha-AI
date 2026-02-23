#!/usr/bin/env python
"""Test database connection and schema initialization."""
import asyncio
import sys
from sqlalchemy import inspect

async def test_db_connection():
    engine = None
    try:
        print("[*] Testing database connection...\n")
        
        from app.core.database import engine
        from app.models import (
            Base, Ticket, Department, User, AuditLog, 
            WardDeptOfficer, Announcement, WardPrediction
        )
        from sqlalchemy import text
        
        # Test connection
        print("[*] Attempting to connect to database...")
        async with engine.begin() as conn:
            await conn.run_sync(lambda c: c.execute(text("SELECT 1")))
        print("[OK] Database connection successful!\n")
        
        # Create tables if they don't exist
        print("[*] Creating database tables (if not already present)...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("[OK] Database tables created/verified!\n")
        
        # Check existing tables
        print("[*] Inspecting database tables:")
        async with engine.begin() as conn:
            def check_tables(connection):
                inspector = inspect(connection)
                tables = inspector.get_table_names()
                if tables:
                    for table in tables:
                        columns = [col['name'] for col in inspector.get_columns(table)]
                        print(f"  [OK] {table}: {', '.join(columns)}")
                else:
                    print("  (no tables found)")
            
            await conn.run_sync(check_tables)
        
        print("\n[SUCCESS] Database setup complete and ready!")
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Database connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if engine:
            await engine.dispose()

if __name__ == "__main__":
    success = asyncio.run(test_db_connection())
    sys.exit(0 if success else 1)
