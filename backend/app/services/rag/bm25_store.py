"""
BM25 Lexical Store

Indexes documents for exact-keyword search using rank_bm25.
In a local/file-based deployment, we persist the index to a python pickle object alongside ChromaDB.
"""
from rank_bm25 import BM25Okapi
import pickle
import os
import logging
from typing import List, Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)

class BM25Store:
    def __init__(self):
        self.persist_path = os.path.join(
            settings.CHROMA_PERSIST_DIR, 
            f"{settings.CHROMA_SCHEMES_COLLECTION}_bm25.pkl"
        )
        self.bm25 = None
        self.corpus = []
        self.metadatas = []
        self.ids = []
        
        self.load()
        
    def _tokenize(self, text: str) -> List[str]:
        """Simple whitespace/lowercase tokenizer for BM25 processing."""
        return text.lower().split()
        
    def add_documents(self, documents: List[str], metadatas: List[Dict[str, Any]], ids: List[str]):
        """Records new chunk texts and rebuilds the BM25 index."""
        if not documents:
            return
            
        self.corpus.extend(documents)
        self.metadatas.extend(metadatas)
        self.ids.extend(ids)
        
        tokenized_corpus = [self._tokenize(doc) for doc in self.corpus]
        self.bm25 = BM25Okapi(tokenized_corpus)
        logger.info(f"Built BM25 index with {len(self.corpus)} documents.")
        self.save()
        
    def query(self, query: str, n_results: int = 5) -> Dict[str, Any]:
        """Searches the lexical corpus using BM25 scoring."""
        if not self.bm25 or not self.corpus:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
            
        tokenized_query = self._tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)
        
        # In BM25, higher score is better. For hybrid search compatibility where we merge with 
        # ChromaDB (where lower distance is better down the line), we just return scores 
        # as the metric value representing BM25 rank factor.
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:n_results]
        
        result_ids = [self.ids[i] for i in top_indices]
        result_docs = [self.corpus[i] for i in top_indices]
        result_metas = [self.metadatas[i] for i in top_indices]
        result_scores = [scores[i] for i in top_indices]
        
        return {
            "ids": [result_ids],
            "documents": [result_docs],
            "metadatas": [result_metas],
            "distances": [result_scores] # Distance key reused to hold similarity scores
        }
        
    def save(self):
        """Persist BM25 structures to disk."""
        os.makedirs(os.path.dirname(self.persist_path), exist_ok=True)
        with open(self.persist_path, 'wb') as f:
            pickle.dump({
                'corpus': self.corpus,
                'metadatas': self.metadatas,
                'ids': self.ids
            }, f)
        logger.info(f"Saved BM25 index to {self.persist_path}")
            
    def load(self):
        """Load from disk if available."""
        if os.path.exists(self.persist_path):
            try:
                with open(self.persist_path, 'rb') as f:
                    data = pickle.load(f)
                    self.corpus = data.get('corpus', [])
                    self.metadatas = data.get('metadatas', [])
                    self.ids = data.get('ids', [])
                    
                    if self.corpus:
                        tokenized_corpus = [self._tokenize(doc) for doc in self.corpus]
                        self.bm25 = BM25Okapi(tokenized_corpus)
                logger.info(f"Loaded BM25 index with {len(self.corpus)} documents.")
            except Exception as e:
                logger.error(f"Failed to load BM25 index: {e}")
                self.corpus = []
                self.metadatas = []
                self.ids = []
        else:
            logger.info("No BM25 index found, starting fresh.")


# Singleton instance
_bm25_store_instance = None
def get_bm25_store() -> BM25Store:
    global _bm25_store_instance
    if _bm25_store_instance is None:
        _bm25_store_instance = BM25Store()
    return _bm25_store_instance
