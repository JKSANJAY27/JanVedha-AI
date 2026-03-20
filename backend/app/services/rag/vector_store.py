"""
Vector Store Wrapper

Provides a simplified interface over ChromaDB for persistent storage and semantic search
of embedding vectors. Employs cosine similarity for distance calculations.
"""
import chromadb
import logging
from typing import List, Dict, Any

from app.core.config import settings

logger = logging.getLogger(__name__)

class VectorStore:
    def __init__(self):
        self.persist_directory = settings.CHROMA_PERSIST_DIR
        self.collection_name = settings.CHROMA_SCHEMES_COLLECTION
        
        logger.info(f"Initializing ChromaDB client at {self.persist_directory}")
        self.client = chromadb.PersistentClient(path=self.persist_directory)
        
        # Get or create the collection with cosine similarity
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        
    def add_documents(
        self, 
        documents: List[str], 
        embeddings: List[List[float]], 
        metadatas: List[Dict[str, Any]], 
        ids: List[str]
    ):
        """Adds embedded chunks to the ChromaDB collection."""
        if not documents:
            return
            
        self.collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )
        logger.info(f"Added {len(documents)} documents to vector store.")
        
    def query(self, query_embedding: List[float], n_results: int = 5) -> Dict[str, Any]:
        """Queries the vector store for the most semantically similar chunks."""
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=['documents', 'metadatas', 'distances']
        )
        return results

# Singleton instance
_vector_store_instance = None
def get_vector_store() -> VectorStore:
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = VectorStore()
    return _vector_store_instance
