import asyncio
import sys
import os
import time

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from passlib.context import CryptContext
from sqlalchemy import text
from app.db.session import engine, AsyncSessionLocal
from app.db.models.client import Client

# ============================================================
# CONFIGURATION
# ============================================================

TOTAL_USERS = 500
BATCH_SIZE = 50  # Insert 50 at a time for efficiency
DEFAULT_PASSWORD = "TestPass123"  # Default password for all test users

pwd_context = CryptContext(schemes=["bcrypt"], bcrypt__rounds=12)


# ============================================================
# SEED FUNCTION
# ============================================================

async def seed_users():
    """Generate and insert 500 test users."""
    
    print(f"[INFO] Seeding {TOTAL_USERS} test users...")
    print(f"   Default password: {DEFAULT_PASSWORD}")
    print(f"   Batch size: {BATCH_SIZE}")
    print()
    
    start_time = time.time()
    
    # Pre-hash the default password (same for all test users)
    print("   Hashing default password...")
    password_hash = pwd_context.hash(DEFAULT_PASSWORD)
    print(f"   Hash: {password_hash[:20]}...")
    print()
    
    # Generate user data dicts
    users_data = []
    for i in range(1, TOTAL_USERS + 1):
        users_data.append({
            "email": f"testuser{i:04d}@triansec.dev",
            "password_hash": password_hash,
            "company_name": f"Test Company {i}",
            "role": "admin" if i <= 5 else "client",  # First 5 are admins
            "status": "active",
            "email_verified": True if i <= 100 else False,  # First 100 verified
        })
    
    # Also add a known admin and known client for manual testing
    users_data.append({
        "email": "admin@triansec.dev",
        "password_hash": pwd_context.hash("AdminPass123"),
        "company_name": "TrianSec Admin",
        "role": "super_admin",
        "status": "active",
        "email_verified": True,
    })
    users_data.append({
        "email": "client@triansec.dev",
        "password_hash": pwd_context.hash("ClientPass123"),
        "company_name": "Demo Client Corp",
        "role": "client",
        "status": "active",
        "email_verified": True,
    })
    
    # Clean existing clients to avoid duplication error on conflict
    async with AsyncSessionLocal() as session:
        await session.execute(text("DELETE FROM clients"))
        await session.commit()
    
    # Insert in batches using ORM objects
    inserted = 0
    for batch_start in range(0, len(users_data), BATCH_SIZE):
        batch = users_data[batch_start:batch_start + BATCH_SIZE]
        
        async with AsyncSessionLocal() as session:
            client_objs = []
            for u in batch:
                client_objs.append(Client(
                    email=u["email"],
                    password_hash=u["password_hash"],
                    company_name=u["company_name"],
                    role=u["role"],
                    status=u["status"],
                    email_verified=u["email_verified"]
                ))
            session.add_all(client_objs)
            await session.commit()
            
        inserted += len(batch)
        progress = (inserted / len(users_data)) * 100
        print(f"   [OK] Inserted batch: {inserted}/{len(users_data)} ({progress:.0f}%)")
        
    elapsed = time.time() - start_time
    print()
    print(f"[SUCCESS] Seeding complete!")
    print(f"   Total users: {inserted}")
    print(f"   Time: {elapsed:.2f}s")
    print()
    print("Test Credentials:")
    print("   admin@triansec.dev / AdminPass123")
    print("   client@triansec.dev / ClientPass123")
    print("   testuser0001@triansec.dev / TestPass123")


# ============================================================
# VERIFY FUNCTION
# ============================================================

async def verify_seed():
    """Verify the seed was successful."""
    
    print("[INFO] Verifying seed...")
    
    async with AsyncSessionLocal() as session:
        # Count total
        result = await session.execute(text("SELECT COUNT(*) FROM clients"))
        total = result.scalar()
        
        # Count by role
        result = await session.execute(
            text("SELECT role, COUNT(*) FROM clients GROUP BY role ORDER BY role")
        )
        roles = result.fetchall()
        
        # Count by status
        result = await session.execute(
            text("SELECT status, COUNT(*) FROM clients GROUP BY status")
        )
        statuses = result.fetchall()
    
    print(f"   Total clients: {total}")
    print(f"   By role:")
    for role, count in roles:
        print(f"      {role}: {count}")
    print(f"   By status:")
    for status_val, count in statuses:
        print(f"      {status_val}: {count}")
    print()
    
    if total >= 500:
        print("   [SUCCESS] Seed verification PASSED")
    else:
        print(f"   [ERROR] Expected >= 500, got {total}")


# ============================================================
# MAIN
# ============================================================

async def main():
    """Run seed + verify."""
    await seed_users()
    await verify_seed()


if __name__ == "__main__":
    asyncio.run(main())
