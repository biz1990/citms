from sqlalchemy import String, ForeignKey, DateTime, Boolean, Integer, JSON, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.src.infrastructure.models.base import CITMSBaseModel
from backend.src.infrastructure.database import Base
from typing import Optional, List
from datetime import datetime
import uuid

class SoftwareCatalog(CITMSBaseModel):
    __tablename__ = "software_catalog"
    
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    publisher: Mapped[Optional[str]] = mapped_column(String(100))
    regex_pattern: Mapped[Optional[str]] = mapped_column(String(255))
    
    installations: Mapped[List["SoftwareInstallation"]] = relationship(back_populates="catalog")

class SoftwareInstallation(CITMSBaseModel):
    __tablename__ = "software_installations"
    
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.id"))
    software_catalog_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("software_catalog.id"))
    version: Mapped[Optional[str]] = mapped_column(String(50))
    install_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    license_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("software_licenses.id"))
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    
    device: Mapped["Device"] = relationship(back_populates="installations")
    catalog: Mapped["SoftwareCatalog"] = relationship(back_populates="installations")

class InventoryRunLog(Base): # Spec 3.8: Raw logs, no soft-delete, no versioning
    __tablename__ = "inventory_run_logs"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inventory_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    device_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("devices.id"))
    status: Mapped[str] = mapped_column(String(20))
    error_message: Mapped[Optional[str]] = mapped_column(String)
    processing_time_ms: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, server_default=text("NOW()"))

class ReconciliationConflict(CITMSBaseModel):
    __tablename__ = "reconciliation_conflicts"
    
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.id"))
    field_name: Mapped[str] = mapped_column(String(50))
    agent_value: Mapped[Optional[str]] = mapped_column(String)
    manual_value: Mapped[Optional[str]] = mapped_column(String)
    agent_reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    server_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(20), default="PENDING") # PENDING, RESOLVED, IGNORED
    resolution_choice: Mapped[Optional[str]] = mapped_column(String(20)) # AGENT, MANUAL
    
    device: Mapped["Device"] = relationship("Device")
