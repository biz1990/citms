from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID
from backend.src.infrastructure.database import get_db
from backend.src.contexts.itsm.schemas import (
    TicketCreate, TicketResponse, TicketStatusUpdate, 
    BulkStatusUpdate, CommentCreate, MaintenanceLogCreate
)
from backend.src.contexts.itsm.services.ticket import TicketService
from backend.src.contexts.itsm.models import Ticket, TicketComment, MaintenanceLog
from backend.src.infrastructure.dependencies.pagination import PaginationParams, get_pagination_params, PaginatedResponse
from backend.src.contexts.auth.dependencies import get_current_user, PermissionChecker, get_data_scope, DataScope
from backend.src.contexts.auth.models import User
from sqlalchemy import select, or_, func

router = APIRouter(prefix="/tickets", tags=["ITSM & Ticket System"])

@router.get("/", response_model=PaginatedResponse[TicketResponse])
async def list_tickets(
    pagination: PaginationParams = Depends(get_pagination_params),
    filter: Optional[str] = None, # SRS 5.4: OData-like filter (status eq 'OPEN')
    priority: Optional[str] = None,
    category: Optional[str] = None,
    assignee_id: Optional[UUID] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    data_scope: DataScope = Depends(get_data_scope),
    _ = Depends(PermissionChecker(["ticket.view"]))
):
    query = select(Ticket)
    
    # Apply Row-Level Security / Data Isolation
    query = data_scope.apply_isolation(query, Ticket)
    
    # Module 5.4: OData-like Filter Parser
    if filter:
        if " eq " in filter:
            field, value = filter.split(" eq ")
            value = value.strip("'").strip("\"")
            if hasattr(Ticket, field):
                query = query.where(getattr(Ticket, field) == value)
        else:
            raise HTTPException(
                status_code=400, 
                detail="Invalid filter format. Expected 'field eq 'value'' (SRS 5.4)"
            )
            
    if priority:
        query = query.where(Ticket.priority == priority)
    if category:
        query = query.where(Ticket.category == category)
    if assignee_id:
        query = query.where(Ticket.assignee_id == assignee_id)
    if search:
        query = query.where(
            or_(
                Ticket.title.ilike(f"%{search}%"),
                Ticket.description.ilike(f"%{search}%")
            )
        )
        
    # Get total count before pagination
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(Ticket.created_at.desc()).offset(pagination.skip).limit(pagination.limit)
    res = await db.execute(query)
    items = res.scalars().all()
    
    return {
        "items": items,
        "total": total,
        "page": pagination.page,
        "limit": pagination.limit
    }

@router.post("/", response_model=TicketResponse)
async def create_ticket(
    ticket_in: TicketCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(PermissionChecker(["ticket.create"]))
):
    service = TicketService(db)
    data = ticket_in.dict()
    data["reporter_id"] = current_user.id
    data["department_id"] = current_user.department_id
    data["location_id"] = current_user.location_id
    return await service.create_ticket(data, current_user.id)

@router.get("/{id}", response_model=TicketResponse)
async def get_ticket(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(PermissionChecker(["ticket.view"]))
):
    res = await db.execute(select(Ticket).where(Ticket.id == id))
    ticket = res.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket

@router.patch("/{id}/status", response_model=TicketResponse)
async def update_ticket_status(
    id: UUID,
    status_in: TicketStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(PermissionChecker(["ticket.update"]))
):
    service = TicketService(db)
    return await service.update_status(id, status_in.status, current_user.id)

@router.patch("/bulk-status", status_code=status.HTTP_200_OK)
async def bulk_update_status(
    bulk_in: BulkStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(PermissionChecker(["ticket.update"]))
):
    service = TicketService(db)
    await service.bulk_update_status(bulk_in.ticket_ids, bulk_in.status, current_user.id)
    return {"status": "success", "updated_count": len(bulk_in.ticket_ids)}

@router.post("/{id}/comments", status_code=status.HTTP_201_CREATED)
async def add_comment(
    id: UUID,
    comment_in: CommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(PermissionChecker(["ticket.comment"]))
):
    comment = TicketComment(
        ticket_id=id,
        author_id=current_user.id,
        content=comment_in.content,
        is_internal=comment_in.is_internal,
        attachments=comment_in.attachments
    )
    db.add(comment)
    await db.commit()
    return {"status": "comment_added"}

@router.patch("/{id}/cab-approve", response_model=TicketResponse)
async def approve_cab(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(PermissionChecker(["ticket.approve"]))
):
    service = TicketService(db)
    return await service.approve_cab(id, current_user.id)

@router.delete("/{id}", status_code=status.HTTP_200_OK)
async def delete_ticket(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(PermissionChecker(["ticket.delete"]))
):
    res = await db.execute(select(Ticket).where(Ticket.id == id))
    ticket = res.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    from datetime import datetime
    ticket.deleted_at = datetime.utcnow()
    await db.commit()
    return {"status": "deleted"}
