"""
Document Ingestion Pipeline

Reads markdown/pdf files from the scheme_docs directory, runs them through the Chunker,
embeds the chunks, and saves them to both ChromaDB and the BM25 store.
"""
import os
import glob
import logging
from typing import List, Dict, Any
import fitz  # PyMuPDF

from app.services.rag.chunker import chunk_text
from app.services.rag.embedder import get_embedder
from app.services.rag.vector_store import get_vector_store
from app.services.rag.bm25_store import get_bm25_store

logger = logging.getLogger(__name__)

class DocumentIngestor:
    def __init__(self):
        self.embedder = get_embedder()
        self.vector_store = get_vector_store()
        self.bm25_store = get_bm25_store()
        
    def ingest_directory(self, directory_path: str):
        """Finds all .md and .pdf files in a directory and ingests them."""
        logger.info(f"Scanning directory {directory_path} for documents to ingest...")
        
        md_files = glob.glob(os.path.join(directory_path, "**/*.md"), recursive=True)
        pdf_files = glob.glob(os.path.join(directory_path, "**/*.pdf"), recursive=True)
        
        all_files = md_files + pdf_files
        if not all_files:
            logger.warning(f"No .md or .pdf files found in {directory_path}")
            return
            
        logger.info(f"Found {len(all_files)} files to ingest.")
        
        all_chunks = []
        
        for file_path in all_files:
            filename = os.path.basename(file_path)
            ext = os.path.splitext(filename)[1].lower()
            
            text = ""
            if ext == '.md':
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
            elif ext == '.pdf':
                try:
                    doc = fitz.open(file_path)
                    text = "\n".join([page.get_text() for page in doc])
                except Exception as e:
                    logger.error(f"Failed to read PDF {file_path}: {e}")
                    continue
                    
            if not text.strip():
                logger.warning(f"File {filename} is empty. Skipping.")
                continue
                
            metadata = {"source": filename}
            chunks = chunk_text(text, source_metadata=metadata)
            all_chunks.extend(chunks)
            
        if not all_chunks:
            logger.warning("No chunks generated from documents.")
            return
            
        logger.info(f"Generated {len(all_chunks)} chunks total. Proceeding to embed and store.")
        self._store_chunks(all_chunks)
        
    def _store_chunks(self, chunks: List[Dict[str, Any]]):
        """Embeds and saves chunks to both Vector and Lexical stores."""
        texts = [chunk["text"] for chunk in chunks]
        metadatas = [chunk["metadata"] for chunk in chunks]
        
        # Generate unique IDs based on filename and chunk_index to ensure overwrites on re-runs
        ids = [f"{m['source']}:chunk_{m['chunk_index']}" for m in metadatas]
        
        logger.info("Computing dense embeddings...")
        embeddings = self.embedder.embed_texts(texts)
        
        logger.info("Saving to ChromaDB...")
        self.vector_store.add_documents(documents=texts, embeddings=embeddings, metadatas=metadatas, ids=ids)
        
        logger.info("Saving to BM25 Store...")
        self.bm25_store.add_documents(documents=texts, metadatas=metadatas, ids=ids)
        
        logger.info("Document ingestion complete.")

# Global instance
_ingestor_instance = None
def get_ingestor() -> DocumentIngestor:
    global _ingestor_instance
    if _ingestor_instance is None:
        _ingestor_instance = DocumentIngestor()
    return _ingestor_instance
