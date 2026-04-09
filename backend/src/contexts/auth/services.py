from datetime import datetime, timedelta
from typing import Optional, List, Any
from fastapi import HTTPException, status
from backend.src.contexts.auth.repositories import UserRepository, RoleRepository, PermissionRepository
from backend.src.contexts.auth.audit_service import AuditService
from backend.src.contexts.auth.schemas import LoginRequest, TokenResponse, UserResponse
from backend.src.core.security import verify_password, get_password_hash, create_access_token, create_refresh_token
from backend.src.core.config import settings
import uuid

class AuthService:
    def __init__(self, user_repo: UserRepository, audit_service: AuditService):
        self.user_repo = user_repo
        self.audit_service = audit_service

    async def authenticate(self, login_data: LoginRequest) -> TokenResponse:
        user = await self.user_repo.get_by_username(login_data.username)
        
        if not user:
            await self.audit_service.log(
                action="LOGIN_FAILED",
                resource_type="USER",
                details={"username": login_data.username, "reason": "User not found"},
                status="FAILED"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )
            
        # Check Account Lockout
        if user.locked_until and user.locked_until > datetime.utcnow():
            await self.audit_service.log(
                action="LOGIN_LOCKED",
                resource_type="USER",
                user_id=user.id,
                details={"reason": "Account locked"},
                status="FAILED"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Account locked until {user.locked_until}. Please try again later."
            )

        # Mock LDAP Provider check
        if login_data.provider == "LDAP":
            # Mock logic: any password works for LDAP mock
            is_valid = True 
        else:
            is_valid = verify_password(login_data.password, user.password_hash)

        if not is_valid:
            # Increment failed attempts
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= 5:
                user.locked_until = datetime.utcnow() + timedelta(minutes=15)
            
            await self.user_repo.db.commit()
            await self.audit_service.log(
                action="LOGIN_FAILED",
                resource_type="USER",
                user_id=user.id,
                details={"reason": "Invalid password"},
                status="FAILED"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )

        # Reset failed attempts on success
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = datetime.utcnow()
        await self.user_repo.db.commit()

        await self.audit_service.log(
            action="LOGIN_SUCCESS",
            resource_type="USER",
            user_id=user.id,
            status="SUCCESS"
        )

        # Prepare User Response
        user_roles = [role.name for role in user.roles]
        user_permissions = list(set([p.code for role in user.roles for p in role.permissions]))
        
        user_resp = UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            employee_id=user.employee_id,
            department_id=user.department_id,
            is_active=user.is_active,
            roles=user_roles,
            permissions=user_permissions,
            last_login=user.last_login
        )

        access_token = create_access_token(data={
            "sub": str(user.id),
            "permissions": user_permissions,
            "roles": user_roles
        })
        refresh_token = create_refresh_token(data={"sub": str(user.id)})

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user_resp
        )

    async def change_password(self, user_id: uuid.UUID, old_password: str, new_password: str):
        user = await self.user_repo.get(user_id)
        if not verify_password(old_password, user.password_hash):
            await self.audit_service.log(
                action="PASSWORD_CHANGE_FAILED",
                resource_type="USER",
                user_id=user_id,
                details={"reason": "Incorrect old password"},
                status="FAILED"
            )
            raise HTTPException(status_code=400, detail="Incorrect old password")
        
        # Password History Check (last 5)
        for old_hash in user.password_history:
            if verify_password(new_password, old_hash):
                await self.audit_service.log(
                    action="PASSWORD_CHANGE_FAILED",
                    resource_type="USER",
                    user_id=user_id,
                    details={"reason": "Password in history"},
                    status="FAILED"
                )
                raise HTTPException(status_code=400, detail="New password cannot be one of the last 5 passwords used")
        
        # Update History
        user.password_history.append(user.password_hash)
        if len(user.password_history) > 5:
            user.password_history.pop(0)
            
        user.password_hash = get_password_hash(new_password)
        await self.user_repo.db.commit()
        
        await self.audit_service.log(
            action="PASSWORD_CHANGE_SUCCESS",
            resource_type="USER",
            user_id=user_id,
            status="SUCCESS"
        )

class RBACService:
    @staticmethod
    def check_permission(user: Any, required_permission: str) -> bool:
        # Super Admin bypass
        if any(role.name == "SUPER_ADMIN" for role in user.roles):
            return True
            
        user_permissions = set([p.code for role in user.roles for p in role.permissions])
        return required_permission in user_permissions
