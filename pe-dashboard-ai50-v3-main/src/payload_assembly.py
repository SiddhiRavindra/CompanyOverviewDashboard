from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from pydantic import ValidationError

if __package__ in (None, "", "__main__"):
    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.append(str(ROOT))
    from models import Payload  # type: ignore
    from structured_extraction import StructuredBundle, load_company_documents  # type: ignore
else:
    from .models import Payload
    from .structured_extraction import StructuredBundle, load_company_documents

STRUCTURED_DIR = Path(__file__).resolve().parents[1] / "data" / "structured"
PAYLOAD_DIR = Path(__file__).resolve().parents[1] / "data" / "payloads"
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


class PayloadValidationError(RuntimeError):
    """Raised when the structured bundle fails downstream validation."""

    def __init__(self, company_id: str, issues: Iterable[str]):
        issues_list = list(issues)
        message = f"Payload for '{company_id}' failed validation:\n- " + "\n- ".join(issues_list)
        super().__init__(message)
        self.issues = issues_list


def load_structured(company_id: str) -> StructuredBundle:
    """Lab 6: Load StructuredBundle from data/structured/"""
    structured_path = STRUCTURED_DIR / f"{company_id}.json"
    if not structured_path.exists():
        raise FileNotFoundError(f"Structured bundle not found at {structured_path}")

    try:
        return StructuredBundle.model_validate_json(structured_path.read_text())
    except ValidationError as exc:
        raise PayloadValidationError(company_id, [f"Pydantic validation failed: {exc}"]) from exc


def validate_payload(payload: Payload, company_id: Optional[str] = None) -> None:
    expected_id = company_id or payload.company_record.company_id
    issues: List[str] = []

    if not payload.company_record.company_id:
        issues.append("company_record.company_id is empty.")
    elif payload.company_record.company_id != expected_id:
        issues.append(
            f"company_record.company_id '{payload.company_record.company_id}' "
            f"does not match expected id '{expected_id}'."
        )

    for collection_name, items in [
        ("events", payload.events),
        ("snapshots", payload.snapshots),
        ("products", payload.products),
        ("leadership", payload.leadership),
        ("visibility", payload.visibility),
    ]:
        for idx, item in enumerate(items):
            if hasattr(item, "company_id"):
                if not item.company_id:
                    issues.append(f"{collection_name}[{idx}] has empty company_id.")
                elif item.company_id != expected_id:
                    issues.append(
                        f"{collection_name}[{idx}] company_id '{item.company_id}' "
                        f"does not match expected id '{expected_id}'."
                    )
            if hasattr(item, "event_id") and not getattr(item, "event_id"):
                issues.append(f"{collection_name}[{idx}] event_id is empty.")
            if hasattr(item, "product_id") and not getattr(item, "product_id"):
                issues.append(f"{collection_name}[{idx}] product_id is empty.")
            if hasattr(item, "person_id") and not getattr(item, "person_id"):
                issues.append(f"{collection_name}[{idx}] person_id is empty.")

    if issues:
        raise PayloadValidationError(expected_id, issues)


def assemble_payload(company_id: str) -> Path:
    """Lab 6: Fix crawled_at timestamps and create validated Payload"""
    bundle = load_structured(company_id)
    docs = list(load_company_documents(company_id) or [])
    
    # Create URL -> doc lookup for fixing crawled_at timestamps
    url_to_doc = {doc.provenance_url: doc for doc in docs}
    
    # Fix crawled_at timestamps for all provenance entries
    def fix_provenance_timestamps(item):
        """Update crawled_at with actual file timestamp by matching source_url"""
        for prov in item.provenance:
            if prov.source_url in url_to_doc:
                prov.crawled_at = url_to_doc[prov.source_url].crawled_at
            # Clean snippet: remove "Reason:" prefixes if LLM included them
            if prov.snippet:
                snippet = prov.snippet
                if snippet.startswith("Reason:"):
                    if "\nExcerpt:" in snippet:
                        snippet = snippet.split("\nExcerpt:", 1)[1].strip()
                    elif "\n" in snippet:
                        snippet = "\n".join(snippet.split("\n")[1:]).strip()
                    else:
                        snippet = snippet.replace("Reason:", "").strip()
                if snippet.startswith("Excerpt:"):
                    snippet = snippet.replace("Excerpt:", "").strip()
                prov.snippet = snippet
    
    # Fix timestamps for all items
    fix_provenance_timestamps(bundle.company_record)
    for event in bundle.events:
        fix_provenance_timestamps(event)
    for snapshot in bundle.snapshots:
        fix_provenance_timestamps(snapshot)
    for product in bundle.products:
        fix_provenance_timestamps(product)
    for leader in bundle.leadership:
        fix_provenance_timestamps(leader)
    for vis in bundle.visibility:
        fix_provenance_timestamps(vis)
    
    # Create Payload
    payload = Payload(
        company_record=bundle.company_record,
        events=bundle.events,
        snapshots=bundle.snapshots,
        products=bundle.products,
        leadership=bundle.leadership,
        visibility=bundle.visibility,
    )

    # Light enrichment from raw/<company>/<run>/metadata.json if fields are missing
    try:
        meta = _load_company_metadata(company_id)
        if meta:
            cr = payload.company_record
            # Strings
            cr.brand_name = cr.brand_name or meta.get("brand_name") or meta.get("name")
            cr.legal_name = cr.legal_name or meta.get("legal_name") or meta.get("company") or cr.legal_name
            # Website
            if not cr.website and isinstance(meta.get("website"), str):
                try:
                    from pydantic import HttpUrl
                    cr.website = HttpUrl(meta["website"])  # type: ignore[assignment]
                except Exception:
                    pass
            # Headquarters
            if not cr.hq_city and isinstance(meta.get("hq_city"), str):
                cr.hq_city = meta.get("hq_city")
            if not cr.hq_state and isinstance(meta.get("hq_state"), str):
                cr.hq_state = meta.get("hq_state")
            if not cr.hq_country and isinstance(meta.get("hq_country"), str):
                cr.hq_country = meta.get("hq_country")
            # Founded year
            if cr.founded_year is None:
                fy = meta.get("founded_year")
                if isinstance(fy, int):
                    cr.founded_year = fy
                elif isinstance(fy, str) and fy.isdigit():
                    cr.founded_year = int(fy)
            # Categories
            if not cr.categories and isinstance(meta.get("categories"), list):
                cr.categories = [str(x) for x in meta.get("categories") if isinstance(x, (str, int))]
            # Related companies
            if not cr.related_companies and isinstance(meta.get("related_companies"), list):
                cr.related_companies = [str(x) for x in meta.get("related_companies") if isinstance(x, (str, int))]
    except Exception:
        # Enrichment is best-effort; proceed silently if metadata not available/invalid
        pass
    
    # Validate
    validate_payload(payload, company_id)
    
    # Set defaults
    if payload.notes is None:
        payload.notes = ""
    if not payload.provenance_policy:
        payload.provenance_policy = "Use only the sources you scraped. If a field is missing, write 'Not disclosed.' Do not infer valuation."

    # Save to payloads
    PAYLOAD_DIR.mkdir(parents=True, exist_ok=True)
    output_path = PAYLOAD_DIR / f"{company_id}.json"
    output_path.write_text(payload.model_dump_json(indent=2, by_alias=True))
    return output_path


def existing_payload(company_id: str) -> bool:
    return (PAYLOAD_DIR / f"{company_id}.json").exists()


def list_structured_company_ids() -> List[str]:
    if not STRUCTURED_DIR.exists():
        return []
    return sorted(file.stem for file in STRUCTURED_DIR.glob("*.json"))


def assemble_all() -> List[Path]:
    paths: List[Path] = []
    for company_id in list_structured_company_ids():
        paths.append(assemble_payload(company_id))
    return paths


def main(*company_ids: str) -> None:
    if company_ids:
        written: List[str] = []
        missing: List[str] = []
        for company_id in company_ids:
            structured_exists = (STRUCTURED_DIR / f"{company_id}.json").exists()
            if not structured_exists and existing_payload(company_id):
                written.append(str((PAYLOAD_DIR / f"{company_id}.json").relative_to(PAYLOAD_DIR.parent)))
                continue
            if not structured_exists:
                missing.append(company_id)
                continue
            path = assemble_payload(company_id)
            written.append(str(path.relative_to(PAYLOAD_DIR.parent)))
        result = {"status": "ok", "written": written}
        if missing:
            result["missing_structured"] = missing  # type: ignore[assignment]
        print(json.dumps(result))
        return

    written = [str(path.relative_to(PAYLOAD_DIR.parent)) for path in assemble_all()]
    print(json.dumps({"status": "ok", "written": written}))


if __name__ == "__main__":
    argv: Sequence[str] = tuple(sys.argv[1:])
    main(*argv)


# --- helpers (kept minimal and local) ---

def _parse_run_directory_name(name: str):
    from datetime import datetime
    candidates = {name.strip()}
    if "_" in name:
        candidates.add(name.split("_", 1)[0])
    if name.endswith("Z"):
        candidates.add(name[:-1])
    formats = ("%Y%m%d", "%Y%m%d%H%M%S", "%Y-%m-%d_%H%M%S", "%Y-%m-%d-%H%M%S")
    for c in candidates:
        try:
            return datetime.fromisoformat(c)
        except Exception:
            pass
        for fmt in formats:
            try:
                return datetime.strptime(c, fmt)
            except Exception:
                continue
    return None


def _resolve_latest_run_dir(company_id: str) -> Optional[Path]:
    company_dir = RAW_DIR / company_id
    if not company_dir.exists() or not company_dir.is_dir():
        return None
    initial_dir: Optional[Path] = None
    dated: List[tuple] = []
    for entry in company_dir.iterdir():
        if not entry.is_dir():
            continue
        if entry.name == "initial":
            initial_dir = entry
            continue
        parsed = _parse_run_directory_name(entry.name)
        if parsed:
            dated.append((parsed, entry))
    if dated:
        dated.sort(key=lambda t: t[0], reverse=True)
        return dated[0][1]
    return initial_dir


def _load_company_metadata(company_id: str) -> Optional[dict]:
    run_dir = _resolve_latest_run_dir(company_id)
    if not run_dir:
        return None
    meta_path = run_dir / "metadata.json"
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text())
    except Exception:
        return None
