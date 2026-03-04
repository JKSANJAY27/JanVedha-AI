import json
import logging
from typing import Optional
from redis.asyncio import Redis
from redis.exceptions import ConnectionError
from app.core.config import settings

logger = logging.getLogger(__name__)
redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)

# In-memory fallback if Redis is not running locally on Windows
_mock_store = {}

class SessionManager:
    """Manages JWT refresh tokens and session active states in Redis with in-memory fallback"""
    
    @staticmethod
    async def create_session(user_id: str, refresh_token: str, expires_in_seconds: int = 86400 * 7) -> None:
        """Store the refresh token against the user ID. Represents an active session."""
        session_data = json.dumps({"refresh_token": refresh_token})
        # Key format: session:{user_id}:{token_suffix} to allow multiple devices
        token_suffix = refresh_token[-10:] 
        key = f"session:{user_id}:{token_suffix}"
        
        try:
            await redis_client.setex(key, expires_in_seconds, session_data)
        except ConnectionError:
            logger.warning("Redis down - using in-memory dict for session")
            _mock_store[key] = session_data
        
    @staticmethod
    async def delete_session(user_id: str, refresh_token: str) -> None:
        """Invalidate a specific session"""
        token_suffix = refresh_token[-10:]
        key = f"session:{user_id}:{token_suffix}"
        
        try:
            await redis_client.delete(key)
        except ConnectionError:
            _mock_store.pop(key, None)
        
    @staticmethod
    async def verify_session(user_id: str, refresh_token: str) -> bool:
        """Check if the session (refresh token) is still valid and not explicitly logged out."""
        token_suffix = refresh_token[-10:]
        key = f"session:{user_id}:{token_suffix}"
        
        try:
            data = await redis_client.get(key)
        except ConnectionError:
            data = _mock_store.get(key)
            
        if not data:
            return False
        session_data = json.loads(data)
        return session_data.get("refresh_token") == refresh_token
