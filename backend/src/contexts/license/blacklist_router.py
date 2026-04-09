from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.src.infrastructure.database import get_db
from backend.src.contexts.auth.dependencies import get_current_user, PermissionChecker
from backend.src.contexts.auth.models import User

router = APIRouter(prefix="/blacklists", tags=["blacklists"])

@router.post("/serial")
async def blacklist_serial(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(PermissionChecker(["license.admin"]))
):
    """Add a serial number to the blacklist."""
    # Service implementation would go here
    return {"status": "success", "message": "Serial blacklisted"}

@router.post("/software")
async def blacklist_software(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(PermissionChecker(["license.admin"]))
):
    """Add a software name to the blacklist."""
    # Service implementation would go here
    return {"status": "success", "message": "Software blacklisted"}
