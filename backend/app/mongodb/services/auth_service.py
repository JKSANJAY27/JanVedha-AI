"""
Service: MongoAuthService

MongoDB port of auth-related logic.
JWT generation and verification are DB-agnostic (handled by the existing
AuthService) — this service adds the MongoDB user look-up layer on top.
"""
from typing import Optional
from datetime import timedelta
from fastapi import HTTPException, status

from app.services.auth_service import AuthService          # re-use JWT logic as-is
from app.core.config import settings
from app.mongodb.models.user import UserMongo
from app.mongodb.repositories.user_repo import UserRepo


class MongoAuthService:
    """Authentication operations using MongoDB user store."""

    # ------------------------------------------------------------------ Login
    @staticmethod
    async def login(phone: str, password: str) -> dict:
        """
        Authenticate a user by phone + password.
        Returns a JWT access token dict on success.
        Raises HTTPException on failure.
        """
        user = await UserRepo.get_by_phone(phone)

        if not user or not user.password_hash:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        if not AuthService.verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user",
            )

        access_token = AuthService.create_access_token(
            data={"sub": str(user.id), "role": user.role},
            expires_delta=timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
        )
        return {"access_token": access_token, "token_type": "bearer"}

    # ------------------------------------------------------------------ Register
    @staticmethod
    async def register_user(
        name: str,
        phone: str,
        password: str,
        role: str,
        email: Optional[str] = None,
        ward_id: Optional[int] = None,
        zone_id: Optional[int] = None,
        dept_id: Optional[str] = None,
    ) -> UserMongo:
        """Create a new user with a hashed password."""
        # Check uniqueness
        if await UserRepo.get_by_phone(phone):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number already registered",
            )
        if email and await UserRepo.get_by_email(email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        user = UserMongo(
            name=name,
            phone=phone,
            email=email,
            password_hash=AuthService.get_password_hash(password),
            role=role,
            ward_id=ward_id,
            zone_id=zone_id,
            dept_id=dept_id,
        )
        return await UserRepo.create(user)

    # ------------------------------------------------------------------ Token → User
    @staticmethod
    async def get_current_user(token: str) -> UserMongo:
        """
        Validate a JWT and return the corresponding UserMongo.
        Drop-in replacement for app/core/dependencies.get_current_user.
        """
        try:
            payload = AuthService.decode_access_token(token)
            user_id: str = payload.get("sub")
            if not user_id:
                raise ValueError("No sub in token")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user = await UserRepo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        if not user.is_active:
            raise HTTPException(status_code=400, detail="Inactive user")

        return user
