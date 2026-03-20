"""
Document Embedder

Wraps sentence-transformers to convert text into dense vector embeddings.
Uses the `all-MiniLM-L6-v2` model which is small, extremely fast, and sufficiently
accurate for short-to-medium length RAG queries.
"""
from typing import List
import logging
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

class Embedder:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        logger.info(f"Loading embedding model: {self.model_name}...")
        self.model = SentenceTransformer(self.model_name)
        logger.info("Embedding model loaded successfully.")
        
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generates dense vector embeddings for a list of texts."""
        if not texts:
            return []
        embeddings = self.model.encode(texts, show_progress_bar=False)
        return embeddings.tolist()
        
    def embed_query(self, query: str) -> List[float]:
        """Generates dense vector embedding for a single query."""
        embedding = self.model.encode(query, show_progress_bar=False)
        return embedding.tolist()
        

# Singleton instance to prevent loading the model multiple times
_embedder_instance = None
def get_embedder() -> Embedder:
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = Embedder()
    return _embedder_instance
