import json
from datetime import datetime
from uuid import UUID
from typing import List, Dict, Any
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from backend.src.contexts.auth.models import User, Role
from backend.src.contexts.notification.models import Notification
from backend.src.contexts.notification.services.websocket import ws_manager
from backend.src.infrastructure.database import AsyncSessionLocal

class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def process_event(self, event: Dict[str, Any]):
        """Process an event and send notifications to relevant users with Throttling."""
        event_type = event["event_type"]
        payload = json.loads(event["payload"])
        
        # 1. Determine target users based on event type
        target_users = await self._get_target_users(event_type)
        
        from backend.src.infrastructure.redis import redis_client
        
        for user in target_users:
            # Throttling: Group alert by (user, alert_type) within 5-minute window
            throttle_key = f"notif_throttle:{user.id}:{event_type}"
            if await redis_client.get(throttle_key):
                continue
            
            # Set throttle key for 5 minutes
            await redis_client.setex(throttle_key, 300, "1")
            
            # 2. Check user preferences
            # Example preferences: {"notifications": {"LICENSE_VIOLATED": ["WS", "EMAIL"], "DEVICE_OFFLINE": ["WS"]}}
            prefs = user.preferences or {}
            notif_prefs = prefs.get("notifications", {}).get(event_type, ["WS"]) # Default to WS
            
            # 3. Create Notification History
            notif = Notification(
                user_id=user.id,
                title=f"CITMS Alert: {event_type}",
                message=self._generate_message(event_type, payload),
                event_type=event_type,
                priority=self._get_priority(event_type),
                metadata_json=payload
            )
            self.db.add(notif)
            
            # 4. Send Realtime (WebSocket)
            if "WS" in notif_prefs:
                await ws_manager.send_personal_message({
                    "id": str(notif.id),
                    "title": notif.title,
                    "message": notif.message,
                    "event_type": notif.event_type,
                    "priority": notif.priority,
                    "timestamp": datetime.utcnow().isoformat()
                }, str(user.id))
            
            # 5. Send Email (Celery)
            if "EMAIL" in notif_prefs:
                from backend.src.contexts.notification.tasks import send_email_task
                send_email_task.delay(user.email, notif.title, notif.message)

        await self.db.commit()

    async def _get_target_users(self, event_type: str) -> List[User]:
        """Find users who should receive this notification based on roles."""
        # Mapping event types to roles
        role_map = {
            "LICENSE_VIOLATED": ["IT_MANAGER", "SUPER_ADMIN"],
            "SOFTWARE_BLACKLIST_DETECTED": ["IT_STAFF", "IT_MANAGER"],
            "SERIAL_CLONE_DETECTED": ["IT_STAFF", "IT_MANAGER"],
            "INVENTORY_RECONCILE_NEEDED": ["IT_STAFF"],
            "TICKET_SLA_BREACHED": ["IT_MANAGER"],
            "PO_PENDING_APPROVAL": ["IT_MANAGER", "SUPER_ADMIN"],
            "WORKFLOW_PENDING_IT": ["IT_STAFF"],
            "DEVICE_STATUS_CHANGED": ["IT_STAFF", "IT_MANAGER"],
            "OFFBOARDING_FAILED": ["IT_MANAGER", "SUPER_ADMIN"],
            "WARRANTY_EXPIRING_30_DAYS": ["IT_STAFF"],
            "LICENSE_EXPIRING_30_DAYS": ["IT_MANAGER"],
            "BLACKLIST_VIOLATION": ["IT_STAFF", "IT_MANAGER"],
            "SPARE_PARTS_BELOW_MIN": ["IT_STAFF"],
            "ASSET_DEPRECIATION_ALERT": ["IT_MANAGER"]
        }
        
        target_roles = role_map.get(event_type, ["IT_STAFF"])
        
        res = await self.db.execute(
            select(User).join(User.role).where(Role.name.in_(target_roles))
        )
        return res.scalars().all()

    def _generate_message(self, event_type: str, payload: Dict[str, Any]) -> str:
        # Simplified message generation
        return f"Event {event_type} detected. Details: {json.dumps(payload)}"

    def _get_priority(self, event_type: str) -> str:
        high_priority = ["LICENSE_VIOLATED", "TICKET_SLA_BREACHED", "SECURITY_LOGIN_FAILED"]
        return "HIGH" if event_type in high_priority else "MEDIUM"
