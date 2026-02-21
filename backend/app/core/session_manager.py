import json
from typing import Optional
from redis.asyncio import Redis
from app.core.config import settings

redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)

class SessionManager:
    """Manages JWT refresh tokens and session active states in Redis"""
    
    @staticmethod
    async def create_session(user_id: int, refresh_token: str, expires_in_seconds: int = 86400 * 7) -> None:
        """Store the refresh token against the user ID. Represents an active session."""
        session_data = json.dumps({"refresh_token": refresh_token})
        # Key format: session:{user_id}:{token_suffix} to allow multiple devices
        token_suffix = refresh_token[-10:] 
        await redis_client.setex(f"session:{user_id}:{token_suffix}", expires_in_seconds, session_data)
        
    @staticmethod
    async def delete_session(user_id: int, refresh_token: str) -> None:
        """Invalidate a specific session"""
        token_suffix = refresh_token[-10:]
        await redis_client.delete(f"session:{user_id}:{token_suffix}")
        
    @staticmethod
    async def verify_session(user_id: int, refresh_token: str) -> bool:
        """Check if the session (refresh token) is still valid and not explicitly logged out."""
        token_suffix = refresh_token[-10:]
        data = await redis_client.get(f"session:{user_id}:{token_suffix}")
        if not data:
            return False
        session_data = json.loads(data)
        return session_data.get("refresh_token") == refresh_token
