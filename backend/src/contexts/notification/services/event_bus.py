import json
from datetime import datetime
from uuid import UUID, uuid4
from typing import Any, Dict, Optional
from backend.src.infrastructure.redis import redis_client

class EventType:
    # License & Compliance
    LICENSE_VIOLATED = "LICENSE_VIOLATED"
    SOFTWARE_BLACKLIST_DETECTED = "SOFTWARE_BLACKLIST_DETECTED"
    SERIAL_CLONE_DETECTED = "SERIAL_CLONE_DETECTED"
    
    # Inventory
    INVENTORY_RECONCILE_NEEDED = "INVENTORY_RECONCILE_NEEDED"
    COMPONENT_UNEXPECTED_MOVE = "COMPONENT_UNEXPECTED_MOVE"
    COMPONENT_NEW_DETECTED = "COMPONENT_NEW_DETECTED"
    PERIPHERAL_NEW_DETECTED = "PERIPHERAL_NEW_DETECTED"
    HARDWARE_SPEC_CHANGED = "HARDWARE_SPEC_CHANGED"
    DEVICE_OFFLINE = "DEVICE_OFFLINE"
    
    # ITSM
    TICKET_SLA_BREACHED = "TICKET_SLA_BREACHED"
    TICKET_NEAR_BREACH = "TICKET_NEAR_BREACH"
    
    # Procurement & Workflow
    SPARE_PARTS_BELOW_MIN = "SPARE_PARTS_BELOW_MIN"
    PROCUREMENT_REQUIRED = "PROCUREMENT_REQUIRED"
    PO_PENDING_APPROVAL = "PO_PENDING_APPROVAL"
    WORKFLOW_PENDING_IT = "WORKFLOW_PENDING_IT"
    OFFBOARDING_FAILED = "OFFBOARDING_FAILED"
    
    # Security & General
    SECURITY_LOGIN_FAILED = "SECURITY_LOGIN_FAILED"
    INTEGRITY_WARNING = "INTEGRITY_WARNING"
    DEVICE_STATUS_CHANGED = "DEVICE_STATUS_CHANGED"
    WARRANTY_EXPIRING_30_DAYS = "WARRANTY_EXPIRING_30_DAYS"
    LICENSE_EXPIRING_30_DAYS = "LICENSE_EXPIRING_30_DAYS"
    ASSET_DEPRECIATION_ALERT = "ASSET_DEPRECIATION_ALERT"

class EventPublisher:
    @staticmethod
    async def publish(
        event_type: str, 
        aggregate_id: UUID, 
        payload: Dict[str, Any], 
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Publish a standardized event to Redis Streams."""
        stream_map = {
            EventType.LICENSE_VIOLATED: "citms:license:events",
            EventType.SOFTWARE_BLACKLIST_DETECTED: "citms:license:events",
            EventType.SERIAL_CLONE_DETECTED: "citms:license:events",
            EventType.INVENTORY_RECONCILE_NEEDED: "citms:inventory:events",
            EventType.COMPONENT_UNEXPECTED_MOVE: "citms:inventory:events",
            EventType.DEVICE_OFFLINE: "citms:inventory:events",
            EventType.TICKET_SLA_BREACHED: "citms:itsm:events",
            EventType.TICKET_NEAR_BREACH: "citms:itsm:events",
            EventType.PO_PENDING_APPROVAL: "citms:procurement:events",
            EventType.SPARE_PARTS_BELOW_MIN: "citms:procurement:events",
            EventType.WORKFLOW_PENDING_IT: "citms:workflow:events",
            EventType.SECURITY_LOGIN_FAILED: "citms:security:events"
        }
        
        stream_name = stream_map.get(event_type, "citms:general:events")
        
        event = {
            "event_id": str(uuid4()),
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "aggregate_id": str(aggregate_id),
            "payload": json.dumps(payload),
            "metadata": json.dumps(metadata or {"source": "CITMS_Backend"})
        }
        
        # Publish to Redis Stream
        await redis_client.xadd(stream_name, event, maxlen=100000)
        
        # Note: In CITMS 3.6, a separate RedisStreamConsumer worker 
        # listens to these streams and dispatches to NotificationService.
        # Direct Celery call removed as per decoupling requirements.
