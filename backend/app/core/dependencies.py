from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.services.auth_service import AuthService
from app.models.user import User
from app.core.rbac import ROLE_PERMISSIONS, can_view_ward

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Validates JWT, fetches user from DB."""
    token = credentials.credentials
    try:
        payload = AuthService.decode_access_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Could not validate credentials")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
        
    return user

async def require_ward_officer(user: User = Depends(get_current_user)) -> User:
    if user.role not in ["WARD_OFFICER", "ZONAL_OFFICER", "DEPT_HEAD",
                          "COMMISSIONER", "SUPER_ADMIN"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="INSUFFICIENT_ROLE")
    return user

async def require_commissioner(user: User = Depends(get_current_user)) -> User:
    if user.role != "COMMISSIONER":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="COMMISSIONER_ROLE_REQUIRED")
    return user
