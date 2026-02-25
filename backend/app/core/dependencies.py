"""
Core dependencies — JWT auth + RBAC guards.
Rewritten to use MongoDB (UserMongo) instead of SQLAlchemy.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.services.auth_service import AuthService
from app.mongodb.models.user import UserMongo

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UserMongo:
    """Validates JWT and fetches the user from MongoDB."""
    token = credentials.credentials
    try:
        payload = AuthService.decode_access_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise ValueError("No sub in token")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    from beanie import PydanticObjectId
    try:
        user = await UserMongo.get(PydanticObjectId(user_id))
    except Exception:
        user = None

    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    return user


async def require_ward_officer(user: UserMongo = Depends(get_current_user)) -> UserMongo:
    allowed = {"WARD_OFFICER", "ZONAL_OFFICER", "DEPT_HEAD", "COMMISSIONER", "SUPER_ADMIN"}
    if user.role not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="INSUFFICIENT_ROLE")
    return user


async def require_commissioner(user: UserMongo = Depends(get_current_user)) -> UserMongo:
    if user.role != "COMMISSIONER":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="COMMISSIONER_ROLE_REQUIRED")
    return user


async def require_admin(user: UserMongo = Depends(get_current_user)) -> UserMongo:
    if user.role not in {"SUPER_ADMIN", "COMMISSIONER"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ADMIN_ROLE_REQUIRED")
    return user
