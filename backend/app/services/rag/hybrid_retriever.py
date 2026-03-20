"""
Hybrid Retriever

Merges semantic searches from ChromaDB and exact-keyword searches from BM25 
using Reciprocal Rank Fusion (RRF).
"""
import logging
from typing import List, Dict, Any

from app.services.rag.embedder import get_embedder
from app.services.rag.vector_store import get_vector_store
from app.services.rag.bm25_store import get_bm25_store
from app.core.config import settings

logger = logging.getLogger(__name__)

def reciprocal_rank_fusion(vector_results, bm25_results, k=60):
    """
    Fuses two ranked lists using Reciprocal Rank Fusion.
    Score = 1 / (k + rank)
    """
    fused_scores = {}
    fused_docs = {}
    fused_metas = {}

    # Process Vector Results
    if vector_results and vector_results.get('ids') and vector_results['ids'][0]:
        v_ids = vector_results['ids'][0]
        v_docs = vector_results['documents'][0]
        v_metas = vector_results['metadatas'][0]
        
        for rank, doc_id in enumerate(v_ids):
            if doc_id not in fused_scores:
                fused_scores[doc_id] = 0.0
                fused_docs[doc_id] = v_docs[rank]
                fused_metas[doc_id] = v_metas[rank]
            fused_scores[doc_id] += 1.0 / (k + rank + 1)
            
    # Process BM25 Results
    if bm25_results and bm25_results.get('ids') and bm25_results['ids'][0]:
        b_ids = bm25_results['ids'][0]
        b_docs = bm25_results['documents'][0]
        b_metas = bm25_results['metadatas'][0]
        
        for rank, doc_id in enumerate(b_ids):
            if doc_id not in fused_scores:
                fused_scores[doc_id] = 0.0
                fused_docs[doc_id] = b_docs[rank]
                fused_metas[doc_id] = b_metas[rank]
            fused_scores[doc_id] += 1.0 / (k + rank + 1)

    # Sort by fused score descending
    sorted_fusion = sorted(fused_scores.items(), key=lambda item: item[1], reverse=True)
    
    # Return top N
    top_n = settings.RAG_TOP_K
    result_docs = []
    result_metas = []
    
    for doc_id, score in sorted_fusion[:top_n]:
        meta = fused_metas[doc_id].copy()
        meta['rrf_score'] = score
        result_docs.append(fused_docs[doc_id])
        result_metas.append(meta)
        
    logger.debug(f"Fused results length: {len(result_docs)}")
    return result_docs, result_metas

class HybridRetriever:
    def __init__(self):
        self.embedder = get_embedder()
        self.vector_store = get_vector_store()
        self.bm25_store = get_bm25_store()
        
    def retrieve(self, query: str) -> List[Dict[str, Any]]:
        """
        Executes query on both vector and lexical stores and fuses the results.
        Returns a combined list of {text, metadata} dicts.
        """
        # Retrieve extra and then fuse down to RAG_TOP_K
        top_k = settings.RAG_TOP_K * 2  
        
        logger.info(f"Retrieving candidate chunks for query: '{query}'")
        
        # 1. Vector Search
        query_embedding = self.embedder.embed_query(query)
        vector_results = self.vector_store.query(query_embedding, n_results=top_k)
        
        # 2. Lexical Search
        bm25_results = self.bm25_store.query(query, n_results=top_k)
        
        # 3. Fuse Results (RRF)
        docs, metas = reciprocal_rank_fusion(vector_results, bm25_results)
        
        return [{"text": docs[i], "metadata": metas[i]} for i in range(len(docs))]
        
# Singleton instance
_retriever_instance = None
def get_hybrid_retriever() -> HybridRetriever:
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = HybridRetriever()
    return _retriever_instance
