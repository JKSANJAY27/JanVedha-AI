"""
Shared Gemini LLM client for all AI pipeline agents.
Uses langchain_google_genai with the Gemini Flash model for fast inference.
"""
from functools import lru_cache
from langchain_google_genai import ChatGoogleGenerativeAI
from app.core.config import settings


@lru_cache(maxsize=1)
def get_llm(model: str = "gemini-1.5-flash") -> ChatGoogleGenerativeAI:
    """
    Returns a cached LangChain Gemini LLM instance.
    Cached with lru_cache so only one client is created per model name per process.
    """
    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0.2,
        max_retries=3,
    )


def get_pro_llm() -> ChatGoogleGenerativeAI:
    """Returns Gemini Pro model for complex reasoning tasks."""
    return get_llm(model="gemini-1.5-pro")
