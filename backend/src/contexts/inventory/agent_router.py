from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.src.infrastructure.database import get_db
from backend.src.contexts.inventory.schemas import InventoryReportRequest, InventoryReportResponse
from backend.src.contexts.inventory.services.ingestion import InventoryIngestionService

router = APIRouter(prefix="/agents", tags=["agents"])

@router.post("/register", response_model=InventoryReportResponse)
async def register_agent(
    report: InventoryReportRequest,
    db: AsyncSession = Depends(get_db)
):
    """Initial agent registration and token generation."""
    service = InventoryIngestionService(db)
    return await service.process_report(report)

@router.post("/heartbeat")
async def agent_heartbeat(
    device_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Simple heartbeat to update last_seen."""
    # Logic will be implemented in IngestionService if needed, 
    # but as per user request, we just need the route.
    return {"status": "alive", "timestamp": "now"}
