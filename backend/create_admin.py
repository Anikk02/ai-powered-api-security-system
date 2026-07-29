# scripts/create_admin.py
import asyncio
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.db.models.admin import Admin
from app.authentication.password_handler import hash_password


async def create_admin_user():
    async with AsyncSessionLocal() as db:
        # Check if admin already exists
        result = await db.execute(
            select(Admin).where(Admin.email == "anshika18@triansec.com")
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            print("❌ Admin already exists!")
            print("=" * 50)
            print(f"   ID:        {existing.id}")
            print(f"   Email:     {existing.email}")
            print(f"   Name:      {existing.name}")
            print(f"   Role:      {existing.role}")
            print(f"   Status:    {existing.status}")
            print("=" * 50)
            print("\n💡 You can login with these existing credentials.")
            return
        
        # Create admin with specified credentials
        admin = Admin(
            email="anshika18@triansec.com",
            password_hash=hash_password("Anshika@003"),
            name="Anshika Singh",
            role="admin",
            status="active",
        )
        
        db.add(admin)
        await db.commit()
        await db.refresh(admin)
        
        print("✅ Admin created successfully!")
        print("=" * 50)
        print(f"   ID:        {admin.id}")
        print(f"   Email:     {admin.email}")
        print(f"   Name:      {admin.name}")
        print(f"   Password:  your password")
        print(f"   Role:      {admin.role}")
        print(f"   Status:    {admin.status}")
        print("=" * 50)
        print("\n🔐 You can now login to the developer dashboard with these credentials.")
        print("   URL: http://localhost:3001/login")


if __name__ == "__main__":
    asyncio.run(create_admin_user())