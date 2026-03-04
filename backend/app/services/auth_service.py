import jwt
import bcrypt
import hashlib
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from typing import Dict, Any, Optional

from app.core.config import settings

def _hash_password(password: str) -> bytes:
    """
    SHA-256 pre-hash then bcrypt.
    Pre-hashing lets us safely handle passwords > 72 bytes
    while keeping bcrypt's cost factor protection.
    """
    digest = hashlib.sha256(password.encode("utf-8")).hexdigest().encode("utf-8")
    return bcrypt.hashpw(digest, bcrypt.gensalt())

class AuthService:
    """Core logic for Authentication: Password hashing and JWT generation"""
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        digest = hashlib.sha256(plain_password.encode("utf-8")).hexdigest().encode("utf-8")
        return bcrypt.checkpw(digest, hashed_password.encode("utf-8") if isinstance(hashed_password, str) else hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        return _hash_password(password).decode("utf-8")

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        
        # In a real system, we'd sign with the secret algorithm setting
        encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        return encoded_jwt

    @staticmethod
    def decode_access_token(token: str) -> Dict[str, Any]:
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token signature has expired",
            )
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            )
