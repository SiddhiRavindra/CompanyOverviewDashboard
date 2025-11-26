# airflow/dags/orbit_initial_load_dag.py
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Any, List

import pendulum
# Airflow 3.x: Old imports still work (deprecated but functional)
# Using old imports for compatibility - Airflow 3.x SDK imports have issues
# Future: migrate to airflow.sdk when stable
from airflow import DAG
from airflow.decorators import task
from airflow.exceptions import AirflowSkipException

# In the Airflow Docker image, your repo is mounted at /opt/airflow
DATA_DIR = Path("/opt/airflow/data")      # seed + raw live here
SRC_DIR  = Path("/opt/airflow/src")       # your python modules live here

# Make src/ importable
import sys
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Call the adapter from ingest module
from ingest import run_full_load_one  # run_full_load_one(company: dict, out_dir: str) -> str


def maybe_upload_dir_to_gcs(local_root: Path) -> None:
    """If PUSH_TO_CLOUD=true, mirror data/raw/** to gs://RAW_BUCKET/raw/**."""
    push = os.getenv("PUSH_TO_CLOUD", "false").lower() == "true"
    if not push:
        return

    bucket = os.getenv("RAW_BUCKET", "")
    if not bucket:
        raise ValueError("Set RAW_BUCKET when PUSH_TO_CLOUD=true")

    from google.cloud import storage  # ensure google-cloud-storage is in requirements.txt
    client = storage.Client()
    bkt = client.bucket(bucket)

    for p in local_root.rglob("*"):
        if p.is_file():
            rel = p.relative_to(DATA_DIR)
            bkt.blob(f"raw/{rel.as_posix()}").upload_from_filename(str(p))


with DAG(
    dag_id="orbit_initial_load_dag",
    description="Initial full-load ingestion for all Forbes AI50 companies",
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    schedule="@once",
    catchup=False,
    tags=["orbit", "initial-load"],
    default_args={"owner": "orbit"},
) as dag:

    @task()
    def load_company_list() -> List[Dict[str, Any]]:
        """Read data/forbes_ai50_seed.json and normalize company_id."""
        seed_path = DATA_DIR / "forbes_ai50_seed.json"
        data = json.loads(seed_path.read_text())
        companies = data["companies"] if isinstance(data, dict) and "companies" in data else data

        def slug(s: str) -> str:
            return "".join(ch.lower() if ch.isalnum() else "-" for ch in s).strip("-")

        for c in companies:
            c["company_id"] = c.get("company_id") or slug(c.get("company_name", "unknown"))
        return companies

    @task
    def prep_company_folder(company: Dict[str, Any]) -> Dict[str, Any]:
        """Create data/raw/<company_id>/initial and pass path forward."""
        out_dir = DATA_DIR / "raw" / company["company_id"] / "initial"
        out_dir.mkdir(parents=True, exist_ok=True)
        company["out_dir"] = str(out_dir)
        return company

    @task
    def scrape_company_pages(company: Dict[str, Any]) -> Dict[str, Any]:
        """Run the scraper (via ingest adapter) for a single company."""
        meta_path = run_full_load_one(company, company["out_dir"])
        company["metadata_path"] = meta_path
        return company

    @task
    def store_raw_to_cloud(companies: List[Dict[str, Any]]) -> str:
        """Optionally upload data/raw/** to GCS."""
        raw_root = DATA_DIR / "raw"
        if not raw_root.exists():
            raise AirflowSkipException("No data/raw found to upload.")
        maybe_upload_dir_to_gcs(raw_root)
        return "ok"

    # DAG wiring with task mapping
    company_list = load_company_list()
    prepped      = prep_company_folder.expand(company=company_list)
    scraped      = scrape_company_pages.expand(company=prepped)
    _            = store_raw_to_cloud(scraped)