"""
Singleton Langfuse client setup for JanVedha AI backend.
Provides a central `get_langfuse()` instance and helper wrappers for traces.
"""
import logging
from typing import Optional
from langfuse import Langfuse
from app.core.config import settings

logger = logging.getLogger(__name__)

_langfuse_client: Optional[Langfuse] = None

def get_langfuse() -> Langfuse:
    """
    Returns the singleton Langfuse instance.
    Initializes lazily if not already present.
    """
    global _langfuse_client
    if _langfuse_client is None:
        if not settings.LANGFUSE_PUBLIC_KEY or not settings.LANGFUSE_SECRET_KEY:
            logger.warning("Langfuse API keys are missing. Traces will not be captured successfully.")
            
        # The Langfuse SDK handles retries and background task submission automatically
        _langfuse_client = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST,
        )
        logger.info(f"Langfuse client initialized for host: {settings.LANGFUSE_HOST}")
        
    return _langfuse_client

def flush():
    """Flushes the event queue. Used primarily during app shutdown to prevent data loss."""
    if _langfuse_client is not None:
        _langfuse_client.flush()
