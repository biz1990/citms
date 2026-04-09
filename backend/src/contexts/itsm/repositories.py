from backend.src.infrastructure.repositories.base import BaseRepository
from backend.src.contexts.itsm.models import Ticket

class TicketRepository(BaseRepository[Ticket]):
    def __init__(self, db):
        super().__init__(Ticket, db)
