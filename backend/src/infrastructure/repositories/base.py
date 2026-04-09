from __future__ import annotations
from typing import Generic, TypeVar, Type, Optional, List, Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
from backend.src.infrastructure.models.base import CITMSBaseModel
from fastapi import HTTPException, status
from datetime import datetime
import uuid

T = TypeVar("T", bound=CITMSBaseModel)

class BaseRepository(Generic[T]):
    def __init__(self, model: Type[T], db: AsyncSession):
        self.model = model
        self.db = db

    async def get(self, id: uuid.UUID) -> Optional[T]:
        query = select(self.model).where(
            and_(self.model.id == id, self.model.deleted_at == None)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list(self, skip: int = 0, limit: int = 100, filters: Dict[str, Any] = None) -> List[T]:
        query = select(self.model).where(self.model.deleted_at == None)
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    query = query.where(getattr(self.model, key) == value)
        
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def create(self, obj_in: Dict[str, Any]) -> T:
        db_obj = self.model(**obj_in)
        self.db.add(db_obj)
        await self.db.commit()
        await self.db.refresh(db_obj)
        return db_obj

    async def update(self, db_obj: T, obj_in: Dict[str, Any]) -> T:
        # Optimistic Locking implementation
        current_version = db_obj.version
        new_version = current_version + 1
        
        # Capture old data for auditing (Module 10)
        old_data = {c.name: getattr(db_obj, c.name) for c in db_obj.__table__.columns}
        
        update_data = obj_in.copy()
        update_data["version"] = new_version
        update_data["updated_at"] = datetime.utcnow()

        query = (
            update(self.model)
            .where(
                and_(
                    self.model.id == db_obj.id, 
                    self.model.version == current_version
                )
            )
            .values(**update_data)
            .returning(self.model)
        )
        
        result = await self.db.execute(query)
        updated_obj = result.scalar_one_or_none()
        
        if not updated_obj:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "type": "https://citms.internal/errors/optimistic-lock-conflict",
                    "title": "Xung đột cập nhật dữ liệu",
                    "status": 409,
                    "detail": "Bản ghi này đã bị người khác chỉnh sửa trước đó. Vui lòng tải lại trang để xem thay đổi mới nhất.",
                    "extensions": {"current_version": current_version}
                }
            )
            
        await self.db.commit()
        await self.db.refresh(updated_obj)
        
        # Attached old_data for the caller to use in Audit Log
        setattr(updated_obj, "_old_data", old_data)
        return updated_obj

    async def soft_delete(self, db_obj: T) -> bool:
        db_obj.deleted_at = datetime.utcnow()
        self.db.add(db_obj)
        await self.db.commit()
        return True
