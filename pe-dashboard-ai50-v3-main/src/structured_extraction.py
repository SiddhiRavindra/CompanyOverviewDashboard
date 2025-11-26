from __future__ import annotations

import os
import sys
import traceback
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, Iterable, List, Optional, Sequence

import instructor
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, field_validator, model_validator

if __package__ in (None, "", "__main__"):
    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.append(str(ROOT))
    from models import (  # type: ignore
        Company,
        Event,
        Leadership,
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
        Product,
        Provenance,
        Snapshot,
        Visibility,
    )

load_dotenv()

RAW_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
STRUCTURED_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "structured"
DEFAULT_MODEL = "gpt-4o-mini"

RUN_DIR_DATE_FORMATS = (
    "%Y%m%d",
    "%Y%m%d%H%M%S",
    "%Y-%m-%d_%H%M%S",
    "%Y-%m-%d-%H%M%S",
    "%Y-%m-%dT%H-%M-%SZ",
    "%Y-%m-%dT%H-%M-%S",
)


@dataclass
class SourceDocument:
    company_id: str
    run_id: Optional[str]
    path: Path
    content: str

    @property
    def provenance_url(self) -> str:
        relative = self.path.relative_to(RAW_DATA_DIR)
        #todo: update with real url of the path
        return f"https://local/data/raw/{relative.as_posix()}"

    @property
    def crawled_at(self) -> str:
        ts = datetime.fromtimestamp(self.path.stat().st_mtime, tz=timezone.utc)
        return ts.isoformat()

    @property
    def snippet(self) -> str:
        excerpt = self.content.replace("\r", " ").replace("\n", " ")
        return excerpt[:280]


class StructuredBundle(BaseModel):
    """Structured extraction bundle - Lab 5 output"""
    company_record: Company
    events: List[Event] = []
    snapshots: List[Snapshot] = []
    products: List[Product] = []
    leadership: List[Leadership] = []
    visibility: List[Visibility] = []
    
    @model_validator(mode='before')
    @classmethod
    def fix_null_lists_and_dates(cls, data: Any) -> Any:
        """Convert null values to empty lists and parse date strings"""
        if isinstance(data, dict):
            # Fix company_record
            if 'company_record' in data and isinstance(data['company_record'], dict):
                company = data['company_record']
                # Fix list fields
                for field in ['categories', 'related_companies']:
                    if field in company and company[field] is None:
                        company[field] = []
                # Fix date fields
                if 'as_of' in company and isinstance(company['as_of'], str):
                    try:
                        company['as_of'] = date.fromisoformat(company['as_of'])
                    except (ValueError, AttributeError):
                        company['as_of'] = None
                if 'last_round_date' in company and isinstance(company['last_round_date'], str):
                    try:
                        company['last_round_date'] = date.fromisoformat(company['last_round_date'])
                    except (ValueError, AttributeError):
                        company['last_round_date'] = None
            
            # Fix snapshots
            if 'snapshots' in data and isinstance(data['snapshots'], list):
                for snapshot in data['snapshots']:
                    if isinstance(snapshot, dict):
                        # Fix list fields
                        for field in ['hiring_focus', 'pricing_tiers', 'active_products', 'geo_presence']:
                            if field in snapshot and snapshot[field] is None:
                                snapshot[field] = []
                        # Fix date fields
                        if 'as_of' in snapshot and isinstance(snapshot['as_of'], str):
                            try:
                                snapshot['as_of'] = date.fromisoformat(snapshot['as_of'])
                            except (ValueError, AttributeError):
                                pass  # Required field, keep as is
            
            # Fix products
            if 'products' in data and isinstance(data['products'], list):
                for product in data['products']:
                    if isinstance(product, dict):
                        # Fix list fields
                        for field in ['pricing_tiers_public', 'integration_partners', 'reference_customers']:
                            if field in product and product[field] is None:
                                product[field] = []
                        # Fix date fields
                        if 'ga_date' in product and isinstance(product['ga_date'], str):
                            try:
                                product['ga_date'] = date.fromisoformat(product['ga_date'])
                            except (ValueError, AttributeError):
                                product['ga_date'] = None
            
            # Fix events
            if 'events' in data and isinstance(data['events'], list):
                for event in data['events']:
                    if isinstance(event, dict):
                        # Fix list fields
                        for field in ['investors', 'actors', 'tags']:
                            if field in event and event[field] is None:
                                event[field] = []
                        # Fix date fields
                        if 'occurred_on' in event and isinstance(event['occurred_on'], str):
                            try:
                                event['occurred_on'] = date.fromisoformat(event['occurred_on'])
                            except (ValueError, AttributeError):
                                pass  # Required field, keep as is
            
            # Fix leadership
            if 'leadership' in data and isinstance(data['leadership'], list):
                for leader in data['leadership']:
                    if isinstance(leader, dict):
                        # Fix date fields
                        for field in ['start_date', 'end_date']:
                            if field in leader and isinstance(leader[field], str):
                                try:
                                    leader[field] = date.fromisoformat(leader[field])
                                except (ValueError, AttributeError):
                                    leader[field] = None
            
            # Fix visibility - filter out any non-dict items (from malformed JSON)
            if 'visibility' in data and isinstance(data['visibility'], list):
                data['visibility'] = [vis for vis in data['visibility'] if isinstance(vis, dict)]
                for vis in data['visibility']:
                    # Fix date fields
                    if 'as_of' in vis and isinstance(vis['as_of'], str):
                        try:
                            vis['as_of'] = date.fromisoformat(vis['as_of'])
                        except (ValueError, AttributeError):
                            pass  # Required field, keep as is
            
            # Clean up any other arrays that might have string contamination
            for array_field in ['events', 'snapshots', 'products', 'leadership']:
                if array_field in data and isinstance(data[array_field], list):
                    data[array_field] = [item for item in data[array_field] if isinstance(item, dict)]
        return data


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
        # base_url = os.getenv("OPENAI_BASE_URL")
        # client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
        client = OpenAI(api_key=api_key)
        return cls(client=client, model=model)

    def extract_company(self, company_id: str) -> StructuredBundle:
        """Lab 5: Extract structured data and return StructuredBundle (raw Pydantic models)"""
        docs = list(load_company_documents(company_id) or [])
        if not docs:
            raise FileNotFoundError(f"No raw documents found for company '{company_id}'.")

        messages = build_messages(company_id, docs)
        try:
            response: StructuredBundle = self.client.chat.completions.create(
                model=self.model,
                response_model=StructuredBundle,
                temperature=0.1,
                messages=messages,
                max_retries=3,
            )
        except Exception as e:
            print(f"[structured: extract_company] Error extracting for '{company_id}': {e}")
            raise

        return response


def _parse_run_directory_name(name: str) -> Optional[datetime]:
    candidate_values = {name.strip()}
    if "_" in name:
        candidate_values.add(name.split("_", 1)[0])
    if name.endswith("Z"):
        candidate_values.add(name[:-1])

    for candidate in candidate_values:
        # Normalize ISO-like with hyphenated time, e.g., 2025-11-07T06-37-33Z
        # Strip trailing Z before normalization
        normalized = candidate[:-1] if candidate.endswith("Z") else candidate
        if "T" in normalized and "-" in normalized.split("T", 1)[1]:
            date_part, time_part = normalized.split("T", 1)
            time_part_colon = time_part.replace("-", ":")
            iso_like = f"{date_part}T{time_part_colon}"
            try:
                return datetime.fromisoformat(iso_like)
            except ValueError:
                pass
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            pass
        for fmt in RUN_DIR_DATE_FORMATS:
            try:
                return datetime.strptime(candidate, fmt)
            except ValueError:
                continue
    return None


def _resolve_company_run_directory(company_dir: Path) -> Optional[Path]:
    if not company_dir.exists() or not company_dir.is_dir():
        return None

    initial_dir: Optional[Path] = None
    dated_dirs: List[tuple[datetime, Path]] = []

    for entry in company_dir.iterdir():
        if not entry.is_dir():
            continue
        if entry.name == "initial":
            initial_dir = entry
            continue

        parsed = _parse_run_directory_name(entry.name)
        if parsed is not None:
            dated_dirs.append((parsed, entry))

    if dated_dirs:
        dated_dirs.sort(key=lambda item: item[0], reverse=True)
        return dated_dirs[0][1]

    if initial_dir is not None and initial_dir.exists():
        return initial_dir

    return None


def load_company_documents(company_id: str) -> Iterable[SourceDocument]:
    company_dir = RAW_DATA_DIR / company_id
    if not company_dir.exists() or not company_dir.is_dir():
        print(f"[structured: load_company_documents] no raw directory found for company '{company_id}'.")
        return

    run_dir = _resolve_company_run_directory(company_dir)
    if run_dir is None:
        print(
            f"[structured: load_company_documents] no dated or initial run found for company '{company_id}', skipping."
        )
        return

    print(
        f"[structured: load_company_documents] using run directory '{run_dir.name}' for company '{company_id}'."
    )

    for path in sorted(run_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".txt", ".md"}:
            continue
        if path.stat().st_size == 0:
            continue
        try:
            run_id = path.relative_to(company_dir).parts[0]
        except Exception:
            run_id = None
        content = load_text_from_file(path)
        if not content.strip():
            continue
        yield SourceDocument(company_id=company_id, run_id=run_id, path=path, content=content)


def load_text_from_file(path: Path) -> str:
    ext = path.suffix.lower()
    raw_bytes = path.read_bytes()
    text = raw_bytes.decode("utf-8", errors="ignore")
    if ext not in {".md", ".txt"}:
        return
    # if ext in {".html", ".htm"}:
        # soup = BeautifulSoup(text, "html.parser")
        # return soup.get_text("\n")
    return text


def build_messages(company_id: str, docs: Sequence[SourceDocument]) -> List[dict]:
    system_prompt = dedent(
        """
        You are a senior PE analyst tasked with producing normalized structured data for a Forbes AI 50 company.
        Use only the provided documents. If information is missing, inconclusive, or lacks evidence then mention "Not disclosed".
        Never invent information. Do not fabricate valuations, ARR, or customer names.
        """
    ).strip()

    overview_lines = [
        f"Company ID: {company_id}",
        "Documents:",
    ]

    for idx, doc in enumerate(docs, start=1):
        overview_lines.append(f"\n[Document {idx}: {doc.path.name}]")
        if doc.run_id:
            overview_lines.append(f"Run ID: {doc.run_id}")
        overview_lines.append(f"Source URL: {doc.provenance_url}")
        overview_lines.append(doc.content.strip())

    user_prompt = "\n".join(overview_lines)
    print (f"[structured: build_messages] built prompt with {len(docs)} documents and characters {len(user_prompt)} for company '{company_id}'.")
    if len(user_prompt) > 200000:
        print(f"[structured: build_messages] WARNING: prompt truncated to 200,000 characters.")
        user_prompt = user_prompt[:200000]

    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": dedent(
                f"""
                Extract the following structured objects as JSON that conforms to the provided Pydantic schemas:
                - company_record (Company)
                - events (List[Event])
                - snapshots (List[Snapshot])
                - products (List[Product])
                - leadership (List[Leadership])
                - visibility (List[Visibility])

                CRITICAL: For each extracted item, you MUST provide provenance that includes:
                1. source_url: The exact source URL from the document labels above (e.g., "https://local/data/raw/...")
                2. snippet: An EXTENDED text excerpt (30-50 words total) with context: include 15-25 words 
                   BEFORE and 15-25 words AFTER the relevant information. This helps show the full context.
                   Example: "...prior experience at Google. Shiv Rao, MD, CEO and Co-Founder of Abridge, 
                   leads the company's mission to transform healthcare through AI. He previously worked..."
                3. crawled_at: Use the timestamp from the document if available, otherwise use a placeholder date.

                IMPORTANT: 
                - The snippet field should contain ONLY the text excerpt from the document, nothing else.
                - Do NOT prefix the snippet with "Reason:" or any explanation. Just the raw text excerpt.
                - Use the exact source_url from the document labels above.
                - Only include provenance for items that actually contain information. If information is missing, omit the item.

                CRITICAL JSON FORMATTING RULES:
                - For list/array fields (e.g., hiring_focus, pricing_tiers, categories, investors, etc.), 
                  ALWAYS use an empty array [] if the field is missing or has no values. NEVER use null.
                - For optional single-value fields, you may use null if the information is not available.
                - Ensure all JSON is properly formatted and COMPLETE - the response must end with properly closed 
                  brackets and braces. Do not truncate or leave JSON incomplete.
                - All arrays (events, snapshots, products, leadership, visibility) must be properly closed with ].
                
                Prioritize factual accuracy. When a field is not mentioned, use [] for lists and null for optional single values.

                {user_prompt}
                """
            ).strip(),
        },
    ]


def save_structured_bundle(company_id: str, bundle: StructuredBundle) -> Path:
    """Lab 5: Save StructuredBundle (raw Pydantic models) to data/structured/"""
    STRUCTURED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_path = STRUCTURED_DATA_DIR / f"{company_id}.json"
    output_path.write_text(bundle.model_dump_json(indent=2, by_alias=True))
    return output_path


def run_all() -> None:
    extractor = StructuredExtractor.from_env()
    if not RAW_DATA_DIR.exists():
        print("[structured] data/raw directory not found.")
        return

    # todo: get the company ids from the forbes ai50 list and check if data/raw has them, if not print not found and move on
    company_ids = sorted({p.name for p in RAW_DATA_DIR.iterdir() if p.is_dir()})
    if not company_ids:
        print("[structured] no companies found under data/raw.")
        return

    for company_id in company_ids:
        try:
            bundle = extractor.extract_company(company_id)
        except FileNotFoundError as err:
            print(f"[structured] skipping '{company_id}': {err}")
            continue
        except Exception as err:
            print(f"[structured] error extracting '{company_id}': {err}")
            traceback.print_exc()
            continue

        try:
            path = save_structured_bundle(company_id, bundle)
        except Exception as err:
            print(f"[structured] error saving bundle for '{company_id}': {err}")
            traceback.print_exc()
            continue

        print(f"[structured] wrote {path.relative_to(STRUCTURED_DATA_DIR.parent)}")


if __name__ == "__main__":
    run_all()
