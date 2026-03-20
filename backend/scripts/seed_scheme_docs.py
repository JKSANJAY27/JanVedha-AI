"""
One-Time Seeding Script

Run this script to parse all documents in backend/app/services/rag/scheme_docs
into chunks, compute embeddings, and store them in ChromaDB and BM25.
"""
import sys
import os

# Add the backend dir to the python path so imports work cleanly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.rag.ingestor import get_ingestor

def main():
    print("Initializing Document Ingestor pipeline...")
    docs_path = os.path.join(os.path.dirname(__file__), '..', 'app', 'services', 'rag', 'scheme_docs')
    docs_path = os.path.abspath(docs_path)
    
    ingestor = get_ingestor()
    ingestor.ingest_directory(docs_path)

if __name__ == "__main__":
    main()
