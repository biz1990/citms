from __future__ import annotations
from sqlalchemy import String, ForeignKey, DateTime, Boolean, Integer, JSON, text, Numeric, Index
from sqlalchemy.dialects.postgresql import UUID, INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.src.infrastructure.models.base import CITMSBaseModel
from backend.src.infrastructure.database import Base
from typing import Optional, List
from datetime import datetime
import uuid

class Location(CITMSBaseModel):
    __tablename__ = "locations"
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(String(255))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    country: Mapped[Optional[str]] = mapped_column(String(100))

class Device(CITMSBaseModel):
    __tablename__ = "devices"
    __table_args__ = (
        Index(
            "idx_device_serial_unique", 
            "serial_number", 
            unique=True, 
            postgresql_where=text("deleted_at IS NULL")
        ),
        Index(
            "idx_device_hostname_unique", 
            "hostname", 
            unique=True, 
            postgresql_where=text("deleted_at IS NULL")
        ),
    )
    
    asset_tag: Mapped[Optional[str]] = mapped_column(String(50))
    name: Mapped[Optional[str]] = mapped_column(String(100))
    device_type: Mapped[Optional[str]] = mapped_column(String(50))
    device_subtype: Mapped[Optional[str]] = mapped_column(String(30))
    manufacturer: Mapped[Optional[str]] = mapped_column(String(100))
    model: Mapped[Optional[str]] = mapped_column(String(100))
    serial_number: Mapped[Optional[str]] = mapped_column(String(100))
    uuid: Mapped[Optional[str]] = mapped_column(String(36))
    primary_mac: Mapped[Optional[str]] = mapped_column(String(17))
    bluetooth_mac: Mapped[Optional[str]] = mapped_column(String(17))
    hostname: Mapped[Optional[str]] = mapped_column(String(100))
    network_ipv4: Mapped[Optional[str]] = mapped_column(INET)
    os_name: Mapped[Optional[str]] = mapped_column(String(50))
    os_version: Mapped[Optional[str]] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(30), default="IN_USE")
    
    assigned_to_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    location_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("locations.id"))
    
    rustdesk_id: Mapped[Optional[str]] = mapped_column(String(50))
    agent_token_hash: Mapped[Optional[str]] = mapped_column(String(255))
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    com_port: Mapped[Optional[str]] = mapped_column(String(20))
    baud_rate: Mapped[Optional[int]] = mapped_column(Integer)
    dock_serial: Mapped[Optional[str]] = mapped_column(String(100))
    
    invalid_serial: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_asset_tag: Mapped[Optional[str]] = mapped_column(String(50))
    alternative_macs: Mapped[dict] = mapped_column(JSONB, default=text("'[]'::jsonb"))
    last_reconciled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Financial fields for depreciation
    purchase_price: Mapped[Optional[float]] = mapped_column(Numeric(15, 2))
    purchase_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    depreciation_years: Mapped[Optional[int]] = mapped_column(Integer, default=5)
    salvage_value: Mapped[Optional[float]] = mapped_column(Numeric(15, 2), default=0)

    # Relationships
    components: Mapped[List[DeviceComponent]] = relationship(back_populates="device", cascade="all, delete-orphan")
    installations: Mapped[List[SoftwareInstallation]] = relationship(back_populates="device", cascade="all, delete-orphan")

class DeviceComponent(CITMSBaseModel):
    __tablename__ = "device_components"
    
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.id"))
    component_type: Mapped[str] = mapped_column(String(50))
    serial_number: Mapped[Optional[str]] = mapped_column(String(100))
    model: Mapped[Optional[str]] = mapped_column(String(100))
    manufacturer: Mapped[Optional[str]] = mapped_column(String(100))
    specifications: Mapped[dict] = mapped_column(JSONB, default=text("'{}'::jsonb"))
    slot_name: Mapped[Optional[str]] = mapped_column(String(50))
    is_internal: Mapped[bool] = mapped_column(Boolean, default=True)
    new_peripheral: Mapped[bool] = mapped_column(Boolean, default=False)
    invalid_serial: Mapped[bool] = mapped_column(Boolean, default=False)
    installation_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    removed_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")

    device: Mapped["Device"] = relationship(back_populates="components")

class DeviceConnection(CITMSBaseModel):
    __tablename__ = "device_connections"
    
    source_device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.id"))
    target_device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.id"))
    connection_type: Mapped[str] = mapped_column(String(50)) # e.g., LAN, WAN, USB, DOCK
    port_name: Mapped[Optional[str]] = mapped_column(String(50))
    slot_name: Mapped[Optional[str]] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    
    source_device: Mapped["Device"] = relationship("Device", foreign_keys=[source_device_id])
    target_device: Mapped["Device"] = relationship("Device", foreign_keys=[target_device_id])

class DeviceStatusHistory(Base):
    __tablename__ = "device_status_history"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.id"), nullable=False)
    old_status: Mapped[Optional[str]] = mapped_column(String(30))
    new_status: Mapped[str] = mapped_column(String(30))
    changed_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, server_default=text("NOW()"))
    
    device: Mapped["Device"] = relationship("Device")
