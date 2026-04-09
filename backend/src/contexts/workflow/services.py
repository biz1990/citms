from datetime import datetime
import uuid
from typing import List, Optional, Any
from uuid import UUID
from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
from backend.src.contexts.workflow.models import WorkflowRequest, WorkflowStatus, WorkflowType, DeviceAssignment, ApprovalHistory
from backend.src.contexts.asset.models import Device, DeviceComponent
from backend.src.contexts.itsm.models import Ticket, TicketStatus, TicketPriority
from fastapi import HTTPException

class OnboardingOffboardingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def process_onboarding(self, request_id: UUID, device_ids: List[UUID]):
        """Complete onboarding by assigning devices to user."""
        res = await self.db.execute(select(WorkflowRequest).where(WorkflowRequest.id == request_id))
        request = res.scalar_one_or_none()
        if not request or request.type != WorkflowType.ONBOARDING:
            raise HTTPException(status_code=400, detail="Invalid onboarding request")

        for d_id in device_ids:
            # 1. Create Device Assignment
            assignment = DeviceAssignment(
                device_id=d_id,
                user_id=request.user_id,
                assigned_at=datetime.utcnow(),
                condition_on_assign="GOOD",
                qr_code_token=f"qr_{uuid.uuid4().hex}"
            )
            self.db.add(assignment)
            
            # 2. Update Device Status
            await self.db.execute(
                update(Device)
                .where(Device.id == d_id)
                .values(assigned_to_id=request.user_id, status="IN_USE")
            )

        request.status = WorkflowStatus.COMPLETED
        await self.db.commit()

    async def process_offboarding(self, request_id: UUID):
        """Handle offboarding: scan devices, create recovery tickets, handle internal components."""
        res = await self.db.execute(select(WorkflowRequest).where(WorkflowRequest.id == request_id))
        request = res.scalar_one_or_none()
        if not request or request.type != WorkflowType.OFFBOARDING:
            raise HTTPException(status_code=400, detail="Invalid offboarding request")

        # 1. Find all devices assigned to user
        res = await self.db.execute(
            select(Device).where(
                and_(Device.assigned_to_id == request.user_id, Device.deleted_at == None)
            )
        )
        devices = res.scalars().all()

        for device in devices:
            # 2. Create Recovery Ticket in ITSM
            ticket = Ticket(
                title=f"Device Recovery: {device.hostname} (User: {request.user_id})",
                description=f"Offboarding recovery for device {device.id}",
                status=TicketStatus.OPEN,
                priority=TicketPriority.HIGH,
                reporter_id=request.requested_by,
                device_id=device.id
            )
            self.db.add(ticket)
            
            # 3. Handle Internal Components (is_internal = TRUE)
            # These components stay with the device, but status might change to 'PENDING_INSPECTION'
            await self.db.execute(
                update(DeviceComponent)
                .where(and_(DeviceComponent.device_id == device.id, DeviceComponent.is_internal == True))
                .values(status="PENDING_INSPECTION")
            )
            
            # 4. Mark Device as 'PENDING_RECOVERY'
            device.status = "PENDING_RECOVERY"
            device.assigned_to_id = None # Unassign from user

        request.status = WorkflowStatus.COMPLETED
        await self.db.commit()

class WorkflowService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_request(self, data: dict) -> WorkflowRequest:
        request = WorkflowRequest(**data)
        request.status = WorkflowStatus.PENDING_IT
        self.db.add(request)
        await self.db.commit()
        await self.db.refresh(request)
        return request

    async def approve_request(self, request_id: UUID, approver_id: UUID, comments: str = None):
        """Record approval in history and move to PREPARING with Inventory check."""
        res = await self.db.execute(select(WorkflowRequest).where(WorkflowRequest.id == request_id))
        request = res.scalar_one_or_none()
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")

        # Inventory Check for Onboarding
        if request.type == WorkflowType.ONBOARDING:
            from sqlalchemy import func
            # Check for available devices (IN_STOCK)
            stock_res = await self.db.execute(
                select(func.count(Device.id)).where(and_(Device.status == "IN_STOCK", Device.deleted_at == None))
            )
            stock_count = stock_res.scalar()
            
            if stock_count == 0:
                from backend.src.contexts.notification.services.event_bus import EventPublisher, EventType
                await EventPublisher.publish(EventType.PROCUREMENT_REQUIRED, request_id, {
                    "request_type": "ONBOARDING",
                    "user_id": str(request.user_id),
                    "reason": "Insufficient stock for onboarding"
                })
                raise HTTPException(status_code=400, detail="Insufficient inventory for onboarding. Procurement required.")

        history = ApprovalHistory(
            request_id=request_id,
            approver_id=approver_id,
            status="APPROVED",
            comments=comments,
            step_name="IT_APPROVAL"
        )
        self.db.add(history)
        
        request.status = WorkflowStatus.PREPARING
        await self.db.commit()
        await self.db.refresh(request)
        return request

    async def cancel_request(self, request_id: UUID, user_id: UUID) -> WorkflowRequest:
        """Cancel a pending or preparing request."""
        res = await self.db.execute(select(WorkflowRequest).where(WorkflowRequest.id == request_id))
        request = res.scalar_one_or_none()
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")
        
        if request.status not in [WorkflowStatus.PENDING_IT, WorkflowStatus.PREPARING]:
            raise HTTPException(status_code=400, detail="Only pending or preparing requests can be cancelled")
            
        request.status = WorkflowStatus.CANCELLED
        await self.db.commit()
        await self.db.refresh(request)
        return request
