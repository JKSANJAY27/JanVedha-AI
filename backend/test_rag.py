"""Quick test to verify the RAG retrieval pipeline works after seeding."""
import sys
sys.path.insert(0, '.')

from app.services.rag.hybrid_retriever import get_hybrid_retriever

query = "62 year old widow BPL family SC category income 2000 per month"
print(f"Query: {query}\n")

retriever = get_hybrid_retriever()
results = retriever.retrieve(query)

print(f"Retrieved {len(results)} chunks:")
for d in results:
    src = d["metadata"].get("source", "?")
    chunk = d["metadata"].get("chunk_index", "?")
    rrf = d["metadata"].get("rrf_score", 0)
    print(f"  [{rrf:.4f}] {src}:chunk_{chunk}")

if results:
    print("\n✅ RAG pipeline is working correctly!")
else:
    print("\n❌ No results returned — retrieval still failing.")
