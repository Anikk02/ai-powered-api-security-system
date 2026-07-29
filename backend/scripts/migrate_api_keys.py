import asyncio
import sys
import os

# Add parent directory of scripts to Python path so we can import 'app'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.base import Base
from app.db.session import engine
from sqlalchemy import text
# Import models to register them on Base.metadata
from app.db.models import api_key

async def migrate():
    print("[INFO] Starting API Keys database migration...")
    async with engine.begin() as conn:
        # Drop existing api_keys table to avoid conflict
        print("   [INFO] Dropping existing api_keys table...")
        await conn.execute(text("DROP TABLE IF EXISTS api_keys CASCADE"))
        
        # Create all tables (it will recreate api_keys with the new columns)
        print("   [INFO] Re-creating api_keys table with new schema...")
        await conn.run_sync(Base.metadata.create_all)
        
    print("[SUCCESS] API Keys database migration complete!")

if __name__ == "__main__":
    asyncio.run(migrate())
