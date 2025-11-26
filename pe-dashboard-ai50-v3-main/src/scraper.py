import requests
from pathlib import Path
from urllib.parse import urljoin
from .cleaners import html_to_text
from .utils_scrape import slugify, utc_now_iso, write_json

DEFAULT_PAGES = ["/", "/about", "/product", "/platform", "/careers", "/blog", "/news"]

def _fetch(url: str, timeout=15):
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent":"Mozilla/5.0"})
        if r.status_code == 200 and r.text: return r.text
    except Exception: pass
    return None

def scrape_company(company: dict, out_root: Path, subfolder="initial", pages=None):
    pages = pages or DEFAULT_PAGES
    name = company.get("company_name") or "Unknown"
    base = (company.get("website") or "").rstrip("/")
    base = base if base.startswith("http") else (f"https://{base}" if base else "")
    cid  = slugify(name)
    outdir = (out_root / "raw" / cid / subfolder); outdir.mkdir(parents=True, exist_ok=True)

    for path in pages:
        if not base: continue
        url = urljoin(base + "/", path.lstrip("/"))
        key = path.strip("/").replace("/", "_") or "home"
        write_json(outdir / f"{key}.meta.json", {"company_name": name, "source_url": url, "crawled_at": utc_now_iso()})
        html = _fetch(url)
        if not html: continue
        (outdir / f"{key}.html").write_text(html, encoding="utf-8")
        (outdir / f"{key}.txt").write_text(html_to_text(html), encoding="utf-8")
