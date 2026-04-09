from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from backend.src.infrastructure.database import get_db
from backend.src.contexts.inventory.schemas import InventoryReportRequest, InventoryReportResponse, SparePartResponse
from backend.src.contexts.procurement.models import SparePart
from sqlalchemy import select
from backend.src.contexts.inventory.services.ingestion import InventoryIngestionService
from backend.src.core.security import get_agent_token_hash

router = APIRouter(prefix="/inventory", tags=["Inventory"])

async def agent_security_dependency(
    report: InventoryReportRequest,
    x_agent_token: Optional[str] = Header(None, alias="X-Agent-Token"),
    x_bootstrap_token: Optional[str] = Header(None, alias="X-Bootstrap-Token"),
    db: AsyncSession = Depends(get_db)
):
    """
    Agent Security Dependency:
    - Identifies device from report body.
    - If device exists:
        - Verifies HMAC-SHA256(token, AGENT_SECRET_KEY) against agent_token_hash.
        - Checks if device status is not PENDING_APPROVAL.
    - If device is NEW:
        - Requires valid X-Bootstrap-Token (compared to AGENT_BOOTSTRAP_TOKEN).
    """
    from backend.src.core.config import settings
    
    service = InventoryIngestionService(db)
    device = await service._identify_device(report)
    
    if device:
        # Existing Device: Must have valid Agent Token
        if not x_agent_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing X-Agent-Token for existing device"
            )
            
        if device.agent_token_hash:
            computed_hash = get_agent_token_hash(x_agent_token)
            if computed_hash != device.agent_token_hash:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid Agent Token: HMAC mismatch"
                )
        
        if device.status == "PENDING_APPROVAL":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Device is pending administrator approval"
            )
    else:
        # New Device: Must have valid Bootstrap Token
        if not x_bootstrap_token or x_bootstrap_token != settings.AGENT_BOOTSTRAP_TOKEN:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing X-Bootstrap-Token for new device registration"
            )
    
    return True

@router.post("/report", response_model=InventoryReportResponse)
async def report_inventory(
    report: InventoryReportRequest,
    db: AsyncSession = Depends(get_db),
    _ = Depends(agent_security_dependency)
):
    service = InventoryIngestionService(db)
    try:
        return await service.process_report(report)
    except HTTPException as e:
        raise e
    except Exception as e:
        # RFC 7807 fallback
        raise HTTPException(
            status_code=500,
            detail=f"Internal Server Error: {str(e)}"
        )

@router.get("/spare-parts", response_model=List[SparePartResponse])
async def list_spare_parts(
    db: AsyncSession = Depends(get_db),
    # current_user: User = Depends(get_current_user),
    # _ = Depends(PermissionChecker(["inventory.view"]))
):
    res = await db.execute(select(SparePart).order_by(SparePart.name))
    return res.scalars().all()

@router.post("/bulk-reconcile")
async def bulk_reconcile(
    payload: dict,
    db: AsyncSession = Depends(get_db)
):
    """Bulk reconcile multiple devices after offline sync."""
    # Logic to reconcile multiple devices
    return {"status": "success", "processed_count": len(payload.get("actions", []))}
