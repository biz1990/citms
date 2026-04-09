from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID
from backend.src.infrastructure.database import get_db
from backend.src.contexts.workflow.schemas import (
    WorkflowRequestCreate, WorkflowRequestResponse, 
    WorkflowStatusUpdate, ApprovalRequest, OnboardingCompleteRequest
)
from backend.src.contexts.workflow.services import WorkflowService, OnboardingOffboardingService
from backend.src.contexts.workflow.models import WorkflowRequest, WorkflowType
from backend.src.contexts.auth.dependencies import get_current_user, PermissionChecker
from backend.src.contexts.auth.models import User
from sqlalchemy import select

router = APIRouter(prefix="/workflow", tags=["Workflow & Onboarding"])

@router.get("/requests", response_model=List[WorkflowRequestResponse])
async def list_requests(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(PermissionChecker(["workflow.view"]))
):
    res = await db.execute(select(WorkflowRequest).order_by(WorkflowRequest.created_at.desc()))
    return res.scalars().all()

@router.post("/requests", response_model=WorkflowRequestResponse)
async def create_request(
    request_in: WorkflowRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(PermissionChecker(["workflow.create"]))
):
    service = WorkflowService(db)
    data = request_in.dict()
    data["requested_by"] = current_user.id
    return await service.create_request(data)

@router.patch("/requests/{id}/approve", response_model=WorkflowRequestResponse)
async def approve_request(
    id: UUID,
    approval_in: ApprovalRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(PermissionChecker(["workflow.approve"]))
):
    service = WorkflowService(db)
    return await service.approve_request(id, current_user.id, approval_in.comments)

@router.post("/requests/{id}/complete", status_code=status.HTTP_200_OK)
async def complete_request(
    id: UUID,
    complete_in: Optional[OnboardingCompleteRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(PermissionChecker(["workflow.complete"]))
):
    service = OnboardingOffboardingService(db)
    
    # Get request type
    res = await db.execute(select(WorkflowRequest).where(WorkflowRequest.id == id))
    request = res.scalar_one_or_none()
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    if request.type == WorkflowType.ONBOARDING:
        if not complete_in or not complete_in.device_ids:
            raise HTTPException(status_code=400, detail="Device IDs required for onboarding")
        await service.process_onboarding(id, complete_in.device_ids)
    elif request.type == WorkflowType.OFFBOARDING:
        await service.process_offboarding(id)
    
    return {"status": "success"}

@router.patch("/requests/{id}/cancel", response_model=WorkflowRequestResponse)
async def cancel_workflow_request(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(PermissionChecker(["workflow.create"]))
):
    service = WorkflowService(db)
    return await service.cancel_request(id, current_user.id)

