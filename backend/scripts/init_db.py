import asyncio
import sys
import os

# Add parent directory of scripts to Python path so we can import 'app'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.base import Base
from app.db.session import engine
# Import models to register them on Base.metadata
from app.db.models import (
    user, api_key, request_log, decision_log,
    feature_log, ml_prediction, feedback,
    client, refresh_token, password_reset_token
)

async def init_db():
    print("[INFO] Creating database tables...")
    async with engine.begin() as conn:
        # Create all tables registered on metadata
        await conn.run_sync(Base.metadata.create_all)
    print("[SUCCESS] Database tables created successfully!")

if __name__ == "__main__":
    asyncio.run(init_db())
