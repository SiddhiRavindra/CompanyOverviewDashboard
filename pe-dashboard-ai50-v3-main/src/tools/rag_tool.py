"""
Tool: rag_search_company

Performs retrieval-augmented search for a company using ChromaDB vector database.
Returns relevant text chunks from scraped company documents.
"""

import os
from typing import List, Dict, Optional

# from src.rag_pipeline import VectorStore
# Windows:
from rag_pipeline import VectorStore


# Singleton instance to avoid re-initializing VectorStore
_vector_store: Optional[VectorStore] = None


def _get_vector_store() -> Optional[VectorStore]:
    """Get or create VectorStore instance. Returns None if unavailable."""
    global _vector_store
    
    if _vector_store is not None:
        return _vector_store
    
    # Get credentials from environment
    credentials = {
        'api_key': os.getenv('CHROMA_API_KEY'),
        'tenant': os.getenv('CHROMA_TENANT'),
        'database': os.getenv('CHROMA_DB'),
        'openai_api_key': os.getenv('OPENAI_KEY')
    }
    
    # Return None if any credential is missing
    if not all(credentials.values()):
        return None
    
    try:
        _vector_store = VectorStore(**credentials)
        return _vector_store
    except Exception:
        return None


async def rag_search_company(company_id: str, query: str, top_k: int = 5) -> List[Dict]:
    """
    Tool: rag_search_company

    Perform retrieval-augmented search for the specified company and query.
    Returns empty list if credentials missing, search fails, or no results found.

    Args:
        company_id: The canonical company identifier.
        query: Natural language query string (e.g., "layoffs", "funding").
        top_k: Number of most relevant chunks to return (default: 5).

    Returns:
        List of chunks with metadata: text, source_url, score, source_type, crawled_at.
        Returns empty list on any error (graceful degradation).
    """
    # Validate inputs
    if not (company_id and company_id.strip()) or not (query and query.strip()):
        return []
    
    # Get VectorStore instance
    vector_store = _get_vector_store()
    if vector_store is None:
        return []
    
    try:
        # Perform search
        results = vector_store.search(
            company_name=company_id.strip(),
            query=query.strip(),
            top_k=top_k
        )
        
        # Format results: convert distance to score
        return [
            {
                'text': r.get('text', ''),
                'source_url': r.get('source_url', 'unknown'),
                'score': round(1.0 / (1.0 + r.get('distance', 1.0)), 3),
                'source_type': r.get('source_type', 'unknown'),
                'crawled_at': r.get('crawled_at', ''),
            }
            for r in results
        ]
    except Exception:
        return []