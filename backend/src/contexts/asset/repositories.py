from backend.src.infrastructure.repositories.base import BaseRepository
from backend.src.contexts.asset.models import Device

class DeviceRepository(BaseRepository[Device]):
    def __init__(self, db):
        super().__init__(Device, db)
