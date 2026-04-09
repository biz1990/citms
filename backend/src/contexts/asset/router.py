from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta
from backend.src.infrastructure.database import get_db
from backend.src.contexts.asset.models import Device, DeviceComponent, DeviceConnection
from backend.src.contexts.asset.repositories import DeviceRepository
from backend.src.infrastructure.dependencies.pagination import PaginationParams, get_pagination_params, PaginatedResponse
from backend.src.contexts.auth.dependencies import get_current_user, get_data_scope, DataScope, PermissionChecker
from backend.src.contexts.auth.models import User
from backend.src.contexts.auth.audit_service import AuditService

router = APIRouter(prefix="/devices", tags=["Asset Management"])

@router.get("/", response_model=PaginatedResponse[dict])
async def list_devices(
    pagination: PaginationParams = Depends(get_pagination_params),
    filter: Optional[str] = None, # SRS 5.4: OData-like filter (status eq 'ACTIVE')
    device_type: Optional[str] = None,
    location_id: Optional[UUID] = None,
    search: Optional[str] = None,
    is_offline: Optional[bool] = None,
    is_warranty_expiring: Optional[bool] = None,
    is_duplicate_serial: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    data_scope: DataScope = Depends(get_data_scope)
):
    query = select(Device)
    
    # Apply Row-Level Security / Data Isolation
    query = data_scope.apply_isolation(query, Device)
    
    # Module 5.4: OData-like Filter Parser
    if filter:
        if " eq " in filter:
            field, value = filter.split(" eq ")
            value = value.strip("'").strip("\"")
            if hasattr(Device, field):
                query = query.where(getattr(Device, field) == value)
        else:
            # Fallback or strict enforcement
            raise HTTPException(
                status_code=400, 
                detail="Invalid filter format. Expected 'field eq 'value'' (SRS 5.4)"
            )
            
    if device_type:
        query = query.where(Device.device_type == device_type)
    if location_id:
        query = query.where(Device.location_id == location_id)
    if search:
        query = query.where(
            or_(
                Device.hostname.ilike(f"%{search}%"),
                Device.serial_number.ilike(f"%{search}%"),
                Device.primary_mac.ilike(f"%{search}%")
            )
        )
    
    now = datetime.utcnow()
    if is_offline:
        five_mins_ago = now - timedelta(minutes=5)
        query = query.where(or_(Device.last_seen < five_mins_ago, Device.last_seen == None))
    
    if is_warranty_expiring:
        # Mock warranty as purchase_date + 3 years
        three_years_ago = now - timedelta(days=3*365)
        thirty_days_from_now = three_years_ago + timedelta(days=30)
        query = query.where(and_(Device.purchase_date >= three_years_ago, Device.purchase_date <= thirty_days_from_now))

    if is_duplicate_serial:
        # Subquery to find duplicate serials
        subq = select(Device.serial_number).group_by(Device.serial_number).having(func.count(Device.id) > 1).subquery()
        query = query.where(Device.serial_number.in_(select(subq)))
        
    # Get total count before pagination
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(Device.hostname).offset(pagination.skip).limit(pagination.limit)
    res = await db.execute(query)
    items = res.scalars().all()
    
    return {
        "items": items,
        "total": total,
        "page": pagination.page,
        "limit": pagination.limit
    }

@router.get("/{id}")
async def get_device(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    res = await db.execute(select(Device).where(Device.id == id))
    device = res.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device

@router.get("/{id}/connections")
async def get_device_connections(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Get connections where this device is either source or target
    # Join with source and target devices to get their info
    from sqlalchemy.orm import joinedload
    res = await db.execute(
        select(DeviceConnection)
        .options(joinedload(DeviceConnection.source_device), joinedload(DeviceConnection.target_device))
        .where(
            or_(
                DeviceConnection.source_device_id == id,
                DeviceConnection.target_device_id == id
            )
        )
    )
    connections = res.scalars().all()
    
    result = []
    for conn in connections:
        is_source = conn.source_device_id == id
        other_device = conn.target_device if is_source else conn.source_device
        
        # Check if other_device is a peripheral with new_peripheral flag
        # We need to find the component record for this device if it exists
        new_peripheral = False
        if other_device.serial_number:
            comp_res = await db.execute(
                select(DeviceComponent.new_peripheral)
                .where(DeviceComponent.serial_number == other_device.serial_number)
                .limit(1)
            )
            new_peripheral = comp_res.scalar() or False

        result.append({
            "id": str(conn.id),
            "source_device_id": str(conn.source_device_id),
            "target_device_id": str(conn.target_device_id),
            "connection_type": conn.connection_type,
            "port_name": conn.port_name,
            "slot_name": conn.slot_name,
            "status": conn.status,
            "other_device": {
                "id": str(other_device.id),
                "hostname": other_device.hostname,
                "device_type": other_device.device_type,
                "status": other_device.status,
                "last_seen": other_device.last_seen.isoformat() if other_device.last_seen else None,
                "new_peripheral": new_peripheral,
                "baud_rate": other_device.baud_rate
            }
        })
    
    return result

@router.get("/{id}/components")
async def get_device_components(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    res = await db.execute(
        select(DeviceComponent).where(
            and_(DeviceComponent.device_id == id, DeviceComponent.removed_date == None)
        )
    )
    return res.scalars().all()

@router.get("/components/{id}/history")
async def get_component_history(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # First get the component to find its serial number
    res = await db.execute(select(DeviceComponent).where(DeviceComponent.id == id))
    comp = res.scalar_one_or_none()
    if not comp or not comp.serial_number:
        return []
    
    # Find all components with the same serial number across all devices
    res = await db.execute(
        select(DeviceComponent, Device.hostname)
        .join(Device, DeviceComponent.device_id == Device.id)
        .where(DeviceComponent.serial_number == comp.serial_number)
        .order_by(DeviceComponent.installation_date.desc())
    )
    history = []
    for c, hostname in res.all():
        history.append({
            "id": str(c.id),
            "device_id": str(c.device_id),
            "hostname": hostname,
            "installation_date": c.installation_date.isoformat() if c.installation_date else None,
            "removed_date": c.removed_date.isoformat() if c.removed_date else None,
            "status": c.status
        })
    return history

@router.post("/")
async def create_device(
    device_data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    device = Device(**device_data)
    db.add(device)
    await db.commit()
    await db.refresh(device)
    
    audit_service = AuditService(db)
    await audit_service.log(
        action="CREATE_DEVICE",
        resource_type="DEVICE",
        resource_id=str(device.id),
        user_id=current_user.id,
        details={"hostname": device.hostname, "serial_number": device.serial_number}
    )
    
    return device

@router.put("/{id}")
async def update_device(
    id: UUID,
    device_data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    res = await db.execute(select(Device).where(Device.id == id))
    device = res.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    repo = DeviceRepository(db)
    updated_device = await repo.update(device, device_data)
    
    audit_service = AuditService(db)
    await audit_service.log(
        action="UPDATE_DEVICE",
        resource_type="DEVICE",
        resource_id=str(updated_device.id),
        user_id=current_user.id,
        details=device_data,
        old_data=getattr(updated_device, "_old_data", None)
    )
    
    return updated_device

@router.delete("/{id}")
async def delete_device(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    res = await db.execute(select(Device).where(Device.id == id))
    device = res.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    hostname = device.hostname
    
    from datetime import datetime
    device.deleted_at = datetime.utcnow()
    await db.commit()
    
    audit_service = AuditService(db)
    await audit_service.log(
        action="DELETE_DEVICE",
        resource_type="DEVICE",
        resource_id=str(id),
        user_id=current_user.id,
        details={"hostname": hostname}
    )
    
    return {"status": "deleted"}

@router.post("/{id}/check-in")
async def device_check_in(
    id: UUID,
    check_in_data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    res = await db.execute(select(Device).where(Device.id == id))
    device = res.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    device.last_seen = datetime.utcnow()
    # Update other fields if provided (e.g. location)
    if "location" in check_in_data:
        # Assuming we have a location mapping or just store it in details for now
        pass
        
    await db.commit()
    await db.refresh(device)
    
    return {"status": "success", "last_seen": device.last_seen}

@router.put("/{id}/approve")
async def approve_device(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(PermissionChecker(["asset.admin"]))
):
    res = await db.execute(select(Device).where(Device.id == id))
    device = res.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    if device.status != "PENDING_APPROVAL":
        raise HTTPException(status_code=400, detail="Device is not in PENDING_APPROVAL status")
    
    device.status = "ACTIVE"
    await db.commit()
    await db.refresh(device)
    
    audit_service = AuditService(db)
    await audit_service.log(
        action="APPROVE_DEVICE",
        resource_type="DEVICE",
        resource_id=str(device.id),
        user_id=current_user.id,
        details={"hostname": device.hostname}
    )
    
    return device

@router.put("/{id}/reject")
async def reject_device(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(PermissionChecker(["asset.admin"]))
):
    res = await db.execute(select(Device).where(Device.id == id))
    device = res.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    if device.status != "PENDING_APPROVAL":
        raise HTTPException(status_code=400, detail="Device is not in PENDING_APPROVAL status")
    
    device.status = "REJECTED"
    await db.commit()
    await db.refresh(device)
    
    audit_service = AuditService(db)
    await audit_service.log(
        action="REJECT_DEVICE",
        resource_type="DEVICE",
        resource_id=str(device.id),
        user_id=current_user.id,
        details={"hostname": device.hostname}
    )
    
    return device

@router.patch("/{device_id}/components/{component_id}/approve")
async def approve_component(
    device_id: UUID,
    component_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(PermissionChecker(["asset.admin"]))
):
    res = await db.execute(
        select(DeviceComponent).where(
            and_(DeviceComponent.id == component_id, DeviceComponent.device_id == device_id)
        )
    )
    comp = res.scalar_one_or_none()
    if not comp:
        raise HTTPException(status_code=404, detail="Component not found")
    
    comp.new_peripheral = False
    await db.commit()
    await db.refresh(comp)
    
    audit_service = AuditService(db)
    await audit_service.log(
        action="APPROVE_COMPONENT",
        resource_type="DEVICE_COMPONENT",
        resource_id=str(comp.id),
        user_id=current_user.id,
        details={"device_id": str(device_id), "component_type": comp.component_type}
    )
    
    return comp

@router.patch("/{device_id}/components/{component_id}/reject")
async def reject_component(
    device_id: UUID,
    component_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(PermissionChecker(["asset.admin"]))
):
    res = await db.execute(
        select(DeviceComponent).where(
            and_(DeviceComponent.id == component_id, DeviceComponent.device_id == device_id)
        )
    )
    comp = res.scalar_one_or_none()
    if not comp:
        raise HTTPException(status_code=404, detail="Component not found")
    
    comp.invalid_serial = True
    await db.commit()
    await db.refresh(comp)
    
    audit_service = AuditService(db)
    await audit_service.log(
        action="REJECT_COMPONENT",
        resource_type="DEVICE_COMPONENT",
        resource_id=str(comp.id),
        user_id=current_user.id,
        details={"device_id": str(device_id), "component_type": comp.component_type, "reason": "Marked as Invalid Serial"}
    )
    
    return comp

@router.get("/{id}/status-history")
async def get_device_status_history(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(PermissionChecker("asset.view"))
):
    """Retrieve historical status changes for a device."""
    from backend.src.contexts.asset.models import DeviceStatusHistory
    res = await db.execute(
        select(DeviceStatusHistory)
        .where(DeviceStatusHistory.device_id == id)
        .order_by(DeviceStatusHistory.created_at.desc())
    )
    return res.scalars().all()

@router.get("/{id}/qr")
async def get_device_qr(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(PermissionChecker("asset.view"))
):
    """Generate QR code data for physical labeling."""
    res = await db.execute(select(Device).where(Device.id == id))
    device = res.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    # Mock QR data generation
    return {
        "device_id": str(id),
        "asset_tag": device.asset_tag,
        "qr_data": f"CITMS:ASSET:{device.asset_tag or str(id)}",
        "qr_url": f"https://citms.internal/assets/{id}"
    }
