from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from backend.src.contexts.itsm.models import TicketStatus, TicketPriority

class TicketBase(BaseModel):
    title: str = Field(..., min_length=5, max_length=200)
    description: str
    priority: TicketPriority = TicketPriority.MEDIUM
    category: Optional[str] = None
    device_id: Optional[UUID] = None
    vendor_id: Optional[UUID] = None
    is_change_request: bool = False
    change_plan: Optional[str] = None
    rollback_plan: Optional[str] = None

class TicketCreate(TicketBase):
    pass

class TicketUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[TicketPriority] = None
    category: Optional[str] = None
    assignee_id: Optional[UUID] = None

class TicketStatusUpdate(BaseModel):
    status: TicketStatus

class BulkStatusUpdate(BaseModel):
    ticket_ids: List[UUID]
    status: TicketStatus

class CommentCreate(BaseModel):
    content: str
    is_internal: bool = False
    attachments: Optional[Dict[str, Any]] = None

class MaintenanceLogCreate(BaseModel):
    device_id: UUID
    action_taken: str
    spare_parts_used: Optional[Dict[str, Any]] = None
    cost: int = 0

class TicketResponse(TicketBase):
    id: UUID
    status: TicketStatus
    reporter_id: UUID
    assignee_id: Optional[UUID] = None
    sla_deadline: Optional[datetime] = None
    is_sla_breached: bool = False
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    cab_approved_at: Optional[datetime] = None
    cab_approver_id: Optional[UUID] = None
    version: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
