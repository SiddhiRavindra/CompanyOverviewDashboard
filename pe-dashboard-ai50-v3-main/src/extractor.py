from __future__ import annotations

import os
import sys
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent
from typing import Iterable, List, Optional, Sequence, Dict, Any  # Added Any here

import instructor
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

if __package__ in (None, "", "__main__"):
    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.append(str(ROOT))
    from models import (  # type: ignore
        Company,
        Event,
        Leadership,
        Payload,
        Product,
        Provenance,
        Snapshot,
        Visibility,
    )
else:
    from .models import (
        Company,
        Event,
        Leadership,
        Payload,
        Product,
        Provenance,
        Snapshot,
        Visibility,
    )

load_dotenv()

RAW_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
STRUCTURED_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "structured"
PROVENANCE_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "provenance"
DEFAULT_MODEL = "gpt-4o-mini"


@dataclass
class SourceDocument:
    company_id: str
    run_id: Optional[str]
    path: Path
    content: str

    @property
    def provenance_url(self) -> str:
        relative = self.path.relative_to(RAW_DATA_DIR)
        return f"https://raw.local/{relative.as_posix()}"

    @property
    def crawled_at(self) -> str:
        ts = datetime.fromtimestamp(self.path.stat().st_mtime, tz=timezone.utc)
        return ts.isoformat()

    @property
    def snippet(self) -> str:
        excerpt = self.content.replace("\r", " ").replace("\n", " ")
        return excerpt[:280]


class StructuredBundle(BaseModel):
    """Clean structured data without provenance references"""
    company_record: Company
    events: List[Event] = []
    snapshots: List[Snapshot] = []
    products: List[Product] = []
    leadership: List[Leadership] = []
    visibility: List[Visibility] = []


class CitedItem(BaseModel):
    """Base class for items with source citations"""
    # source_docs: List[int] = []  # Document indices this item came from
    # citation_reason: Optional[str] = None  # Why these sources were chosen
    source_docs: List[int]  # Document indices this item came from
    citation_reason: str  # Why these sources were chosen


class CitedCompany(Company, CitedItem):
    """Company with source citations"""
    pass


class CitedEvent(Event, CitedItem):
    """Event with source citations"""
    pass


class CitedSnapshot(Snapshot, CitedItem):
    """Snapshot with source citations"""
    pass


class CitedProduct(Product, CitedItem):
    """Product with source citations"""
    pass


class CitedLeadership(Leadership, CitedItem):
    """Leadership with source citations"""
    pass


class CitedVisibility(Visibility, CitedItem):
    """Visibility with source citations"""
    pass


class StructuredBundleWithCitations(BaseModel):
    """Structured data WITH citation information from LLM"""
    company_record: CitedCompany
    events: List[CitedEvent] = []
    snapshots: List[CitedSnapshot] = []
    products: List[CitedProduct] = []
    leadership: List[CitedLeadership] = []
    visibility: List[CitedVisibility] = []


class ProvenanceMapping(BaseModel):
    """Maps each item to its source documents with explanations"""
    company_id: str
    extraction_timestamp: str
    document_sources: Dict[int, Dict[str, str]]  # doc_index -> {url, path, crawled_at}
    
    company_record: Dict[str, Any] = {}  # Changed from any to Any
    events: List[Dict[str, Any]] = []    # Changed from any to Any
    snapshots: List[Dict[str, Any]] = [] # Changed from any to Any
    products: List[Dict[str, Any]] = []  # Changed from any to Any
    leadership: List[Dict[str, Any]] = []  # Changed from any to Any
    visibility: List[Dict[str, Any]] = []  # Changed from any to Any


class StructuredExtractor:
    def __init__(self, client: Optional[OpenAI], model: str = DEFAULT_MODEL):
        if client is None:
            raise ValueError("An OpenAI client (patched by instructor) must be provided.")
        self.client = instructor.patch(client)
        self.model = model

    @classmethod
    def from_env(cls, model: str = DEFAULT_MODEL) -> StructuredExtractor:
        api_key = os.getenv("OPENAI_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_KEY not set; cannot call structured extractor.")
        client = OpenAI(api_key=api_key)
        return cls(client=client, model=model)

    def extract_company(self, company_id: str) -> StructuredBundle:
        """Extract structured data with provenance tracking"""
        docs = list(load_company_documents(company_id) or [])
        if not docs:
            raise FileNotFoundError(f"No raw documents found for company '{company_id}'.")

        # Get extraction with citations
        messages = build_messages_with_citation_request(company_id, docs)
        response: StructuredBundleWithCitations = self.client.chat.completions.create(
            model=self.model,
            response_model=StructuredBundleWithCitations,
            temperature=0.1,
            messages=messages,
        )
        # Debug: Check if citations are present
        print(f"[DEBUG] Company citations: source_docs={response.company_record.source_docs}, reason={response.company_record.citation_reason}")
        if response.products:
            print(f"[DEBUG] First product citations: source_docs={response.products[0].source_docs}, reason={response.products[0].citation_reason}")
    
        
        # Create clean bundle without citations
        clean_bundle = self._create_clean_bundle(response)
        
        # Create provenance mapping
        provenance_map = self._create_provenance_mapping(company_id, response, docs)
        
        # Save both
        save_structured_bundle(company_id, clean_bundle)
        save_provenance_mapping(company_id, provenance_map)
        
        print(f"[structured] Extracted {company_id} with provenance from {len(docs)} documents")
        
        return clean_bundle
    
    def _create_clean_bundle(self, cited_bundle: StructuredBundleWithCitations) -> StructuredBundle:
        """Strip citation info to create clean bundle"""
        return StructuredBundle(
            company_record=Company(**cited_bundle.company_record.dict(exclude={'source_docs', 'citation_reason'})),
            events=[Event(**e.dict(exclude={'source_docs', 'citation_reason'})) for e in cited_bundle.events],
            snapshots=[Snapshot(**s.dict(exclude={'source_docs', 'citation_reason'})) for s in cited_bundle.snapshots],
            products=[Product(**p.dict(exclude={'source_docs', 'citation_reason'})) for p in cited_bundle.products],
            leadership=[Leadership(**l.dict(exclude={'source_docs', 'citation_reason'})) for l in cited_bundle.leadership],
            visibility=[Visibility(**v.dict(exclude={'source_docs', 'citation_reason'})) for v in cited_bundle.visibility],
        )
    
    def _create_provenance_mapping(self, company_id: str, cited_bundle: StructuredBundleWithCitations, 
                                   docs: List[SourceDocument]) -> ProvenanceMapping:
        """Create detailed provenance mapping"""
        # Create document source reference
        doc_sources = {}
        for idx, doc in enumerate(docs, start=1):
            doc_sources[idx] = {
                "url": doc.provenance_url,
                "path": str(doc.path.relative_to(RAW_DATA_DIR)),
                "crawled_at": doc.crawled_at,
                "filename": doc.path.name
            }
        
        # Extract citation info
        mapping = ProvenanceMapping(
            company_id=company_id,
            extraction_timestamp=datetime.now(timezone.utc).isoformat(),
            document_sources=doc_sources,
            company_record={
                "source_docs": cited_bundle.company_record.source_docs,
                "reason": cited_bundle.company_record.citation_reason
            }
        )
        
        # Map events
        for event in cited_bundle.events:
            mapping.events.append({
                "event_id": event.event_id,
                "source_docs": event.source_docs,
                "reason": event.citation_reason
            })
        
        # Map other collections similarly
        for snapshot in cited_bundle.snapshots:
            mapping.snapshots.append({
                "as_of": snapshot.as_of.isoformat() if snapshot.as_of else None,
                "source_docs": snapshot.source_docs,
                "reason": snapshot.citation_reason
            })
        
        for product in cited_bundle.products:
            mapping.products.append({
                "product_id": product.product_id,
                "source_docs": product.source_docs,
                "reason": product.citation_reason
            })
        
        for leader in cited_bundle.leadership:
            mapping.leadership.append({
                "person_id": leader.person_id,
                "name": leader.name,
                "source_docs": leader.source_docs,
                "reason": leader.citation_reason
            })
        
        for vis in cited_bundle.visibility:
            mapping.visibility.append({
                "as_of": vis.as_of.isoformat() if vis.as_of else None,
                "source_docs": vis.source_docs,
                "reason": vis.citation_reason
            })
        
        return mapping


def build_messages_with_citation_request(company_id: str, docs: Sequence[SourceDocument]) -> List[dict]:
    """Build messages that request citation tracking"""
    system_prompt = dedent(
        """
        You are a senior PE analyst tasked with producing normalized structured data for a Forbes AI 50 company.
        
        CRITICAL REQUIREMENTS:
        1. Use ONLY the provided documents - never invent information
        2. For EACH piece of information you extract, you MUST include:
           - source_docs: list of document numbers [1, 2, 3, etc.]
           - citation_reason: explanation of what you found and where
        3. EVERY item (company_record, events, products, etc.) MUST have source_docs and citation_reason
        4. If information is missing, use "Not disclosed" for the field value
        5. Never fabricate valuations, ARR, revenue figures, or customer names
        
        EXAMPLE OUTPUT STRUCTURE:
        {
            "company_record": {
                "company_id": "example",
                "legal_name": "Example Corp",
                "source_docs": [1, 2],
                "citation_reason": "Legal name from homepage (Doc 1), confirmed in About page (Doc 2)"
            },
            "products": [
                {
                    "product_id": "1",
                    "name": "Product A",
                    "source_docs": [3],
                    "citation_reason": "Product details from products page (Doc 3)"
                }
            ]
        }
        """
    ).strip()

    # Build document overview with clear markers
    overview_lines = [
        f"Company ID: {company_id}",
        "=" * 50,
        "DOCUMENTS PROVIDED:",
        "=" * 50,
    ]

    for idx, doc in enumerate(docs, start=1):
        overview_lines.append(f"\n{'='*30} DOCUMENT {idx} {'='*30}")
        overview_lines.append(f"Path: {doc.path.name}")
        if doc.run_id:
            overview_lines.append(f"Run ID: {doc.run_id}")
        overview_lines.append(f"Source URL: {doc.provenance_url}")
        overview_lines.append(f"Crawled at: {doc.crawled_at}")
        overview_lines.append(f"\n--- CONTENT START (Document {idx}) ---")
        overview_lines.append(doc.content.strip())
        overview_lines.append(f"--- CONTENT END (Document {idx}) ---\n")

    user_prompt = "\n".join(overview_lines)
    
    print(f"[structured: build_messages] built prompt with {len(docs)} documents and {len(user_prompt)} characters for company '{company_id}'.")
    if len(user_prompt) > 200000:
        print(f"[structured: build_messages] WARNING: prompt truncated to 200,000 characters.")
        user_prompt = user_prompt[:200000]

    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": dedent(
                f"""
                Extract structured data from the documents above for company: {company_id}
                
                REMEMBER TO INCLUDE FOR EACH ITEM:
                1. source_docs: list of document indices where you found this information
                2. citation_reason: brief explanation of what you found and where
                
                Example format:
                - For company_record: include source_docs: [1, 2] and citation_reason: "HQ from About page (1), founded year from blog (2)"
                - For each event: include source_docs and citation_reason
                - For each product: include source_docs and citation_reason
                
                Extract:
                - company_record (CitedCompany with source_docs and citation_reason)
                - events (List[CitedEvent] each with source_docs and citation_reason)
                - snapshots (List[CitedSnapshot] each with source_docs and citation_reason)
                - products (List[CitedProduct] each with source_docs and citation_reason)
                - leadership (List[CitedLeadership] each with source_docs and citation_reason)
                - visibility (List[CitedVisibility] each with source_docs and citation_reason)

                {user_prompt}
                """
            ).strip(),
        },
    ]


def load_company_documents(company_id: str) -> Iterable[SourceDocument]:
    """Load all documents for a company"""
    company_dir = RAW_DATA_DIR / company_id
    if not company_dir.exists() or not company_dir.is_dir():
        print(f"[structured: load_company_documents] no raw directory found for company '{company_id}'.")
        return

    for path in sorted(company_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".txt", ".md", ".html", ".htm"}:
            continue
        if path.stat().st_size == 0:
            continue
        try:
            run_id = path.relative_to(company_dir).parts[0]
        except Exception:
            run_id = None
        content = load_text_from_file(path)
        if not content or not content.strip():
            continue
        yield SourceDocument(company_id=company_id, run_id=run_id, path=path, content=content)


def load_text_from_file(path: Path) -> str:
    """Load text content from file"""
    ext = path.suffix.lower()
    raw_bytes = path.read_bytes()
    text = raw_bytes.decode("utf-8", errors="ignore")
    if ext not in {".md", ".txt"}:
        return ""
    return text


def save_structured_bundle(company_id: str, bundle: StructuredBundle) -> Path:
    """Save clean structured data (Lab 5)"""
    STRUCTURED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_path = STRUCTURED_DATA_DIR / f"{company_id}.json"
    output_path.write_text(bundle.model_dump_json(indent=2, by_alias=True))
    print(f"[structured] Saved structured bundle to {output_path.relative_to(STRUCTURED_DATA_DIR.parent)}")
    return output_path


def save_provenance_mapping(company_id: str, mapping: ProvenanceMapping) -> Path:
    """Save provenance mapping for use in payload assembly"""
    PROVENANCE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_path = PROVENANCE_DATA_DIR / f"{company_id}_provenance.json"
    output_path.write_text(mapping.model_dump_json(indent=2))
    print(f"[structured] Saved provenance mapping to {output_path.relative_to(PROVENANCE_DATA_DIR.parent)}")
    return output_path


def run_all() -> None:
    """Extract structured data for all companies"""
    extractor = StructuredExtractor.from_env()
    if not RAW_DATA_DIR.exists():
        print("[structured] data/raw directory not found.")
        return

    company_ids = sorted({p.name for p in RAW_DATA_DIR.iterdir() if p.is_dir()})
    if not company_ids:
        print("[structured] no companies found under data/raw.")
        return

    successful = []
    failed = []
    
    for company_id in company_ids:
        try:
            print(f"\n[structured] Processing {company_id}...")
            bundle = extractor.extract_company(company_id)
            successful.append(company_id)
        except Exception as e:
            print(f"[structured] ERROR processing {company_id}: {e}")
            failed.append(company_id)
    
    print(f"\n[structured] Complete! Successful: {len(successful)}, Failed: {len(failed)}")
    if failed:
        print(f"[structured] Failed companies: {', '.join(failed)}")


if __name__ == "__main__":
    run_all()