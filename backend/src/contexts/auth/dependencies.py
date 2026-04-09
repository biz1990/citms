from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from backend.src.core.config import settings
from backend.src.infrastructure.database import get_db
from backend.src.contexts.auth.repositories import UserRepository
from backend.src.contexts.auth.models import User
from backend.src.contexts.auth.services import RBACService
from sqlalchemy import or_
import uuid

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

class DataScope:
    def __init__(self, user: User):
        self.user = user
        self.roles = [r.name for r in user.roles]
        self.is_admin = "SUPER_ADMIN" in self.roles or "IT_MANAGER" in self.roles
        self.is_it_staff = "IT_STAFF" in self.roles
        self.is_dept_head = "DEPARTMENT_HEAD" in self.roles
        
    def apply_isolation(self, query, model):
        """Apply row-level filtering based on user's department/location and soft delete."""
        # Always filter out soft-deleted records if the model has deleted_at
        if hasattr(model, "deleted_at"):
            query = query.where(model.deleted_at == None)
            
        if self.is_admin:
            return query
            
        filters = []
        
        # IT Staff see data in their location
        if self.is_it_staff and hasattr(model, "location_id") and self.user.location_id:
            filters.append(model.location_id == self.user.location_id)
            
        # Dept Head see data in their department
        if self.is_dept_head and hasattr(model, "department_id") and self.user.department_id:
            filters.append(model.department_id == self.user.department_id)
            
        # Regular users see their own data
        if not (self.is_admin or self.is_it_staff or self.is_dept_head):
            if hasattr(model, "assigned_to_id"):
                filters.append(model.assigned_to_id == self.user.id)
            elif hasattr(model, "reporter_id"):
                filters.append(model.reporter_id == self.user.id)
            elif hasattr(model, "user_id"):
                filters.append(model.user_id == self.user.id)
                
        if filters:
            return query.where(or_(*filters))
        return query

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user_repo = UserRepository(db)
    user = await user_repo.get_user_with_permissions(uuid.UUID(user_id))
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
        
    # Module 6: Immediate Power Refresh
    # If DB permissions differ from JWT permissions, force token refresh
    db_permissions = sorted(list(set([p.code for role in user.roles for p in role.permissions])))
    jwt_permissions = sorted(payload.get("permissions", []))
    
    if db_permissions != jwt_permissions:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User permissions have changed. Please refresh token.",
            headers={"WWW-Authenticate": "Bearer", "X-Action": "REFRESH_TOKEN"}
        )

    return user

async def get_data_scope(current_user: User = Depends(get_current_user)) -> DataScope:
    return DataScope(current_user)

class PermissionChecker:
    def __init__(self, permission_code: str):
        self.permission_code = permission_code

    def __call__(self, current_user: User = Depends(get_current_user)):
        if not RBACService.check_permission(current_user, self.permission_code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {self.permission_code}"
            )
        return True
