import asyncio
import sys
import os
from datetime import datetime
import uuid

# Add the project root to sys.path to allow imports from backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from sqlalchemy import select
from backend.src.infrastructure.database import AsyncSessionLocal
from backend.src.contexts.auth.models import Role, Permission, Department, User

# Define essential roles and permissions
ROLES = [
    {"name": "SUPER_ADMIN", "description": "Global administrator"},
    {"name": "IT_MANAGER", "description": "IT Department management"},
    {"name": "IT_STAFF", "description": "Helpdesk and technical staff"},
    {"name": "PROCUREMENT", "description": "Asset purchasing agents"},
    {"name": "USER", "description": "Standard business user"}
]

PERMISSIONS = [
    {"code": "asset.view", "name": "View Assets", "module": "Asset"},
    {"code": "asset.create", "name": "Create Assets", "module": "Asset"},
    {"code": "asset.edit", "name": "Edit Assets", "module": "Asset"},
    {"code": "asset.delete", "name": "Soft Delete Assets", "module": "Asset"},
    {"code": "asset.admin", "name": "Approve/Audit Assets", "module": "Asset"},
    {"code": "itsm.ticket_view", "name": "View Tickets", "module": "ITSM"},
    {"code": "itsm.ticket_create", "name": "Create Tickets", "module": "ITSM"},
    {"code": "itsm.ticket_resolve", "name": "Resolve Tickets", "module": "ITSM"},
    {"code": "rbac.manage", "name": "Manage Users & Roles", "module": "Auth"},
]

DEPARTMENTS = [
    {"name": "IT Department"},
    {"name": "Human Resources"},
    {"name": "Finance"},
    {"name": "Operations"}
]

async def seed_data():
    print("Seeding initial data...")
    async with AsyncSessionLocal() as db:
        # 1. Seed Permissions
        print("  - Seeding Permissions...")
        for p_data in PERMISSIONS:
            res = await db.execute(select(Permission).where(Permission.code == p_data["code"]))
            if not res.scalar_one_or_none():
                db.add(Permission(**p_data))
        await db.flush()

        # 2. Seed Roles
        print("  - Seeding Roles...")
        all_perms_res = await db.execute(select(Permission))
        all_perms = all_perms_res.scalars().all()
        
        for r_data in ROLES:
            res = await db.execute(select(Role).where(Role.name == r_data["name"]))
            role = res.scalar_one_or_none()
            if not role:
                role = Role(**r_data)
                db.add(role)
                await db.flush()
            
            # Auto-assign permissions to SUPER_ADMIN
            if role.name == "SUPER_ADMIN":
                role.permissions = all_perms
        
        # 3. Seed Departments
        print("  - Seeding Departments...")
        for d_data in DEPARTMENTS:
            res = await db.execute(select(Department).where(Department.name == d_data["name"]))
            if not res.scalar_one_or_none():
                db.add(Department(**d_data))

        await db.commit()
        print("Seeding completed successfully!")

if __name__ == "__main__":
    asyncio.run(seed_data())
