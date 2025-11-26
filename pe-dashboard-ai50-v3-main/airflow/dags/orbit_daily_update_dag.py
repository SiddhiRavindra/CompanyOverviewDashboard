# airflow/dags/orbit_daily_update_dag.py
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import json
import os
from typing import Any, Dict, List

# Airflow 3.x: Old imports still work (deprecated but functional)
# Using old imports for compatibility - Airflow 3.x SDK imports have issues
# Future: migrate to airflow.sdk when stable
from airflow import DAG
from airflow.operators.python import PythonOperator

# In the Airflow Docker image, your repo is mounted at /opt/airflow
DATA_DIR = Path("/opt/airflow/data")
SRC_DIR = Path("/opt/airflow/src")

# Make src/ importable
import sys
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Import scraper
from ingest import run_full_load_one


def _read_json(path: Path) -> Any:
    """Read JSON file, return None if not found or invalid."""
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def _ensure_list(obj) -> List[dict]:
    """Normalize seed data to list of companies."""
    if isinstance(obj, dict) and "companies" in obj:
        return obj["companies"]
    return obj if isinstance(obj, list) else []


def daily_refresh(**context):
    """
    Daily refresh for all companies:
      - Creates date-based folder: data/raw/<company_id>/<YYYY-MM-DD>/
      - Runs scraper which collects website pages + external news
      - Saves all files in the date folder
    """
    seed_path = DATA_DIR / "forbes_ai50_seed.json"
    seed = _read_json(seed_path)
    rows = _ensure_list(seed)
    
    if not rows:
        print(f"[WARN] No companies found in {seed_path}")
        return

    # Get today's date in YYYY-MM-DD format
    today = datetime.utcnow().date().isoformat()
    
    # Normalize companies
    companies: List[dict] = []
    for r in rows:
        cid = (
            r.get("company_id")
            or r.get("company_name", "").strip().lower().replace(" ", "-")
            or r.get("website", "").strip().lower().replace("https://", "").replace("http://", "").split("/")[0]
        )
        companies.append(
            {
                "company_id": cid,
                "company_name": r.get("company_name") or cid,
                "website": r.get("website") or r.get("homepage") or "",
                "linkedin": r.get("linkedin", ""),
            }
        )

    success_count = 0
    failed_count = 0
    
    for comp in companies:
        cid = comp["company_id"]
        cname = comp.get("company_name", cid)
        
        # Create date-based output directory: data/raw/<company_id>/<YYYY-MM-DD>/
        out_dir = DATA_DIR / "raw" / cid / today
        out_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"[{cid}] Running daily refresh -> {out_dir}")
        
        try:
            # Run scraper which will collect website pages + external news
            meta_path = run_full_load_one(comp, str(out_dir))
            print(f"[{cid}] ✓ Success: {meta_path}")
            success_count += 1
        except Exception as e:
            print(f"[{cid}] ✗ Failed: {e}")
            failed_count += 1
            # Create failure manifest
            failure_manifest = {
                "company_id": cid,
                "company_name": cname,
                "status": "failed",
                "error": str(e),
                "run_date": today,
                "crawled_at": datetime.utcnow().isoformat() + "Z",
            }
            manifest_path = out_dir / "manifest.json"
            manifest_path.write_text(json.dumps(failure_manifest, indent=2), encoding="utf-8")
    
    print(f"\n[Daily Refresh Summary] Success: {success_count}, Failed: {failed_count}, Total: {len(companies)}")


# ---------------------- Airflow DAG ----------------------
with DAG(
    dag_id="orbit_daily_update_dag",
    description="Daily refresh for all Forbes AI50 companies with external news",
    start_date=datetime(2025, 1, 1),
    schedule="0 3 * * *",      # 03:00 every day
    catchup=False,
    tags=["orbit", "daily-update"],
    default_args={"retries": 1, "retry_delay": timedelta(minutes=5)},
) as dag:
    t1 = PythonOperator(
        task_id="daily_refresh_companies",
        python_callable=daily_refresh,
    )