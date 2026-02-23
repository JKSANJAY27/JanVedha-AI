from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel, EmailStr

from app.core.database import get_db
from app.services.auth_service import AuthService
from app.core.session_manager import SessionManager
from app.models.user import User

router = APIRouter()

@router.post("/login")
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    # 1. Fetch user by email (form sets it to 'username')
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()
    
    # 2. Verify existence and password
    if not user or not AuthService.verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    # 3. Create tokens
    access_token = AuthService.create_access_token(data={"sub": str(user.id), "role": user.role})
    import secrets
    refresh_token = secrets.token_urlsafe(32)
    
    # 4. Store session in Redis (7 days TTL)
    await SessionManager.create_session(user.id, refresh_token, 86400 * 7)
    
    # 5. Set HTTP-Only Cookie for Refresh Token
    response.set_cookie(
        key="refresh_token", value=refresh_token,
        httponly=True, secure=True, samesite="lax",
        max_age=86400 * 7
    )
    
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "name": user.name,
            "role": user.role,
            "ward_id": user.ward_id,
            "zone_id": user.zone_id,
            "dept_id": user.dept_id
        }
    }

@router.post("/refresh")
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    # 1. Get refresh token from cookie
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token missing")
        
    # We don't know the user ID inherently from an opaque token, 
    # but we can pass it in the request or store a reverse map. 
    # simplest approach is to embed user_id explicitly or query finding it.
    # To keep the stub simple and resilient, we will pass explicit `user_id` in headers or body 
    # OR we use a JWT for the refresh token too
    # Let's pivot to making the refresh token a JWT so we can extract user_id easily
    try:
        payload = AuthService.decode_access_token(refresh_token)
        user_id = int(payload.get("sub"))
    except:
        response.delete_cookie("refresh_token")
        raise HTTPException(status_code=401, detail="Invalid refresh token")
        
    # Validate against Redis
    is_valid = await SessionManager.verify_session(user_id, refresh_token)
    if not is_valid:
        response.delete_cookie("refresh_token")
        raise HTTPException(status_code=401, detail="Session expired or invalidated")
        
    # Generate new access token
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
         raise HTTPException(status_code=401, detail="User invalid")
         
    access_token = AuthService.create_access_token(data={"sub": str(user.id), "role": user.role})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/logout")
async def logout(request: Request, response: Response):
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        try:
            payload = AuthService.decode_access_token(refresh_token)
            user_id = int(payload.get("sub"))
            await SessionManager.delete_session(user_id, refresh_token)
        except:
            pass # already invalid or expired
    
    # Always clear the cookie
    response.delete_cookie("refresh_token")
    return {"status": "Logged out successfully"}

class PublicUserRegister(BaseModel):
    name: str
    email: EmailStr
    phone: str
    password: str

@router.post("/register/public", status_code=status.HTTP_201_CREATED)
async def register_public_user(
    data: PublicUserRegister,
    db: AsyncSession = Depends(get_db)
):
    # Check if user with email or phone already exists
    result_email = await db.execute(select(User).where(User.email == data.email))
    if result_email.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
        
    result_phone = await db.execute(select(User).where(User.phone == data.phone))
    if result_phone.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Phone already registered")
        
    new_user = User(
        name=data.name,
        email=data.email,
        phone=data.phone,
        password_hash=AuthService.get_password_hash(data.password),
        role="PUBLIC_USER"
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return {"message": "User registered successfully", "user_id": new_user.id}
