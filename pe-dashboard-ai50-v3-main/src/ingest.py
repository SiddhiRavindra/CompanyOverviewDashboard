# src/ingest.py
from __future__ import annotations

import argparse
import datetime as dt
from datetime import timezone
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

# -- Repo roots ---------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"

# Ensure src/ is importable (useful when called by Airflow)
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# --- Import your Lab1 scraper ------------------------------------------------
# We only import the symbol name here; the adapter below will call it flexibly.
try:
    # Your Lab1 module should export scrape_company
    from lab1_scraper import scrape_company  # type: ignore
except Exception as e:  # pragma: no cover
    raise ImportError(
        "Could not import 'scrape_company' from src/lab1_scraper.py. "
        "Verify it exists and exports scrape_company()."
    ) from e


# --- Utilities ---------------------------------------------------------------
def _slugify(s: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in s).strip("-")


def _now_utc_iso() -> str:
    return dt.datetime.now(timezone.utc).replace(microsecond=0).isoformat() + "Z"


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def _dir_sha256_and_size(dir_path: Path) -> Tuple[str, int]:
    """
    Compute a content hash of all files under dir_path (stable by path+bytes)
    and the total content length, for lightweight provenance.
    """
    h = hashlib.sha256()
    total = 0
    for f in sorted([p for p in dir_path.rglob("*") if p.is_file()]):
        rel = f.relative_to(dir_path)
        h.update(str(rel).encode("utf-8"))
        b = f.read_bytes()
        h.update(b)
        total += len(b)
    return h.hexdigest(), total


# --- Public API --------------------------------------------------------------
def run_full_load_one(company: Dict[str, Any], out_dir: str) -> str:
    """
    Full-load a single company into data/raw/<company_id>/initial.

    Parameters
    ----------
    company : dict
        Must include 'company_name'. If 'company_id' is missing,
        one will be derived from 'company_name'.
        (Optional) 'homepage' or 'source_url'.
    out_dir : str
        Destination directory (usually data/raw/<company_id>/initial).

    Returns
    -------
    str
        Path to the written metadata.json.
    """
    # Normalize company id + fields
    company_id = company.get("company_id") or _slugify(company.get("company_name", "unknown"))
    company_name = company.get("company_name", company_id)
    homepage = company.get("homepage") or company.get("source_url") or company.get("website") or ""

    out_path = Path(out_dir)
    _ensure_dir(out_path)

    # --- Adapter: call your Lab1 scraper regardless of its exact signature ----
    # We try keyword-first (company_id/out_dir), then positional, then the original (company/output_dir).
    scraper_result = None
    try:
        scraper_result = scrape_company(company_id=company_id, out_dir=str(out_path))  # type: ignore
    except TypeError:
        try:
            scraper_result = scrape_company(company_id, str(out_path))  # type: ignore[arg-type]
        except TypeError:
            # Fall back to the original style used earlier in your DAG
            scraper_result = scrape_company(company=company, output_dir=str(out_path))  # type: ignore

    # Compute lightweight content provenance of the output directory
    content_sha256, content_length = _dir_sha256_and_size(out_path)

    metadata = {
        "company_id": company_id,
        "company_name": company_name,
        "source_homepage": homepage,
        "crawled_at": _now_utc_iso(),
        "run_type": "full-load",
        "output_dir": str(out_path),
        "content_sha256": content_sha256,
        "content_length": content_length,
        "parser": "lab1_scraper",
        "version": 1,
    }

    # If the scraper returned structured info, include a trimmed view
    if isinstance(scraper_result, dict):
        metadata["scraper_result"] = {
            k: scraper_result[k]
            for k in list(scraper_result.keys())[:10]
            if k not in {"html", "raw_html", "content"}  # avoid huge fields
        }

    meta_path = out_path / "metadata.json"
    _write_json(meta_path, metadata)
    return str(meta_path)


def run_full_load_all(companies: Iterable[Dict[str, Any]], base_out: Path | None = None) -> List[str]:
    """
    Convenience function to run a full-load for many companies (useful for local testing).

    Returns a list of metadata.json paths (one per company).
    """
    base = base_out or RAW_DIR
    out_paths: List[str] = []
    for c in companies:
        cid = c.get("company_id") or _slugify(c.get("company_name", "unknown"))
        dest = base / cid / "initial"
        path = run_full_load_one(c, str(dest))
        out_paths.append(path)
    return out_paths


# --- CLI for quick local testing --------------------------------------------
def _load_seed(seed_path: Path, limit: int | None = None) -> List[Dict[str, Any]]:
    data = json.loads(seed_path.read_text(encoding="utf-8"))
    companies = data["companies"] if isinstance(data, dict) and "companies" in data else data
    # normalize ids
    for c in companies:
        c["company_id"] = c.get("company_id") or _slugify(c.get("company_name", "unknown"))
    return companies[:limit] if limit else companies


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run full-load ingestion (Lab 2 adapter).")
    p.add_argument("--seed", default=str(DATA_DIR / "forbes_ai50_seed.json"),
                   help="Path to the AI50 seed JSON.")
    p.add_argument("--limit", type=int, default=None, help="Limit companies for a dry run.")
    p.add_argument("--out", default=str(RAW_DIR), help="Base output dir (default: data/raw).")
    return p.parse_args()


def main() -> None:  # pragma: no cover
    args = _parse_args()
    seed_path = Path(args.seed)
    out_base = Path(args.out)
    out_base.mkdir(parents=True, exist_ok=True)

    companies = _load_seed(seed_path, args.limit)
    print(f"Loaded {len(companies)} companies from {seed_path}")

    meta_paths = run_full_load_all(companies, base_out=out_base)
    print(f"Wrote {len(meta_paths)} metadata files.")
    for p in meta_paths[:5]:
        print(" -", p)
    if len(meta_paths) > 5:
        print(" ...")


if __name__ == "__main__":  # pragma: no cover
    main()
