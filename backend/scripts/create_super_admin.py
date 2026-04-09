import asyncio
import sys
import os
from datetime import datetime

# Add the project root to sys.path to allow imports from backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from sqlalchemy import select
from backend.src.infrastructure.database import AsyncSessionLocal
from backend.src.contexts.auth.models import User, Role
from backend.src.core.security import get_password_hash

async def create_super_admin(email, password, username="admin", full_name="System Administrator"):
    print(f"Creating super admin: {username} ({email})...")
    async with AsyncSessionLocal() as db:
        # 1. Ensure SUPER_ADMIN role exists
        res = await db.execute(select(Role).where(Role.name == "SUPER_ADMIN"))
        role = res.scalar_one_or_none()
        
        if not role:
            print("Role SUPER_ADMIN not found. Creating it...")
            role = Role(name="SUPER_ADMIN", description="Master administrative role with all permissions")
            db.add(role)
            await db.flush()
        
        # 2. Check if user already exists
        res = await db.execute(select(User).where(User.username == username))
        existing_user = res.scalar_one_or_none()
        
        if existing_user:
            print(f"User {username} already exists. Updating password...")
            existing_user.password_hash = get_password_hash(password)
            existing_user.email = email
            existing_user.is_active = True
        else:
            user = User(
                username=username,
                email=email,
                password_hash=get_password_hash(password),
                full_name=full_name,
                is_active=True,
                auth_provider="LOCAL"
            )
            db.add(user)
            await db.flush()
            
            # Assign role
            user.roles.append(role)
            print(f"User {username} created and assigned SUPER_ADMIN role.")
        
        await db.commit()
        print("Done!")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Create a super admin user for CITMS")
    parser.add_argument("--email", required=True, help="Email for the admin user")
    parser.add_argument("--password", required=True, help="Password for the admin user")
    parser.add_argument("--username", default="admin", help="Username (default: admin)")
    parser.add_argument("--name", default="System Administrator", help="Full name")
    
    args = parser.parse_args()
    
    asyncio.run(create_super_admin(args.email, args.password, args.username, args.name))
