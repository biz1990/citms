from typing import Optional, Any, Dict
from datetime import datetime
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from backend.src.contexts.auth.models import AuditLog

class AuditService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None,
        status: str = "SUCCESS",
        details: Optional[Dict[str, Any]] = None,
        old_data: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ):
        """
        Creates an audit log entry. If old_data is provided, it calculates a diff.
        """
        processed_details = details
        if old_data and details:
            # Module 10: Store only diff JSON
            processed_details = self._calculate_diff(old_data, details)

        audit_entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            status=status,
            details=processed_details,
            ip_address=ip_address,
            created_at=datetime.utcnow()
        )
        self.db.add(audit_entry)
        await self.db.commit()
        return audit_entry

    def _calculate_diff(self, old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
        """Calculates differences between two dictionaries."""
        diff = {}
        # We only care about fields that exist in 'new'
        for key, new_val in new.items():
            if key in ["updated_at", "version"]: continue
            if key not in old or old[key] != new_val:
                diff[key] = {
                    "old": old.get(key),
                    "new": new_val
                }
        return diff
