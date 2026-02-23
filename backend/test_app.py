#!/usr/bin/env python
import sys
import asyncio
import logging

logging.basicConfig(level=logging.DEBUG)

try:
    print("📦 Importing FastAPI app...")
    from app.main import app
    print("✓ FastAPI app imported successfully")
    
    print("🔍 App routes:")
    for route in app.routes:
        print(f"  - {route}")
    
    print("✓ Backend is ready!")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
