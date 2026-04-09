from datetime import datetime
from typing import List, Optional, Any
from uuid import UUID
from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
from backend.src.contexts.itsm.models import Ticket, TicketStatus, TicketPriority, TicketComment
from backend.src.contexts.itsm.repositories import TicketRepository
from backend.src.contexts.itsm.services.sla import SlaService
from backend.src.contexts.auth.audit_service import AuditService
from fastapi import HTTPException

class TicketService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.sla_service = SlaService(db)
        self.audit_service = AuditService(db)
        self.repo = TicketRepository(db)

    async def create_ticket(self, data: dict, user_id: Optional[UUID] = None) -> Ticket:
        """Create a new ticket and calculate SLA."""
        ticket = Ticket(**data)
        ticket.status = TicketStatus.OPEN
        
        # Calculate SLA
        ticket.sla_deadline = await self.sla_service.calculate_deadline(
            datetime.utcnow(), 
            ticket.priority
        )
        
        self.db.add(ticket)
        await self.db.commit()
        await self.db.refresh(ticket)
        
        await self.audit_service.log(
            action="CREATE_TICKET",
            resource_type="TICKET",
            resource_id=str(ticket.id),
            user_id=user_id or ticket.requester_id,
            details={"title": ticket.title, "priority": ticket.priority}
        )
        
        return ticket

    async def update_status(self, ticket_id: UUID, new_status: TicketStatus, user_id: UUID) -> Ticket:
        """Handle ticket state transitions."""
        res = await self.db.execute(select(Ticket).where(Ticket.id == ticket_id))
        ticket = res.scalar_one_or_none()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        old_status = ticket.status

        # State Machine Logic
        valid_transitions = {
            TicketStatus.OPEN: [TicketStatus.ASSIGNED, TicketStatus.CANCELLED],
            TicketStatus.ASSIGNED: [TicketStatus.IN_PROGRESS, TicketStatus.PENDING, TicketStatus.CANCELLED],
            TicketStatus.IN_PROGRESS: [TicketStatus.PENDING, TicketStatus.RESOLVED, TicketStatus.CANCELLED],
            TicketStatus.PENDING: [TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED],
            TicketStatus.RESOLVED: [TicketStatus.CLOSED, TicketStatus.IN_PROGRESS],
            TicketStatus.CLOSED: [],
            TicketStatus.CANCELLED: []
        }

        if new_status not in valid_transitions.get(ticket.status, []):
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid transition from {ticket.status} to {new_status}"
            )

        update_data = {"status": new_status, "updated_at": datetime.utcnow()}
        if new_status == TicketStatus.RESOLVED:
            update_data["resolved_at"] = datetime.utcnow()
        elif new_status == TicketStatus.CLOSED:
            update_data["closed_at"] = datetime.utcnow()
        elif new_status == TicketStatus.ASSIGNED and not ticket.assignee_id:
            update_data["assignee_id"] = user_id

        # Use Repository for Optimistic Locking
        updated_ticket = await self.repo.update(ticket, update_data)
        
        await self.audit_service.log(
            action="UPDATE_TICKET_STATUS",
            resource_type="TICKET",
            resource_id=str(updated_ticket.id),
            user_id=user_id,
            details=update_data,
            old_data=getattr(updated_ticket, "_old_data", None)
        )
        
        return updated_ticket

    async def bulk_update_status(self, ticket_ids: List[UUID], new_status: TicketStatus, user_id: UUID):
        """Update status for multiple tickets."""
        await self.db.execute(
            update(Ticket)
            .where(Ticket.id.in_(ticket_ids))
            .values(status=new_status, updated_at=datetime.utcnow())
        )
        await self.db.commit()
        
        for tid in ticket_ids:
            await self.audit_service.log(
                action="BULK_UPDATE_TICKET_STATUS",
                resource_type="TICKET",
                resource_id=str(tid),
                user_id=user_id,
                details={"new_status": new_status}
            )

    async def approve_cab(self, ticket_id: UUID, approver_id: UUID) -> Ticket:
        """Approve a change request ticket."""
        res = await self.db.execute(select(Ticket).where(Ticket.id == ticket_id))
        ticket = res.scalar_one_or_none()
        if not ticket or not ticket.is_change_request:
            raise HTTPException(status_code=400, detail="Invalid change request")

        ticket.cab_approved_at = datetime.utcnow()
        ticket.cab_approver_id = approver_id
        await self.db.commit()
        await self.db.refresh(ticket)
        
        await self.audit_service.log(
            action="APPROVE_CAB",
            resource_type="TICKET",
            resource_id=str(ticket.id),
            user_id=approver_id,
            details={"title": ticket.title}
        )
        
        return ticket
