from app.interfaces.sentiment_provider import SentimentProvider, SentimentResult


class HuggingFaceAdapter(SentimentProvider):
    """Stub implementation of HuggingFace sentiment provider."""

    async def analyze(self, texts: list[str]) -> SentimentResult:
        """Stub implementation - returns balanced sentiment."""
        total_texts = len(texts)
        return SentimentResult(
            positive_pct=0.35,
            negative_pct=0.35,
            neutral_pct=0.30,
            total_analysed=total_texts,
            top_negative_keywords=[]
        )
