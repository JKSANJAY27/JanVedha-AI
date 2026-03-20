"""
Token-based Document Chunker

Splits large documents into small semantic chunks based on EXACT token counts,
using tiktoken. Includes chunk overlap to prevent cutting off context at boundaries.
"""
import tiktoken
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

def chunk_text(
    text: str, 
    source_metadata: Dict[str, Any], 
    chunk_size: int = 800, 
    overlap: int = 100
) -> List[Dict[str, Any]]:
    """
    Splits text into chunks of `chunk_size` tokens with `overlap` tokens using the OpenAI cl100k_base tokenizer.
    
    Returns a list of dictionaries, each containing:
      - 'text': The decoded string of the chunk
      - 'metadata': A copy of source_metadata combined with chunk_index
    """
    encoder = tiktoken.get_encoding("cl100k_base")
    tokens = encoder.encode(text)
    
    chunks = []
    start = 0
    total_tokens = len(tokens)
    chunk_index = 0
    
    if total_tokens == 0:
        return []
        
    while start < total_tokens:
        # Calculate end index for this chunk
        end = min(start + chunk_size, total_tokens)
        
        # Extract tokens and decode back to text
        chunk_tokens = tokens[start:end]
        chunk_text = encoder.decode(chunk_tokens)
        
        # Combine metadata
        meta = source_metadata.copy()
        meta["chunk_index"] = chunk_index
        
        chunks.append({
            "text": chunk_text,
            "metadata": meta
        })
        
        chunk_index += 1
        
        # Move start pointer forward, stepping back by 'overlap' tokens
        # Unless we've already reached the end
        if end >= total_tokens:
            break
            
        start += (chunk_size - overlap)
        
    logger.debug(f"Chunked document {source_metadata.get('source', 'unknown')} into {len(chunks)} chunks.")
    return chunks
