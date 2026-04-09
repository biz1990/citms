from __future__ import annotations
from datetime import datetime
from typing import Optional, List, Any
import uuid
from sqlalchemy import String, Boolean, DateTime, ForeignKey, JSON, Integer, text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.src.infrastructure.models.base import CITMSBaseModel

class Role(CITMSBaseModel):
    __tablename__ = "roles"
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    # Relationships
    permissions: Mapped[List[Permission]] = relationship(
        secondary="role_permissions", back_populates="roles"
    )
    users: Mapped[List[User]] = relationship(
        secondary="user_roles", back_populates="roles"
    )

class Permission(CITMSBaseModel):
    __tablename__ = "permissions"
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    module: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    # Relationships
    roles: Mapped[List[Role]] = relationship(
        secondary="role_permissions", back_populates="permissions"
    )

class RolePermission(CITMSBaseModel):
    __tablename__ = "role_permissions"
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"))
    permission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("permissions.id", ondelete="CASCADE"))

class User(CITMSBaseModel):
    __tablename__ = "users"
    
    __table_args__ = (
        Index(
            "ix_user_email_active",
            "email",
            unique=True,
            postgresql_where=text("deleted_at IS NULL")
        ),
        Index(
            "ix_user_username_active",
            "username",
            unique=True,
            postgresql_where=text("deleted_at IS NULL")
        ),
    )

    username: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    employee_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("departments.id"), nullable=True)
    location_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("locations.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    auth_provider: Mapped[str] = mapped_column(String(20), default="LOCAL")
    preferences: Mapped[dict] = mapped_column(JSONB, default=text("'{}'::jsonb"))
    
    # Password Policy & Security
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    password_history: Mapped[List[str]] = mapped_column(JSONB, default=text("'[]'::jsonb"))
    
    # Relationships
    roles: Mapped[List[Role]] = relationship(
        secondary="user_roles", back_populates="users"
    )

class UserRole(CITMSBaseModel):
    __tablename__ = "user_roles"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"))
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    assigned_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)

class Department(CITMSBaseModel):
    __tablename__ = "departments"
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("departments.id"), nullable=True)
    manager_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", deferrable=True, initially="DEFERRED"), nullable=True)
    level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

class AuditLog(CITMSBaseModel):
    __tablename__ = "audit_logs"
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(100))
    resource_type: Mapped[str] = mapped_column(String(50))
    resource_id: Mapped[Optional[str]] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20)) # SUCCESS, DENIED, FAILED
    details: Mapped[Optional[dict]] = mapped_column(JSONB)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    
    # Relationships
    user: Mapped[Optional[User]] = relationship(foreign_keys=[user_id])
