"""
Auth API — register and login, fully MongoDB-backed.
"""
from fastapi import APIRouter, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import Depends
from pydantic import BaseModel, EmailStr

from app.services.auth_service import AuthService
from app.core.session_manager import SessionManager
from app.mongodb.models.user import UserMongo
from app.enums import UserRole

router = APIRouter()


class PublicUserRegister(BaseModel):
    name: str
    email: EmailStr
    phone: str
    password: str


@router.post("/register/public", status_code=status.HTTP_201_CREATED)
async def register_public_user(data: PublicUserRegister):
    # Check uniqueness
    if await UserMongo.find_one(UserMongo.email == data.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    if await UserMongo.find_one(UserMongo.phone == data.phone):
        raise HTTPException(status_code=400, detail="Phone already registered")

    new_user = UserMongo(
        name=data.name,
        email=data.email,
        phone=data.phone,
        password_hash=AuthService.get_password_hash(data.password),
        role=UserRole.PUBLIC_USER,
    )
    await new_user.insert()
    return {"message": "User registered successfully", "user_id": str(new_user.id)}


@router.post("/login")
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    user = await UserMongo.find_one(UserMongo.email == form_data.username)
    if not user or not AuthService.verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    import secrets
    user_id_str = str(user.id)
    access_token = AuthService.create_access_token(data={"sub": user_id_str, "role": user.role})
    refresh_token = secrets.token_urlsafe(32)

    await SessionManager.create_session(user_id_str, refresh_token, 86400 * 7)

    response.set_cookie(
        key="refresh_token", value=refresh_token,
        httponly=True, secure=True, samesite="lax",
        max_age=86400 * 7
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user_id_str,
            "name": user.name,
            "role": user.role,
            "ward_id": user.ward_id,
            "zone_id": user.zone_id,
            "dept_id": user.dept_id,
        }
    }


@router.post("/refresh")
async def refresh(request: Request, response: Response):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token missing")

    try:
        payload = AuthService.decode_access_token(refresh_token)
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("No sub")
    except Exception:
        response.delete_cookie("refresh_token")
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    is_valid = await SessionManager.verify_session(user_id, refresh_token)
    if not is_valid:
        response.delete_cookie("refresh_token")
        raise HTTPException(status_code=401, detail="Session expired or invalidated")

    from beanie import PydanticObjectId
    user = await UserMongo.get(PydanticObjectId(user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User invalid")

    access_token = AuthService.create_access_token(data={"sub": user_id, "role": user.role})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout")
async def logout(request: Request, response: Response):
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        try:
            payload = AuthService.decode_access_token(refresh_token)
            user_id = payload.get("sub")
            if user_id:
                await SessionManager.delete_session(user_id, refresh_token)
        except Exception:
            pass
    response.delete_cookie("refresh_token")
    return {"status": "Logged out successfully"}
