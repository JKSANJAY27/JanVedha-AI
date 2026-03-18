"""
Shared Gemini LLM client for all AI pipeline agents.
Uses langchain_google_genai with the Gemini Flash model for fast inference.
"""
from functools import lru_cache
from langchain_google_genai import ChatGoogleGenerativeAI
from app.core.config import settings


@lru_cache(maxsize=1)
def get_llm(model: str = "gemini-2.5-flash") -> ChatGoogleGenerativeAI:
    """
    Gets a standard LangChain LLM instance.
    Defaults to the latest Gemini 1.5 Flash model.
    """
    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0.2,
        max_retries=5, # Increased retries for better robustness
    )


def get_pro_llm() -> ChatGoogleGenerativeAI:
    """Returns Gemini Pro model for complex reasoning tasks."""
    return get_llm(model="gemini-2.5-flash")


def get_classifier_llm() -> ChatGoogleGenerativeAI:
    """Returns Gemini model with best instruction following."""
    # classification requires good instruction following, gemini-2.5-flash is best-effort general-purpose
    return get_llm(model="gemini-2.5-flash")

