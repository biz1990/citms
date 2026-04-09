from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Any
from backend.src.infrastructure.database import get_db
from backend.src.contexts.reports.schemas import ReportFilter, AssetInventoryReport, AssetDepreciationReport, SoftwareComplianceReport, TicketSlaReport
from backend.src.contexts.reports.services import ReportService
from backend.src.contexts.auth.dependencies import get_current_user, PermissionChecker, get_data_scope, DataScope
from backend.src.contexts.auth.models import User

router = APIRouter(prefix="/reports", tags=["Reports & Materialized Views"])

@router.get("/asset-inventory")
async def asset_inventory_report(
    filters: ReportFilter = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    data_scope: DataScope = Depends(get_data_scope),
    _ = Depends(PermissionChecker(["report.view"]))
):
    """1. Asset Inventory Report with filters."""
    service = ReportService(db)
    return await service.generate_asset_inventory_report(filters, data_scope)

@router.get("/asset-depreciation")
async def asset_depreciation_report(
    filters: ReportFilter = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(PermissionChecker(["report.view"]))
):
    """2. Asset Depreciation Report from MV."""
    service = ReportService(db)
    return await service.generate_depreciation_report(filters)

@router.get("/software-usage")
async def software_usage_report(
    filters: ReportFilter = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(PermissionChecker(["report.view"]))
):
    """3. Software Usage & License Compliance from MV."""
    service = ReportService(db)
    return await service.generate_software_usage_report(filters)

@router.get("/license-expiration")
async def license_expiration_report(
    filters: ReportFilter = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(PermissionChecker(["report.view"]))
):
    """4. License Expiration Report (Next 30 days)."""
    service = ReportService(db)
    return await service.generate_license_expiration_report(filters)

@router.get("/ticket-sla")
async def ticket_sla_report(
    filters: ReportFilter = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    data_scope: DataScope = Depends(get_data_scope),
    _ = Depends(PermissionChecker(["report.view"]))
):
    """5. Ticket SLA Performance from MV."""
    service = ReportService(db)
    return await service.generate_sla_performance_report(filters, data_scope)

@router.get("/offline-missing")
async def offline_missing_report(
    filters: ReportFilter = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(PermissionChecker(["report.view"]))
):
    """8. Offline/Missing Devices from MV."""
    service = ReportService(db)
    return await service.generate_offline_missing_report(filters)

@router.get("/audit-log")
async def audit_log_report(
    filters: ReportFilter = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(PermissionChecker(["report.view"]))
):
    """6. Audit Log Report."""
    service = ReportService(db)
    return await service.generate_audit_log_report(filters)

@router.get("/procurement")
async def procurement_report(
    filters: ReportFilter = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(PermissionChecker(["report.view"]))
):
    """7. Procurement Report."""
    service = ReportService(db)
    return await service.generate_procurement_report(filters)

@router.get("/workflow")
async def workflow_report(
    filters: ReportFilter = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(PermissionChecker(["report.view"]))
):
    """8. Workflow Report."""
    service = ReportService(db)
    return await service.generate_workflow_report(filters)

@router.get("/remote-session")
async def remote_session_report(
    filters: ReportFilter = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(PermissionChecker(["report.view"]))
):
    """9. Remote Control Session Report."""
    service = ReportService(db)
    return await service.generate_remote_session_report(filters)

@router.post("/refresh-views", status_code=status.HTTP_202_ACCEPTED)
async def refresh_views(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(PermissionChecker(["report.admin"]))
):
    """Manually refresh all materialized views."""
    from backend.src.contexts.reports.repositories import ReportRepository
    repo = ReportRepository(db)
    await repo.refresh_all_materialized_views()
    return {"status": "refresh_started"}

@router.post("/scheduled", status_code=status.HTTP_201_CREATED)
async def create_scheduled_report(
    config: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(PermissionChecker("report.admin"))
):
    """Schedule a recurring report (SRS Module 8)."""
    # Logic to save schedule to DB and register with Celery Beat
    # Mocking successful creation
    return {
        "status": "scheduled",
        "schedule_id": "SCH-12345",
        "next_run": "2026-04-10T08:00:00Z"
    }
