from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class SentimentResult:
    positive_pct: float
    negative_pct: float
    neutral_pct: float
    total_analysed: int
    top_negative_keywords: list[str]

class SentimentProvider(ABC):
    @abstractmethod
    async def analyze(self, texts: list[str]) -> SentimentResult:
        pass
