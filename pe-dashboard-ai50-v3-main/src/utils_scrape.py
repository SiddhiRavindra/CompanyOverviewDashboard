import re, json, datetime
from pathlib import Path

def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+","-", (name or "").lower()).strip("-") or "unknown"

def utc_now_iso() -> str:
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat()+"Z"

def write_json(path: Path, obj: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")
