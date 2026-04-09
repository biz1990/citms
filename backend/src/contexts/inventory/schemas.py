from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

class ComponentReport(BaseModel):
    component_type: str
    serial_number: Optional[str] = None
    model: Optional[str] = None
    manufacturer: Optional[str] = None
    specifications: Dict[str, Any] = {}
    slot_name: Optional[str] = None
    port_name: Optional[str] = None
    is_internal: bool = True
    baud_rate: Optional[int] = None

class SoftwareReport(BaseModel):
    raw_name: str
    version: Optional[str] = None
    install_date: Optional[datetime] = None

class NetworkInterfaceReport(BaseModel):
    name: str
    mac_address: str
    ipv4: Optional[str] = None
    type: Optional[str] = None # ETHERNET, WIFI, BLUETOOTH, VIRTUAL

class InventoryReportRequest(BaseModel):
    inventory_run_id: UUID
    hostname: str
    primary_mac: str
    all_macs: List[NetworkInterfaceReport] = []
    serial_number: Optional[str] = None
    uuid: Optional[str] = None
    device_type: str = "COMPUTER"
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    os_name: Optional[str] = None
    os_version: Optional[str] = None
    network_ipv4: Optional[str] = None
    
    # Zebra/COM specific
    bluetooth_mac: Optional[str] = None
    dock_serial: Optional[str] = None
    com_port: Optional[str] = None
    baud_rate: Optional[int] = None
    
    components: List[ComponentReport] = []
    software: List[SoftwareReport] = []

class InventoryReportResponse(BaseModel):
    device_id: UUID
    status: str
    processed_at: datetime
    version: int
    conflicts_detected: bool = False
    agent_token: Optional[str] = None

class SparePartResponse(BaseModel):
    id: UUID
    name: str
    category: str
    manufacturer: Optional[str] = None
    quantity: int
    min_quantity: int
    unit_price: float
    
    class Config:
        from_attributes = True
