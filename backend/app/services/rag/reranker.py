"""
Cross-Encoder Reranker

Takes the retrieved candidates from the Hybrid Retriever and rescores them
using a more sophisticated cross-encoder language model to maximize precision.
"""
import logging
from typing import List, Dict, Any
from sentence_transformers import CrossEncoder

from app.core.config import settings

logger = logging.getLogger(__name__)

class Reranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        logger.info(f"Loading reranker model: {self.model_name}...")
        self.model = CrossEncoder(self.model_name)
        logger.info("Reranker model loaded successfully.")
        
    def rerank(self, query: str, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Scores query-document pairs using a cross-encoder model.
        candidates: List of dicts with 'text' and 'metadata'.
        Returns the top RAG_RERANKER_TOP_K chunks, sorted by relevance score.
        """
        if not candidates:
            return []
            
        # Prepare pairs for the cross-encoder: [(query, doc_text), ...]
        pairs = [[query, doc["text"]] for doc in candidates]
        
        # Predict logits
        scores = self.model.predict(pairs)
        
        # Attach scores to candidates
        reranked_candidates = []
        for i, candidate in enumerate(candidates):
            c_copy = candidate.copy()
            c_copy['metadata'] = candidate['metadata'].copy()
            c_copy['metadata']['rerank_score'] = float(scores[i])
            reranked_candidates.append(c_copy)
            
        # Sort descending by score
        reranked_candidates.sort(key=lambda x: x['metadata']['rerank_score'], reverse=True)
        
        top_k = settings.RAG_RERANKER_TOP_K
        if reranked_candidates:
            logger.info(f"Reranking completed. Top score: {reranked_candidates[0]['metadata']['rerank_score']}")
            
        return reranked_candidates[:top_k]

# Singleton instance
_reranker_instance = None
def get_reranker() -> Reranker:
    global _reranker_instance
    if _reranker_instance is None:
        _reranker_instance = Reranker()
    return _reranker_instance
