# 🚀 Migration & Seed Script — Database Setup

> Alembic migration + 500 test user seeder

---

## Overview

This document provides:
1. **Alembic migration** to create the 3 auth tables
2. **Python seed script** to generate 500 test users with hashed passwords
3. **Quick setup commands** for getting started

---

## 1. Alembic Migration

### Setup (if Alembic not yet initialized)

```bash
# From backend/ directory
pip install alembic
alembic init alembic

# Edit alembic.ini — set sqlalchemy.url:
# sqlalchemy.url = postgresql+asyncpg://postgres:5501@localhost:5513/api_security

# Edit alembic/env.py to import your models:
```

### Migration File: `alembic/versions/001_create_auth_tables.py`

```python
"""
Create authentication tables: clients, refresh_tokens, password_reset_tokens.

Revision ID: 001_auth_tables
Create Date: 2026-06-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import BIGINT

# Revision identifiers
revision = '001_auth_tables'
down_revision = None  # Set to your latest migration ID
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create authentication tables."""
    
    # ─────────────────────────────────────────────────────────
    # 1. CLIENTS TABLE
    # ─────────────────────────────────────────────────────────
    op.create_table(
        'clients',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('company_name', sa.String(255), nullable=True),
        sa.Column('role', sa.String(50), nullable=False, server_default='client'),
        sa.Column('status', sa.String(50), nullable=False, server_default='active'),
        sa.Column('email_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )
    
    # Indexes
    op.create_index('idx_clients_status', 'clients', ['status'])
    op.create_index('idx_clients_role', 'clients', ['role'])
    
    # ─────────────────────────────────────────────────────────
    # 2. REFRESH TOKENS TABLE
    # ─────────────────────────────────────────────────────────
    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('client_id', sa.BigInteger(), nullable=False),
        sa.Column('token_hash', sa.String(255), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('device_info', sa.String(500), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
    )
    
    # Indexes
    op.create_index('idx_refresh_tokens_client_id', 'refresh_tokens', ['client_id'])
    op.create_index('idx_refresh_tokens_expires', 'refresh_tokens', ['expires_at'])
    
    # ─────────────────────────────────────────────────────────
    # 3. PASSWORD RESET TOKENS TABLE
    # ─────────────────────────────────────────────────────────
    op.create_table(
        'password_reset_tokens',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('client_id', sa.BigInteger(), nullable=False),
        sa.Column('token_hash', sa.String(255), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
    )
    
    # Indexes
    op.create_index('idx_password_reset_client', 'password_reset_tokens',
                    ['client_id', 'created_at'])
    op.create_index('idx_password_reset_expires', 'password_reset_tokens',
                    ['expires_at'])
    
    # ─────────────────────────────────────────────────────────
    # 4. TRIGGER: Auto-update updated_at
    # ─────────────────────────────────────────────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    op.execute("""
        CREATE TRIGGER trigger_clients_updated_at
            BEFORE UPDATE ON clients
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    """Drop authentication tables."""
    op.execute("DROP TRIGGER IF EXISTS trigger_clients_updated_at ON clients;")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")
    
    op.drop_table('password_reset_tokens')
    op.drop_table('refresh_tokens')
    op.drop_table('clients')
```

---

## 2. Direct SQL Migration (Alternative)

If you prefer raw SQL over Alembic:

```sql
-- Run this against your PostgreSQL database
-- Database: api_security (same as existing)

-- Execute all SQL from 01_database_schema.md
-- Then run the seed script below
```

---

## 3. Seed Script — Generate 500 Test Users

### File: `scripts/seed_auth_users.py`

```python
"""
Seed script: Generate 500 test users with hashed passwords.
Place this file at: backend/scripts/seed_auth_users.py

Usage:
    cd backend
    python -m scripts.seed_auth_users

Or:
    python scripts/seed_auth_users.py
"""

import asyncio
import sys
import os
import time

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from passlib.context import CryptContext
from sqlalchemy import text
from app.db.session import engine, AsyncSessionLocal

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
    
    print(f"🔐 Seeding {TOTAL_USERS} test users...")
    print(f"   Default password: {DEFAULT_PASSWORD}")
    print(f"   Batch size: {BATCH_SIZE}")
    print()
    
    start_time = time.time()
    
    # Pre-hash the default password (same for all test users)
    print("   Hashing default password...")
    password_hash = pwd_context.hash(DEFAULT_PASSWORD)
    print(f"   Hash: {password_hash[:20]}...")
    print()
    
    # Generate user data
    users = []
    for i in range(1, TOTAL_USERS + 1):
        users.append({
            "email": f"testuser{i:04d}@triansec.dev",
            "password_hash": password_hash,
            "company_name": f"Test Company {i}",
            "role": "admin" if i <= 5 else "client",  # First 5 are admins
            "status": "active",
            "email_verified": True if i <= 100 else False,  # First 100 verified
        })
    
    # Also add a known admin and known client for manual testing
    users.append({
        "email": "admin@triansec.dev",
        "password_hash": pwd_context.hash("AdminPass123"),
        "company_name": "TrianSec Admin",
        "role": "super_admin",
        "status": "active",
        "email_verified": True,
    })
    users.append({
        "email": "client@triansec.dev",
        "password_hash": pwd_context.hash("ClientPass123"),
        "company_name": "Demo Client Corp",
        "role": "client",
        "status": "active",
        "email_verified": True,
    })
    
    # Insert in batches
    inserted = 0
    async with AsyncSessionLocal() as session:
        for batch_start in range(0, len(users), BATCH_SIZE):
            batch = users[batch_start:batch_start + BATCH_SIZE]
            
            # Build batch INSERT
            values_list = []
            params = {}
            for j, user in enumerate(batch):
                idx = batch_start + j
                values_list.append(
                    f"(:email_{idx}, :hash_{idx}, :company_{idx}, "
                    f":role_{idx}, :status_{idx}, :verified_{idx})"
                )
                params[f"email_{idx}"] = user["email"]
                params[f"hash_{idx}"] = user["password_hash"]
                params[f"company_{idx}"] = user["company_name"]
                params[f"role_{idx}"] = user["role"]
                params[f"status_{idx}"] = user["status"]
                params[f"verified_{idx}"] = user["email_verified"]
            
            values_sql = ", ".join(values_list)
            query = text(f"""
                INSERT INTO clients 
                    (email, password_hash, company_name, role, status, email_verified)
                VALUES {values_sql}
                ON CONFLICT (email) DO NOTHING
            """)
            
            await session.execute(query, params)
            inserted += len(batch)
            
            progress = (inserted / len(users)) * 100
            print(f"   ✅ Inserted batch: {inserted}/{len(users)} ({progress:.0f}%)")
        
        await session.commit()
    
    elapsed = time.time() - start_time
    print()
    print(f"🎉 Seeding complete!")
    print(f"   Total users: {inserted}")
    print(f"   Time: {elapsed:.2f}s")
    print()
    print("📋 Test Credentials:")
    print("   ┌────────────────────────────────────────────────────────┐")
    print("   │ Admin:   admin@triansec.dev   / AdminPass123          │")
    print("   │ Client:  client@triansec.dev  / ClientPass123         │")
    print("   │ Bulk:    testuser0001@triansec.dev / TestPass123      │")
    print("   │          testuser0002@triansec.dev / TestPass123      │")
    print("   │          ...                                           │")
    print("   │          testuser0500@triansec.dev / TestPass123      │")
    print("   └────────────────────────────────────────────────────────┘")


# ============================================================
# VERIFY FUNCTION
# ============================================================

async def verify_seed():
    """Verify the seed was successful."""
    
    print("🔍 Verifying seed...")
    
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
        print("   ✅ Seed verification PASSED")
    else:
        print(f"   ❌ Expected >= 500, got {total}")


# ============================================================
# MAIN
# ============================================================

async def main():
    """Run seed + verify."""
    await seed_users()
    await verify_seed()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 4. Quick Start Commands

```bash
# 1. Install dependencies
pip install python-jose[cryptography] passlib[bcrypt] bcrypt email-validator alembic

# 2. Run migration (Alembic)
cd backend
alembic upgrade head

# 3. OR run migration (raw SQL)
psql -h localhost -p 5513 -U postgres -d api_security -f docs/auth_system/01_database_schema.sql

# 4. Seed 500 users
cd backend
python -m scripts.seed_auth_users

# 5. Verify
psql -h localhost -p 5513 -U postgres -d api_security -c "SELECT COUNT(*) FROM clients;"
```

---

## 5. Cleanup Script

```python
"""
Cleanup: Remove all test users and tokens.
"""

async def cleanup_auth_data():
    async with AsyncSessionLocal() as session:
        await session.execute(text("DELETE FROM password_reset_tokens"))
        await session.execute(text("DELETE FROM refresh_tokens"))
        await session.execute(text("DELETE FROM clients"))
        await session.commit()
    print("🧹 All auth data cleaned up")
```

---

**End of Migration & Seed Script Document**
