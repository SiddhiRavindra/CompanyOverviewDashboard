"""
FastAPI Application - PE Dashboard API
Lab 4 RAG Search + Lab 7 Dashboard Generation
"""

import os
import sys
from dotenv import load_dotenv
from pathlib import Path
from rag_pipeline import VectorStore 
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import json
from openai import OpenAI
from structured_pipeline import load_payload
from dashboard_generator import generate_dashboard, generate_dashboard_from_rag

env_path=Path(__file__).parent.parent/'src'/'.env'
load_dotenv(env_path,override=True)
print("This is the api key",os.getenv('OPENAI_KEY'))

ENVIRONMENT = os.getenv("ENVIRONMENT", 'production')  # Changed to 'local' for testing



# Original imports (optional - only if these files exist)
# try:
# from utils.gcs_util import gcs_util
# from src.utils.gcs_util import gcs_util

# except ImportError:
    # These are optional - set to None if not available
    # gcs_utils = None
    # load_payload = None
    # generate_dashboard = None
    # generate_dashboard_from_rag = None

app = FastAPI(
    title="PE Dashboard API - Complete",
    description="Lab 4 RAG Search + Lab 7 Dashboard Generation",
    version="0.2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if ENVIRONMENT == "local":
    DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# Global instances
vector_store = None
openai_client = None

# System prompt (inline)
DASHBOARD_SYSTEM_PROMPT = """You generate an investor-facing diligence dashboard for a private AI startup.

Use ONLY data in the provided payload. If something is unknown or not disclosed, literally say "Not disclosed."

If a claim is marketing, attribute it: "The company states ..."

Never include personal emails or phone numbers.

Always include the final section "## Disclosure Gaps".

Required section order:

## Company Overview
## Business Model and GTM
## Funding & Investor Profile
## Growth Momentum
## Visibility & Market Sentiment
## Risks and Challenges
## Outlook
## Disclosure Gaps"""


# ========== UTILITY FUNCTIONS ==========

def clean_env_value(value):
    if value is None:
        return None
    value = value.strip()
    if (value.startswith("'") and value.endswith("'")) or \
       (value.startswith('"') and value.endswith('"')):
        value = value[1:-1]
    return value


def get_vector_store():
    """Get or create vector store instance."""
    global vector_store
    if vector_store is None:
        api_key = clean_env_value(os.getenv('CHROMA_API_KEY'))
        tenant = clean_env_value(os.getenv('CHROMA_TENANT'))
        database = clean_env_value(os.getenv('CHROMA_DB'))
        openai_api_key = clean_env_value(os.getenv('OPENAI_KEY'))
        
        if not all([api_key, tenant, database, openai_api_key]):
            raise RuntimeError("Missing credentials in .env")
        
        vector_store = VectorStore(
            api_key=api_key,
            tenant=tenant,
            database=database,
            openai_api_key=openai_api_key
        )
    return vector_store


def get_openai_client():
    """Get OpenAI client."""
    global openai_client
    if openai_client is None:
        api_key = os.getenv('OPENAI_KEY')
        openai_client = OpenAI(api_key=api_key)
    return openai_client


def retrieve_context_for_dashboard(company_name: str, top_k: int = 15) -> List[Dict]:
    """Retrieve context for dashboard."""
    vs = get_vector_store()
    
    queries = [
        f"{company_name} company overview mission",
        "funding investors series round capital valuation",
        "business model revenue pricing customers GTM",
        "founders CEO leadership team executives",
        "hiring jobs positions growth expansion",
        "product platform features technology AI",
        "customers clients partnerships enterprise",
        "awards press recognition forbes AI 50"
    ]
    
    all_results = []
    seen_chunks = set()
    
    for query in queries:
        try:
            results = vs.search(
                company_name=company_name,
                query=query,
                top_k=max(2, top_k // len(queries))
            )
            
            for result in results:
                chunk_id = f"{result['source_type']}_{result['chunk_index']}"
                if chunk_id not in seen_chunks:
                    all_results.append(result)
                    seen_chunks.add(chunk_id)
        except:
            continue
    
    all_results.sort(key=lambda x: x.get('distance', 999))
    return all_results[:top_k]


def format_payload(company_name: str, chunks: List[Dict]) -> str:
    """Format chunks as payload for GPT."""
    if not chunks:
        return f"No data for {company_name}. Use 'Not disclosed.' for all sections."
    
    payload = f"# Company Data: {company_name}\n\n**Retrieved Chunks**: {len(chunks)}\n\n"
    
    # Group by source
    by_source = {}
    for chunk in chunks:
        source = chunk['source_type']
        if source not in by_source:
            by_source[source] = []
        by_source[source].append(chunk)
    
    # Format
    for source_type, source_chunks in sorted(by_source.items()):
        payload += f"## {source_type.upper()} PAGE\n\n"
        
        for chunk in sorted(source_chunks, key=lambda x: x.get('chunk_index', 0)):
            payload += f"**Chunk {chunk.get('chunk_index', 0) + 1}:**\n"
            payload += f"{chunk['text']}\n\n"
        
        payload += "---\n\n"
    
    return payload


# ========== PYDANTIC MODELS ==========

class SearchRequest(BaseModel):
    company_name: str
    query: str
    top_k: int = Field(5, ge=1, le=20)
    filter_source: Optional[str] = None


class SearchResult(BaseModel):
    text: str
    source_url: str
    source_type: str
    chunk_index: int
    distance: Optional[float] = None
    chunk_size: Optional[int] = None


class SearchResponse(BaseModel):
    company_name: str
    query: str
    results: List[SearchResult]
    total_results: int


class DashboardRequest(BaseModel):
    company_name: str
    top_k: int = Field(15, ge=5, le=30)
    max_tokens: int = Field(4000, ge=1000, le=8000)
    temperature: float = Field(0.3, ge=0.0, le=1.0)
    model: str = Field("gpt-4o")


class DashboardResponse(BaseModel):
    company_name: str
    dashboard: str
    metadata: Dict
    context_sources: List[str]


# ========== ENDPOINTS ==========

@app.get("/")
def root():
    return {
        "title": "PE Dashboard API",
        "version": "0.2.0",
        "endpoints": {
            "health": "GET /health",
            "companies": "GET /companies",
            "rag_search": "GET/POST /rag/search",
            "dashboard_rag": "GET/POST /dashboard/rag"
        },
        "test_urls": {
            "companies": "http://localhost:8000/companies",
            "search": "http://localhost:8000/rag/search?company_name=abridge&query=funding",
            "dashboard": "http://localhost:8000/dashboard/rag/abridge"
        }
    }


@app.get("/health")
def health():
    try:
        vs = get_vector_store()
        companies = vs.get_company_list()
        return {
            "status": "ok",
            "vector_db_connected": True,
            "companies_indexed": len(companies)
        }
    except:
        return {"status": "ok", "vector_db_connected": False}


@app.get("/companies")
def list_companies():
    """List all companies."""
    companies = []
    
    # Try to get from vector DB
    try:
        vs = get_vector_store()
        companies = vs.get_company_list()
        return sorted(companies)
    except Exception as e:
        print(f"Error getting companies: {e}")
        return []


# ========== LAB 4: RAG SEARCH ==========

@app.post("/rag/search", response_model=SearchResponse)
async def search_post(request: SearchRequest):
    """Lab 4: RAG Search (POST)"""
    try:
        vs = get_vector_store()
        
        filter_source = request.filter_source
        if filter_source in ["string", "null", ""]:
            filter_source = None
        
        results = vs.search(
            company_name=request.company_name,
            query=request.query,
            top_k=request.top_k,
            filter_by_source_type=filter_source
        )
        
        return SearchResponse(
            company_name=request.company_name,
            query=request.query,
            results=[SearchResult(**r) for r in results],
            total_results=len(results)
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/rag/search", response_model=SearchResponse)
async def search_get(
    company_name: str = Query(...),
    query: str = Query(...),
    top_k: int = Query(5, ge=1, le=20),
    filter_source: Optional[str] = Query(None)
):
    """Lab 4: RAG Search (GET)"""
    request = SearchRequest(
        company_name=company_name,
        query=query,
        top_k=top_k,
        filter_source=filter_source
    )
    return await search_post(request)


# ========== LAB 7: DASHBOARD GENERATION ==========

@app.post("/dashboard/rag", response_model=DashboardResponse)
async def dashboard_post(request: DashboardRequest):
    """Lab 7: Generate Dashboard (POST)"""
    try:
        print(f"\n🚀 Generating dashboard: {request.company_name}")
        
        # Retrieve context
        chunks = retrieve_context_for_dashboard(request.company_name, request.top_k)
        
        if not chunks:
            return DashboardResponse(
                company_name=request.company_name,
                dashboard=_empty_dashboard(request.company_name),
                metadata={"status": "no_context", "chunks_retrieved": 0},
                context_sources=[]
            )
        
        print(f"✓ Retrieved {len(chunks)} chunks")
        
        # Format payload
        payload = format_payload(request.company_name, chunks)
        
        # Create prompt
        user_prompt = f"""Generate a PE dashboard for {request.company_name}.

Use ONLY the data below. Use "Not disclosed." for missing info.

{payload}

Generate all 8 sections.
"""
        
        # Call GPT
        client = get_openai_client()
        
        response = client.chat.completions.create(
            model=request.model,
            messages=[
                {"role": "system", "content": DASHBOARD_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=request.max_tokens,
            temperature=request.temperature
        )
        
        dashboard = response.choices[0].message.content
        
        # Verify
        sections = sum(1 for s in [
            "## Company Overview", "## Business Model and GTM",
            "## Funding & Investor Profile", "## Growth Momentum",
            "## Visibility & Market Sentiment", "## Risks and Challenges",
            "## Outlook", "## Disclosure Gaps"
        ] if s in dashboard)
        
        not_disclosed = dashboard.count("Not disclosed")
        
        print(f"✓ Generated | Sections: {sections}/8 | 'Not disclosed': {not_disclosed}x")
        
        return DashboardResponse(
            company_name=request.company_name,
            dashboard=dashboard,
            metadata={
                'chunks_retrieved': len(chunks),
                'sources_used': list(set(c['source_type'] for c in chunks)),
                'model': request.model,
                'tokens_used': {'total': response.usage.total_tokens},
                'not_disclosed_count': not_disclosed,
                'sections_present': sections,
                'status': 'success'
            },
            context_sources=list(set(c['source_type'] for c in chunks))
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dashboard/rag/{company_name}")
async def dashboard_get(
    company_name: str,
    top_k: int = Query(15, ge=5, le=30),
    max_tokens: int = Query(4000, ge=1000, le=8000),
    temperature: float = Query(0.3, ge=0.0, le=1.0),
    model: str = Query("gpt-4o")
):
    """Lab 7: Dashboard (GET)"""
    request = DashboardRequest(
        company_name=company_name,
        top_k=top_k,
        max_tokens=max_tokens,
        temperature=temperature,
        model=model
    )
    return await dashboard_post(request)


def _empty_dashboard(company_name: str) -> str:
    """Empty dashboard."""
    return f"""# {company_name} - PE Intelligence Dashboard

## Company Overview
Not disclosed.

## Business Model and GTM
Not disclosed.

## Funding & Investor Profile
Not disclosed.

## Growth Momentum
Not disclosed.

## Visibility & Market Sentiment
Not disclosed.

## Risks and Challenges
Not disclosed.

## Outlook
Not disclosed.

## Disclosure Gaps
- All company information
- No data available in vector database
"""

@app.get("/payloads")
def list_payloads():
    """List all available company IDs that have payloads."""
    if ENVIRONMENT == "local":
        # Old code (local file system)
        payload_dir = DATA_DIR / "payloads"
        if not payload_dir.exists():
            return []
        payloads = [f.stem for f in payload_dir.glob("*.json")]
        return sorted(payloads)
    else:
        # New GCS code
        # List all file stems in the 'data/payloads/' folder in GCS
        # payloads = gcs_util.list_gcs_files("payloads")
        return payloads # The utility function already sorts them

@app.post("/dashboard/structured")
def dashboard_structured(company_id: str = "00000000-0000-0000-0000-000000000000"):
    """Generate dashboard from structured payload using LLM."""
    
    # This function call doesn't change!
    # We successfully updated load_payload (in the other file) to use GCS,
    # so the API layer doesn't need to know.
    print("company_id" + company_id)
    payload = load_payload(company_id)
    print(payload)
    if not payload:
        error_msg = "Payload not found in GCS" if ENVIRONMENT != "local" else "Payload not found"
        raise HTTPException(status_code=404, detail=error_msg)

    try:
        markdown = generate_dashboard(payload)
        return {
            "markdown": markdown,
            "company_id": company_id
        }
    except Exception as e:
        print(f"Error in /dashboard/structured: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate dashboard: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
