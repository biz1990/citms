import re
import time
from datetime import datetime
from typing import List, Optional, Any
from uuid import UUID
from sqlalchemy import select, and_, update, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from backend.src.contexts.asset.models import Device, DeviceComponent, DeviceConnection, DeviceStatusHistory
from backend.src.contexts.inventory.models import SoftwareCatalog, SoftwareInstallation, InventoryRunLog
from backend.src.contexts.inventory.schemas import InventoryReportRequest, InventoryReportResponse
from backend.src.contexts.notification.services.event_bus import EventPublisher, EventType
from backend.src.contexts.license.services.license import LicenseService
from backend.src.contexts.license.models import SoftwareLicense
from fastapi import HTTPException

import secrets
from backend.src.core.security import get_agent_token_hash

class InventoryIngestionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.license_service = LicenseService(db)

    async def process_report(self, report: InventoryReportRequest) -> InventoryReportResponse:
        start_time = time.time()
        
        # 1. Idempotency Check
        existing_run = await self.db.execute(
            select(InventoryRunLog).where(InventoryRunLog.inventory_run_id == report.inventory_run_id)
        )
        if existing_run.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Inventory run ID already processed")

        # 2. Identify Device
        device = await self._identify_device(report)
        is_new = False
        new_agent_token = None
        
        is_invalid_serial = not self._is_valid_serial(report.serial_number)
        auto_tag = None
        if is_invalid_serial:
            auto_tag = f"AUTO-{report.primary_mac.replace(':', '').upper()}"

        if not device:
            # Generate a secure random token for the agent
            new_agent_token = secrets.token_urlsafe(32)
            token_hash = get_agent_token_hash(new_agent_token)
            
            # Auto-classify
            dtype, dsubtype = self._classify_device_type(report)
            
            device = Device(
                hostname=report.hostname,
                primary_mac=report.primary_mac,
                bluetooth_mac=report.bluetooth_mac,
                serial_number=report.serial_number,
                uuid=str(report.uuid) if report.uuid else None,
                device_type=dtype,
                device_subtype=dsubtype,
                manufacturer=report.manufacturer,
                model=report.model,
                os_name=report.os_name,
                os_version=report.os_version,
                network_ipv4=report.network_ipv4,
                com_port=report.com_port,
                baud_rate=report.baud_rate,
                dock_serial=report.dock_serial,
                status="PENDING_APPROVAL", # SRS §10.2: Manual Approval Flow
                agent_token_hash=token_hash,
                invalid_serial=is_invalid_serial,
                auto_asset_tag=auto_tag,
                asset_tag=auto_tag if is_invalid_serial else None
            )
            self.db.add(device)
            await self.db.flush() # Get device.id
            # Log initial status
            self.db.add(DeviceStatusHistory(
                device_id=device.id,
                new_status=device.status,
                reason="INITIAL_REGISTRATION"
            ))
            
            # Audit Log for Registration
            from backend.src.contexts.auth.audit_service import AuditService
            audit_service = AuditService(self.db)
            await audit_service.log(
                action="AGENT_REGISTRATION_REQUEST",
                resource_type="DEVICE",
                resource_id=str(device.id),
                details={"hostname": device.hostname, "status": "PENDING_APPROVAL", "invalid_serial": is_invalid_serial}
            )
        else:
            # Check for status change
            old_status = device.status
            new_status = device.status # Default
            
            # Logic: If it was OFFLINE, it's now ONLINE (handled via websocket/webhook usually, 
            # but ingestion also counts as 'online' activity)
            
            # Update basic info
            device.last_seen = datetime.utcnow()
            device.hostname = report.hostname
            device.network_ipv4 = report.network_ipv4
            device.os_version = report.os_version
            device.invalid_serial = is_invalid_serial
            device.com_port = report.com_port
            device.baud_rate = report.baud_rate
            device.dock_serial = report.dock_serial
            
            # Re-classify if needed
            dtype, dsubtype = self._classify_device_type(report)
            device.device_type = dtype
            device.device_subtype = dsubtype
            
            if old_status != device.status:
                self.db.add(DeviceStatusHistory(
                    device_id=device.id,
                    old_status=old_status,
                    new_status=device.status,
                    reason="INVENTORY_INGESTION_UPDATE"
                ))
                await EventPublisher.publish(
                    EventType.DEVICE_STATUS_CHANGED,
                    device.id,
                    {"old_status": old_status, "new_status": device.status}
                )

            if is_invalid_serial and not device.asset_tag:
                device.auto_asset_tag = auto_tag
                device.asset_tag = auto_tag

        # Update MAC history
        await self._update_alternative_macs(device, report)

        # Update Connections (Dock, COM, etc.)
        await self._sync_device_connections(device, report)

        # 3. Process data (allowed for the first registration report to provide context)
        # Check Serial Blacklist
        if report.serial_number and not is_invalid_serial:
            await self.license_service.check_serial_blacklist(report.serial_number, device.id)

        # 4. FULL_REPLACE Components
        await self._sync_components(device, report.components)

        # 5. FULL_REPLACE Software (Regex Mapping + License Assignment)
        await self._sync_software(device, report.software)

        # 6. Log Run
        processing_time = int((time.time() - start_time) * 1000)
        run_log = InventoryRunLog(
            inventory_run_id=report.inventory_run_id,
            device_id=device.id,
            status="SUCCESS",
            processing_time_ms=processing_time
        )
        self.db.add(run_log)
        
        # 7. Refresh Materialized Views for Reports
        try:
            await self.db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_inventory_summary"))
        except Exception:
            # Fallback if MV doesn't exist or concurrent refresh fails
            pass
        
        await self.db.commit()
        
        return InventoryReportResponse(
            device_id=device.id,
            status="PROCESSED" if not is_new else "PENDING_APPROVAL",
            processed_at=datetime.utcnow(),
            agent_token=new_agent_token
        )

    async def _identify_device(self, report: InventoryReportRequest) -> Optional[Device]:
        # Priority 1: Serial Number (if valid)
        if report.serial_number and self._is_valid_serial(report.serial_number):
            res = await self.db.execute(select(Device).where(Device.serial_number == report.serial_number))
            if d := res.scalar_one_or_none(): return d

        # Priority 2: UUID (if valid)
        if report.uuid and self._is_valid_uuid(report.uuid):
            res = await self.db.execute(select(Device).where(Device.uuid == str(report.uuid)))
            if d := res.scalar_one_or_none(): return d

        # Priority 3: MAC Address (Primary or Alternative)
        # Check primary mac
        res = await self.db.execute(select(Device).where(Device.primary_mac == report.primary_mac))
        if d := res.scalar_one_or_none(): return d

        # Check alternative macs
        res = await self.db.execute(
            select(Device).where(Device.alternative_macs.contains([{"mac": report.primary_mac}]))
        )
        if d := res.scalar_one_or_none(): return d
        
        for net in report.all_macs:
            res = await self.db.execute(
                select(Device).where(Device.alternative_macs.contains([{"mac": net.mac_address}]))
            )
            if d := res.scalar_one_or_none(): return d

        # Priority 4: Hostname + Motherboard (Manufacturer + Model) -> Auto Merge Logic
        if report.hostname and report.manufacturer and report.model:
            res = await self.db.execute(
                select(Device).where(
                    and_(
                        Device.hostname == report.hostname,
                        Device.manufacturer == report.manufacturer,
                        Device.model == report.model,
                        Device.deleted_at == None
                    )
                )
            )
            if d := res.scalar_one_or_none():
                return d

        return None

    def _is_valid_serial(self, serial: str) -> bool:
        if not serial: return False
        # Spec v3.6: Complex regex to filter common invalid serials
        pattern = r"^(?!(0|12345678|Default string|To be filled by O\.E\.M\.|None|Unknown|Not Applicable))[a-zA-Z0-9\-\.]{5,30}$"
        if not re.match(pattern, serial, re.IGNORECASE):
            return False
        
        # Additional blacklist patterns
        invalid_patterns = [
            r"0123456789", r"1234567890",
            r"^0+$", r"^F+$"
        ]
        for pattern in invalid_patterns:
            if re.search(pattern, serial, re.IGNORECASE):
                return False
        return len(serial) > 4

    def _is_valid_uuid(self, uuid_str: str) -> bool:
        if not uuid_str: return False
        invalid_uuids = ["00000000-0000-0000-0000-000000000000", "ffffffff-ffff-ffff-ffff-ffffffffffff"]
        return uuid_str.lower() not in invalid_uuids

    async def _update_alternative_macs(self, device: Device, report: InventoryReportRequest):
        current_macs = device.alternative_macs or []
        existing_mac_vals = {m["mac"] for m in current_macs}
        
        new_macs_found = False
        
        if report.primary_mac not in existing_mac_vals:
            current_macs.append({
                "mac": report.primary_mac,
                "type": "PRIMARY",
                "first_seen": datetime.utcnow().isoformat()
            })
            existing_mac_vals.add(report.primary_mac)
            new_macs_found = True
            
        for net in report.all_macs:
            if net.mac_address not in existing_mac_vals:
                current_macs.append({
                    "mac": net.mac_address,
                    "type": net.type or "UNKNOWN",
                    "interface": net.name,
                    "first_seen": datetime.utcnow().isoformat()
                })
                existing_mac_vals.add(net.mac_address)
                new_macs_found = True
        
        if new_macs_found:
            device.alternative_macs = current_macs
            from backend.src.contexts.auth.audit_service import AuditService
            audit_service = AuditService(self.db)
            await audit_service.log(
                action="DEVICE_MAC_ADDED",
                resource_type="DEVICE",
                resource_id=str(device.id),
                details={"new_macs": list(existing_mac_vals)}
            )

    async def _sync_components(self, device: Device, reported_components: List[Any]):
        # Get current active components
        res = await self.db.execute(
            select(DeviceComponent).where(
                and_(DeviceComponent.device_id == device.id, DeviceComponent.removed_date == None)
            )
        )
        current_components = {c.serial_number or f"{c.component_type}_{c.slot_name}": c for c in res.scalars().all()}
        
        reported_keys = set()
        for rc in reported_components:
            key = rc.serial_number or f"{rc.component_type}_{rc.slot_name}"
            reported_keys.add(key)
            
            if key in current_components:
                # Update existing
                comp = current_components[key]
                
                # Deep JSONB Diff for hardware downgrades
                old_spec = comp.specifications or {}
                new_spec = rc.specifications or {}
                downgrades = []
                for field in ["ram_gb", "cpu_cores", "disk_gb"]:
                    if field in old_spec and field in new_spec:
                        try:
                            if float(new_spec[field]) < float(old_spec[field]):
                                downgrades.append(f"{field}: {old_spec[field]} -> {new_spec[field]}")
                        except (ValueError, TypeError):
                            pass
                
                if downgrades:
                    await EventPublisher.publish(EventType.HARDWARE_SPEC_CHANGED, device.id, {
                        "component_id": str(comp.id),
                        "component_type": comp.component_type,
                        "downgrades": downgrades
                    })

                comp.specifications = rc.specifications
                comp.status = "ACTIVE"
                comp.slot_name = rc.slot_name
            else:
                # Add new
                is_peripheral = not rc.is_internal or rc.component_type in ["SCANNER", "PRINTER", "PCI_CARD", "PCIE_CARD"]
                
                new_comp = DeviceComponent(
                    device_id=device.id,
                    component_type=rc.component_type,
                    serial_number=rc.serial_number,
                    model=rc.model,
                    manufacturer=rc.manufacturer,
                    specifications=rc.specifications,
                    slot_name=rc.slot_name,
                    is_internal=rc.is_internal,
                    new_peripheral=is_peripheral,
                    installation_date=datetime.utcnow()
                )
                self.db.add(new_comp)
                
                # Publish Event for New Component/Peripheral
                event_type = EventType.PERIPHERAL_NEW_DETECTED if is_peripheral else EventType.COMPONENT_NEW_DETECTED
                await EventPublisher.publish(event_type, device.id, {
                    "component_type": rc.component_type,
                    "model": rc.model,
                    "serial_number": rc.serial_number,
                    "slot_name": rc.slot_name
                })

                # Handle Device Connections for Cards and Peripherals
                if is_peripheral:
                    await self._create_peripheral_connection(device, rc)

                # Check if this component was on another device (Unexpected Move)
                if rc.serial_number:
                    other_res = await self.db.execute(
                        select(DeviceComponent).where(
                            and_(DeviceComponent.serial_number == rc.serial_number, DeviceComponent.device_id != device.id)
                        )
                    )
                    if other := other_res.scalar_one_or_none():
                        await EventPublisher.publish(EventType.COMPONENT_UNEXPECTED_MOVE, device.id, {
                            "component_id": str(other.id),
                            "old_device_id": str(other.device_id),
                            "new_device_id": str(device.id)
                        })

        # Mark removed
        for key, comp in current_components.items():
            if key not in reported_keys:
                comp.removed_date = datetime.utcnow()
                comp.status = "REMOVED"

    async def _create_peripheral_connection(self, device: Device, rc: Any):
        """Creates a DeviceConnection for a peripheral or expansion card."""
        if not rc.serial_number: return

        # Find or create target device for the peripheral
        res = await self.db.execute(select(Device).where(Device.serial_number == rc.serial_number))
        target = res.scalar_one_or_none()
        
        if not target:
            target = Device(
                serial_number=rc.serial_number,
                device_type=rc.component_type,
                manufacturer=rc.manufacturer,
                model=rc.model,
                status="ACTIVE",
                hostname=f"PERIPHERAL-{rc.serial_number}"
            )
            self.db.add(target)
            await self.db.flush()

        # Determine connection type
        conn_type = "USB"
        if "pci" in rc.component_type.lower(): conn_type = "PCIe" if "pcie" in rc.component_type.lower() else "PCI"
        elif "com" in rc.component_type.lower() or rc.port_name and "com" in rc.port_name.lower(): conn_type = "COM"

        # Create connection
        conn_res = await self.db.execute(
            select(DeviceConnection).where(
                and_(
                    DeviceConnection.source_device_id == device.id,
                    DeviceConnection.target_device_id == target.id,
                    DeviceConnection.connection_type == conn_type
                )
            )
        )
        if not conn_res.scalar_one_or_none():
            conn = DeviceConnection(
                source_device_id=device.id,
                target_device_id=target.id,
                connection_type=conn_type,
                port_name=rc.port_name,
                slot_name=rc.slot_name,
                status="ACTIVE"
            )
            self.db.add(conn)

    async def _sync_device_connections(self, device: Device, report: InventoryReportRequest):
        """Handles high-level connections like Dock Pairing or COM Scanners."""
        # 1. Dock Pairing
        if report.dock_serial:
            res = await self.db.execute(select(Device).where(Device.serial_number == report.dock_serial))
            dock = res.scalar_one_or_none()
            if not dock:
                dock = Device(
                    serial_number=report.dock_serial,
                    device_type="DOCK",
                    status="ACTIVE",
                    hostname=f"DOCK-{report.dock_serial}"
                )
                self.db.add(dock)
                await self.db.flush()
            
            # Link
            conn_res = await self.db.execute(
                select(DeviceConnection).where(
                    and_(
                        DeviceConnection.source_device_id == device.id,
                        DeviceConnection.target_device_id == dock.id,
                        DeviceConnection.connection_type == "DOCK_PAIRING"
                    )
                )
            )
            if not conn_res.scalar_one_or_none():
                self.db.add(DeviceConnection(
                    source_device_id=device.id,
                    target_device_id=dock.id,
                    connection_type="DOCK_PAIRING"
                ))

    def _classify_device_type(self, report: InventoryReportRequest):
        """Refines device classification based on industrial attributes."""
        dtype = report.device_type
        dsubtype = None

        if report.dock_serial:
            dtype = "SCANNER"
            dsubtype = "SCANNER_WIRELESS"
        elif report.com_port:
            dtype = "SCANNER"
            dsubtype = "SCANNER_COM"
        elif report.manufacturer and "zebra" in report.manufacturer.lower():
            dtype = "SCANNER"
            dsubtype = "SCANNER_WIRED"
        elif report.device_type == "PRINTER":
            dsubtype = "PRINTER_INDUSTRIAL"
        
        return dtype, dsubtype

    async def _sync_software(self, device: Device, reported_software: List[Any]):
        # 1. Get all regex patterns
        res = await self.db.execute(select(SoftwareCatalog).where(SoftwareCatalog.regex_pattern != None))
        catalogs = res.scalars().all()
        
        # 2. Map reported strings to catalog IDs
        mapped_installations = []
        for rs in reported_software:
            # Check Software Blacklist
            is_blacklisted = await self.license_service.check_software_blacklist(rs.raw_name, device.id)
            
            catalog_id = None
            for cat in catalogs:
                if re.search(cat.regex_pattern, rs.raw_name, re.IGNORECASE):
                    catalog_id = cat.id
                    break
            
            if not catalog_id:
                # Create unknown catalog entry for later normalization
                new_cat = SoftwareCatalog(name=rs.raw_name)
                self.db.add(new_cat)
                await self.db.flush()
                catalog_id = new_cat.id
            
            mapped_installations.append({
                "catalog_id": catalog_id,
                "version": rs.version,
                "install_date": rs.install_date
            })

        # 3. FULL_REPLACE logic
        # Get current installations
        res = await self.db.execute(
            select(SoftwareInstallation).where(
                and_(SoftwareInstallation.device_id == device.id, SoftwareInstallation.deleted_at == None)
            )
        )
        current_installs = {str(si.software_catalog_id): si for si in res.scalars().all()}
        
        reported_ids = set()
        for mi in mapped_installations:
            cid_str = str(mi["catalog_id"])
            reported_ids.add(cid_str)
            
            if cid_str not in current_installs:
                # New installation (Trigger will handle used_seats)
                # Check if this catalog entry is blacklisted (deep check)
                is_blacklisted = await self.license_service.check_software_blacklist(mi["catalog_id"], device.id)
                
                new_si = SoftwareInstallation(
                    device_id=device.id,
                    software_catalog_id=mi["catalog_id"],
                    version=mi["version"],
                    install_date=mi["install_date"] or datetime.utcnow(),
                    is_blocked=is_blacklisted
                )
                self.db.add(new_si)
                await self.db.flush()
                
                # Auto-assign license
                await self.license_service.auto_assign_license(mi["catalog_id"], new_si.id)
        
        # Remove missing (Trigger will handle used_seats)
        removed_license_ids = set()
        for cid_str, si in current_installs.items():
            if cid_str not in reported_ids:
                if si.license_id:
                    removed_license_ids.add(si.license_id)
                si.deleted_at = datetime.utcnow()
        
        if removed_license_ids:
            await self.db.flush()
            # Verify used_seats consistency after transaction
            for lid in removed_license_ids:
                count_res = await self.db.execute(
                    select(func.count(SoftwareInstallation.id))
                    .where(and_(SoftwareInstallation.license_id == lid, SoftwareInstallation.deleted_at == None))
                )
                actual_count = count_res.scalar()
                
                lic_res = await self.db.execute(select(SoftwareLicense).where(SoftwareLicense.id == lid))
                lic = lic_res.scalar_one_or_none()
                
                if lic and lic.used_seats != actual_count:
                    await EventPublisher.publish(EventType.INTEGRITY_WARNING, lid, {
                        "entity": "SoftwareLicense",
                        "field": "used_seats",
                        "expected": actual_count,
                        "actual": lic.used_seats
                    })
