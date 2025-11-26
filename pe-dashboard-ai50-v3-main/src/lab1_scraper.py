#!/usr/bin/env python3
# src/lab1_scraper_fixed.py
"""
Fixed Lab 1 Scraper - addresses DNS issues, section detection, and performance
NOW WITH LINKEDIN EXTRACTION
"""

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import sys
import time
from urllib.parse import urljoin, urlparse


try:  # Allow import both inside/outside package context
    from src.external_data_collector import (
        fetch_external_news,
        fetch_github_data,
        fetch_linkedin_data,
    )
except ModuleNotFoundError:  # Airflow container imports from /opt/airflow/src directly
    from external_data_collector import (
        fetch_external_news,
        fetch_github_data,
        fetch_linkedin_data,
    )

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_SEED_PATH = REPO_ROOT / "data" / "forbes_ai50_seed.json"
_SEED_INDEX = None

import requests
from bs4 import BeautifulSoup

try:
    import lxml  # noqa: F401
    _PARSER = "lxml"
except Exception:
    _PARSER = "html.parser"

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120 Safari/537.36"
)
HEADERS = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"}
TIMEOUT = 15  # Reduced from 25
MAX_RETRIES = 2

BLOCKED_HOSTS = {"forbes.com", "www.forbes.com", "w1.buysub.com", "buysub.com"}
SPAM_PATH = re.compile(r"(coupon|coupons|offer|deals|ref=|utm_|#)", re.I)

# -------- Improved Section Patterns (more strict) --------
PATTERNS = {
    "about": re.compile(
        r"^(about|about-us|company|who-we-are|our-story|our-team|mission|vision|values)$",
        re.I),
    "product": re.compile(
        r"^(products?|platform|solutions?|technology|features|api|services|offerings)$",
        re.I),
    "careers": re.compile(
        r"^(careers?|jobs?|join-us?|join|work-with-us|hiring|opportunities|open-positions)$",
        re.I),
    "blog": re.compile(
        r"^(blog|articles?|posts?|engineering-blog|technical-blog|developer-blog)$",
        re.I),
    "news": re.compile(
        r"^(news|newsroom|press-releases?|announcements?|latest-news|company-news|updates)$",
        re.I),
    "press": re.compile(
        r"^(press|media|media-kit|press-center|press-room|in-the-news|media-coverage)$",
        re.I),
    "events": re.compile(
        r"^(events?|webinars?|conferences?|workshops?|upcoming-events|event-calendar)$",
        re.I),
    "research": re.compile(
        r"^(research|publications?|papers?|whitepapers?|white-papers?|reports?|studies)$",
        re.I),
    "resources": re.compile(
        r"^(resources?|resource-center|docs?|documentation|guides?|tutorials?|learn|knowledge)$",
        re.I),
    "customers": re.compile(
        r"^(customers?|case-studies?|success-stories?|testimonials?|use-cases?|client-stories?)$",
        re.I),
}

CANDIDATE_SLUGS = {
    "homepage": [""],
    "about": ["about", "about-us", "company", "who-we-are", "our-story"],
    "product": ["products", "product", "platform", "solutions", "api", "technology"],
    "careers": ["careers", "jobs", "join-us", "join", "work-with-us"],
    "blog": ["blog", "articles", "engineering-blog"],
    "news": ["news", "newsroom", "press-releases", "announcements"],
    "press": ["press", "media", "media-kit", "press-center"],
    "events": ["events", "webinars", "conferences"],
    "research": ["research", "publications", "papers", "whitepapers"],
    "resources": ["resources", "docs", "documentation", "guides"],
    "customers": ["customers", "case-studies", "success-stories"],
}

SECTION_PRIORITY = [
    "homepage", "about", "product", "news", "blog", 
    "press", "careers", "events", "research", "customers", "resources"
]

try:
    from google.cloud import storage
    _HAS_GCS = True
except Exception:
    _HAS_GCS = False


# ========================== utilities ==========================

def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_seed(path="data/forbes_ai50_seed.json"):
    """Read seed WITHOUT normalizing URLs (defer to scrape time)"""
    data = read_json(path)
    rows = data.get("companies", data) if isinstance(data, dict) else data
    out = []
    for r in rows:
        cid = r.get("company_id") or slugify(r.get("company_name", ""))
        website = r.get("website", "").strip()
        # Just ensure https:// prefix, don't fetch
        if website and not website.startswith("http"):
            website = "https://" + website.lstrip("/")
        
        out.append({
            "company_id": cid,
            "company_name": r.get("company_name", cid),
            "website": website.rstrip("/"),
            "linkedin": r.get("linkedin", ""),
        })
    return out


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-") or "company"


def same_domain(u: str, base: str) -> bool:
    try:
        u_parsed = urlparse(u)
        b_parsed = urlparse(base)
        # Handle www. variations
        u_net = u_parsed.netloc.lower().replace("www.", "")
        b_net = b_parsed.netloc.lower().replace("www.", "")
        return u_net == b_net
    except Exception:
        return False


def is_html_ok(resp: requests.Response) -> bool:
    ctype = resp.headers.get("Content-Type", "").lower()
    return resp.status_code == 200 and ("text/html" in ctype or "application/xhtml" in ctype)


def fetch(url: str, retries=MAX_RETRIES) -> requests.Response:
    """Fetch with retry logic"""
    for attempt in range(retries):
        try:
            return requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if attempt == retries - 1:
                raise
            time.sleep(1)
    raise Exception("Max retries exceeded")


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, _PARSER)


def clean_text(html: str) -> str:
    s = soup(html)
    for tag in s(["script", "style", "noscript", "svg"]):
        tag.decompose()
    for tag in s.find_all(["nav", "footer", "form", "iframe"]):
        tag.decompose()
    text = s.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def extract_metadata(html: str, url: str) -> dict:
    """Extract structured metadata from HTML"""
    s = soup(html)
    meta = {}
    
    # OpenGraph tags
    for tag in s.find_all("meta", property=re.compile(r"og:")):
        prop = tag.get("property", "").replace("og:", "")
        content = tag.get("content", "")
        if prop and content:
            meta[f"og_{prop}"] = content
    
    # Twitter card tags
    for tag in s.find_all("meta", attrs={"name": re.compile(r"twitter:")}):
        name = tag.get("name", "").replace("twitter:", "")
        content = tag.get("content", "")
        if name and content:
            meta[f"twitter_{name}"] = content
    
    # Schema.org JSON-LD
    schema_data = []
    for script in s.find_all("script", type="application/ld+json"):
        try:
            schema_data.append(json.loads(script.string))
        except:
            pass
    if schema_data:
        meta["schema_org"] = schema_data
    
    # Meta description
    desc_tag = s.find("meta", attrs={"name": re.compile(r"description", re.I)})
    if desc_tag:
        meta["description"] = desc_tag.get("content", "")
    
    return meta


def page_meta(html: str, url: str, company_name: str, status: int) -> dict:
    s = soup(html)
    title = (s.title.get_text(strip=True) if s.title else "") or ""
    canonical = ""
    link_canon = s.find("link", rel=lambda x: x and "canonical" in x)
    if link_canon and link_canon.has_attr("href"):
        canonical = urljoin(url, link_canon["href"])
    robots = ""
    meta_robots = s.find("meta", attrs={"name": re.compile(r"robots", re.I)})
    if meta_robots and meta_robots.has_attr("content"):
        robots = meta_robots["content"]

    content_bytes = html.encode("utf-8")
    structured_meta = extract_metadata(html, url)
    
    return {
        "company_name": company_name,
        "source_url": url,
        "crawled_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "http_status": status,
        "title": title[:400],
        "canonical": canonical or url,
        "robots": robots,
        "content_sha256": hashlib.sha256(content_bytes).hexdigest(),
        "content_length": len(content_bytes),
        "parser": "lxml" if _PARSER == "lxml" else "bs4",
        "structured_metadata": structured_meta,
        "version": 2,
    }


def blocked(host: str) -> bool:
    host = (host or "").lower()
    return host in BLOCKED_HOSTS or any(host.endswith("." + b) for b in BLOCKED_HOSTS)


def normalize_path(path: str) -> str:
    """Normalize path for comparison"""
    path = path.lower().strip("/")
    # Remove common suffixes
    path = re.sub(r"\.(html|htm|php|asp|aspx)$", "", path)
    return path


def extract_linkedin_metadata(company_name: str, homepage_html: str, base_url: str):
    """
    Extract LinkedIn profile URL and other social links from HTML
    Also extracts company info from structured data
    """
    s = soup(homepage_html)
    linkedin_data = {
        "company_profile": None,
        "other_social": {},
        "found_on_page": base_url,
    }
    
    # LinkedIn regex patterns
    linkedin_company_pattern = re.compile(r'linkedin\.com/company/([^/\s"\'?#]+)', re.I)
    
    # Check all links on the page
    for a in s.find_all("a", href=True):
        href = a.get("href", "").strip()
        
        # LinkedIn company page
        if "linkedin.com/company" in href.lower():
            match = linkedin_company_pattern.search(href)
            if match:
                company_slug = match.group(1).rstrip("/")
                linkedin_data["company_profile"] = f"https://www.linkedin.com/company/{company_slug}"
        
        # Other social media (bonus)
        elif "twitter.com" in href.lower() or "x.com" in href.lower():
            if "other_social" not in linkedin_data:
                linkedin_data["other_social"] = {}
            linkedin_data["other_social"]["twitter"] = href.split("?")[0]  # Remove tracking
        elif "github.com" in href.lower():
            if "other_social" not in linkedin_data:
                linkedin_data["other_social"] = {}
            linkedin_data["other_social"]["github"] = href.split("?")[0]
        elif "youtube.com" in href.lower():
            if "other_social" not in linkedin_data:
                linkedin_data["other_social"] = {}
            linkedin_data["other_social"]["youtube"] = href.split("?")[0]
    
    # Check JSON-LD structured data for LinkedIn and company info
    for script in s.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if isinstance(data, dict):
                # Look for sameAs property (common in Organization schema)
                same_as = data.get("sameAs", [])
                if isinstance(same_as, list):
                    for link in same_as:
                        if "linkedin.com/company" in link:
                            match = linkedin_company_pattern.search(link)
                            if match:
                                company_slug = match.group(1).rstrip("/")
                                linkedin_data["company_profile"] = f"https://www.linkedin.com/company/{company_slug}"
                
                # Extract additional company info
                if data.get("@type") == "Organization":
                    if "structured_data" not in linkedin_data:
                        linkedin_data["structured_data"] = {}
                    linkedin_data["structured_data"] = {
                        "name": data.get("name", company_name),
                        "description": data.get("description"),
                        "foundingDate": data.get("foundingDate"),
                        "employees": data.get("numberOfEmployees"),
                        "address": data.get("address"),
                    }
        except:
            pass
    
    return linkedin_data


def discover_from_nav(base_url: str, homepage_html: str, section_key: str):
    """Enhanced discovery with better scoring"""
    s = soup(homepage_html)
    candidates = []
    
    # Find navigation areas
    nav_areas = s.find_all(["nav", "header"]) + s.find_all(attrs={"role": "navigation"})
    all_links = []
    
    for nav in nav_areas:
        for a in nav.find_all("a", href=True):
            all_links.append((a, True))
    
    for a in s.find_all("a", href=True):
        all_links.append((a, False))
    
    for a, is_nav in all_links:
        href = a.get("href", "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
            
        text = (a.get_text() or "").strip()
        url_abs = urljoin(base_url + "/", href)
        
        if not same_domain(url_abs, base_url):
            continue
        if SPAM_PATH.search(url_abs):
            continue
        
        candidates.append((url_abs, text, is_nav))

    pattern = PATTERNS[section_key]

    def score(candidate):
        url_abs, text, is_nav = candidate
        p = urlparse(url_abs)
        path = normalize_path(p.path or "/")
        t = text.lower().strip()
        
        # Remove common words from text for matching
        t_normalized = re.sub(r'\b(our|the|view|see|explore)\b', '', t).strip()
        
        sc = 0.0
        
        # Exact path match (highest priority)
        if pattern.match(path):
            sc += 10.0
        
        # Path segment match
        path_segments = [seg for seg in path.split("/") if seg]
        if path_segments:
            last_segment = path_segments[-1]
            if pattern.match(last_segment):
                sc += 8.0
        
        # Anchor text exact match
        if pattern.match(t_normalized):
            sc += 6.0 if is_nav else 4.0
        
        # Partial pattern match in text
        if pattern.search(t):
            sc += 3.0 if is_nav else 2.0
        
        # Prefer shorter paths
        if path in ("", "/"):
            sc -= 3.0
        sc += max(0.0, 2.0 - 0.4 * len(path_segments))
        
        # Penalize query params heavily
        if p.query:
            sc -= 2.0
        
        return sc

    ranked = sorted(candidates, key=score, reverse=True)
    seen, out = set(), []
    for u, _, _ in ranked:
        normalized_u = u.split("#")[0].split("?")[0]  # Remove fragments and query
        if normalized_u not in seen and score((u, "", False)) > 0:
            seen.add(normalized_u)
            out.append(u)
    return out[:8]


def try_section(base_url: str, homepage_html: str, section_key: str):
    """Try canonical slugs first; then ranked nav-discovered candidates."""
    tried = []
    
    # Try canonical slugs
    for slug in CANDIDATE_SLUGS.get(section_key, []):
        url = base_url if slug == "" else urljoin(base_url + "/", slug)
        if url not in tried and not SPAM_PATH.search(url):
            tried.append(url)
    
    # Add discovered URLs
    discovered = discover_from_nav(base_url, homepage_html, section_key)
    tried.extend(u for u in discovered if u not in tried)

    for u in tried:
        try:
            r = fetch(u)
            if is_html_ok(r) and same_domain(r.url, base_url):
                # Verify content is substantial and relevant
                text = clean_text(r.text)
                if len(text) > 100:
                    # Additional validation: check if page title or content relates to section
                    s = soup(r.text)
                    title = (s.title.get_text() if s.title else "").lower()
                    pattern = PATTERNS[section_key]
                    
                    # For strict sections, require pattern match in title or URL
                    if section_key in ["careers", "blog", "news", "press", "events"]:
                        url_path = normalize_path(urlparse(r.url).path)
                        if pattern.search(title) or pattern.search(url_path):
                            return r.url.rstrip("/"), r.text, r.status_code
                    else:
                        return r.url.rstrip("/"), r.text, r.status_code
        except Exception:
            continue
    
    return None, None, None


def ensure_dir(p: pathlib.Path):
    p.mkdir(parents=True, exist_ok=True)


def write_text(path: pathlib.Path, content: str):
    ensure_dir(path.parent)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def save_page(out_dir: pathlib.Path, section: str, url: str, html: str,
              company_name: str, status: int, pages_meta_fp):
    write_text(out_dir / f"{section}.html", html)
    write_text(out_dir / f"{section}.txt", clean_text(html))
    m = page_meta(html, url, company_name, status)
    write_text(out_dir / f"{section}.meta.json", json.dumps(m, indent=2))
    pages_meta_fp.write(json.dumps({
        "company_name": company_name,
        "section": section,
        "source_url": url,
        "crawled_at": m["crawled_at"],
        "status": status,
        "bytes": m["content_length"],
    }) + "\n")


def upload_dir_to_gcs(local_dir: pathlib.Path, bucket_name: str, prefix: str = ""):
    if not _HAS_GCS:
        raise RuntimeError("google-cloud-storage not installed")
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    for root, _, files in os.walk(local_dir):
        for name in files:
            lp = pathlib.Path(root) / name
            rel = lp.relative_to(local_dir)
            bucket.blob(str(pathlib.Path(prefix) / rel)).upload_from_filename(str(lp))


# ========================== adapters ==========================

def _seed_record(company_id: str):
    global _SEED_INDEX
    if _SEED_INDEX is None:
        if DEFAULT_SEED_PATH.exists():
            try:
                rows = read_seed(str(DEFAULT_SEED_PATH))
            except Exception:
                _SEED_INDEX = {}
            else:
                _SEED_INDEX = {row["company_id"]: row for row in rows}
        else:
            _SEED_INDEX = {}
    return (_SEED_INDEX or {}).get(company_id)


def _resolve_company_inputs(company_id=None, company=None, overrides=None):
    company = company or {}
    cid = company.get("company_id") or company_id or company.get("company_name", "")
    cid = slugify(cid or "")
    name = company.get("company_name") or company_id or cid
    website = (
        company.get("website")
        or company.get("homepage")
        or company.get("source_url")
        or company.get("url")
        or ""
    )
    linkedin = company.get("linkedin", "")

    overrides = overrides or {}
    override_url = overrides.get(cid)
    if override_url:
        website = override_url

    if not website:
        seed_entry = _seed_record(cid)
        if seed_entry:
            name = seed_entry.get("company_name", name)
            website = seed_entry.get("website") or seed_entry.get("homepage") or website
            linkedin = seed_entry.get("linkedin") or linkedin

    website = (website or "").strip()
    if website and not website.startswith("http"):
        website = "https://" + website.lstrip("/")
    website = website.rstrip("/")

    return {
        "company_id": cid or "company",
        "company_name": name or cid or "company",
        "website": website,
        "linkedin": linkedin,
    }


class ScrapeCompanyError(Exception):
    def __init__(self, company_id: str, message: str, reason: str = "error"):
        super().__init__(message)
        self.company_id = company_id
        self.reason = reason


def _scrape_company_to_dir(record: dict, out_dir: pathlib.Path, sections_to_scrape=None) -> dict:
    """Enhanced scraping with configurable sections and LinkedIn extraction"""
    cid = record["company_id"]
    name = record["company_name"]
    base_url = record.get("website", "")
    
    if not base_url:
        raise ScrapeCompanyError(cid, "cannot scrape without a website URL", reason="missing_website")

    host = urlparse(base_url).netloc.lower()
    if blocked(host):
        raise ScrapeCompanyError(cid, f"seed website blocked ({base_url})", reason="blocked_host")

    ensure_dir(out_dir)

    try:
        r0 = fetch(base_url)
    except Exception as exc:
        raise ScrapeCompanyError(
            cid, f"homepage fetch failed ({base_url}) -> {exc}", reason="homepage_fetch_failed"
        ) from exc

    if not is_html_ok(r0):
        status = getattr(r0, "status_code", None)
        raise ScrapeCompanyError(
            cid,
            f"homepage not HTML/200 ({base_url}) status={status}",
            reason="homepage_http_error",
        )

    homepage_final = r0.url.rstrip("/")
    final_host = urlparse(homepage_final).netloc.lower()
    if blocked(final_host):
        raise ScrapeCompanyError(
            cid, f"homepage resolved to blocked host ({homepage_final})", reason="blocked_redirect"
        )

    homepage_html = r0.text
    
    # Extract LinkedIn and social links from homepage
    linkedin_data = extract_linkedin_metadata(name, homepage_html, homepage_final)
    
    pages_meta_path = out_dir / "pages.jsonl"
    sections_to_scrape = sections_to_scrape or [s for s in SECTION_PRIORITY if s != "homepage"]
    
    with open(pages_meta_path, "w", encoding="utf-8") as pages_fp:
        save_page(out_dir, "homepage", homepage_final, homepage_html, name, r0.status_code, pages_fp)
        
        manifest = {
            "company_id": cid,
            "company_name": name,
            "crawled_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sections": {"homepage": homepage_final},
            "linkedin_data": linkedin_data,  # LinkedIn info added here
            "scraper_version": 2,
        }

        for section in sections_to_scrape:
            if section == "homepage":
                continue
            
            url, html, status = try_section(homepage_final, homepage_html, section)
            if url and html:
                save_page(out_dir, section, url, html, name, status, pages_fp)
                manifest["sections"][section] = url
                
                # Also check these pages for LinkedIn if not found on homepage
                if not linkedin_data.get("company_profile") and section in ["about", "careers"]:
                    page_linkedin = extract_linkedin_metadata(name, html, url)
                    if page_linkedin.get("company_profile"):
                        linkedin_data.update(page_linkedin)
                        manifest["linkedin_data"] = linkedin_data
            else:
                manifest["sections"][section] = None
            
            time.sleep(0.3)  # Rate limiting

    # Fetch external data (news, LinkedIn, GitHub)
    external_dir = out_dir / "external"
    ensure_dir(external_dir)
    
    # Fetch external news from RSS feeds (filtered to last 1 day for daily refresh)
    try:
        # For daily refresh, only get articles from the last 1 day
        external_news = fetch_external_news(name, base_url, days_back=1)
        # Always create news.json for consistency (empty array if no articles)
        write_text(external_dir / "news.json", json.dumps(external_news, indent=2))
        manifest["external_news_count"] = len(external_news)
        manifest["external_news_sources"] = list(set([n.get("source", "unknown") for n in external_news])) if external_news else []
        if external_news:
            print(f"[{cid}] Fetched {len(external_news)} external news articles from RSS feeds")
        else:
            print(f"[{cid}] No external news articles found in last 1 day")
    except Exception as e:
        print(f"[WARN] Failed to fetch external news for {cid}: {e}")
        manifest["external_news_count"] = 0
        manifest["external_news_sources"] = []
    
    # Fetch LinkedIn data if LinkedIn URL is available
    linkedin_url_from_data = linkedin_data.get("company_profile") or record.get("linkedin", "")
    if linkedin_url_from_data:
        try:
            linkedin_api_data = fetch_linkedin_data(linkedin_url_from_data)
            if linkedin_api_data:
                write_text(external_dir / "linkedin.json", json.dumps(linkedin_api_data, indent=2))
        except Exception as e:
            print(f"[WARN] Failed to fetch LinkedIn data for {cid}: {e}")
    
    # Fetch GitHub data
    try:
        github_data = fetch_github_data(name)
        if github_data and github_data.get("organization"):
            write_text(external_dir / "github.json", json.dumps(github_data, indent=2))
            manifest["github_data"] = {
                "organization": github_data.get("organization"),
                "repos_count": github_data.get("repos_count", 0),
                "stars_total": github_data.get("stars_total", 0),
            }
            print(f"[{cid}] Found GitHub org: {github_data.get('organization')}")
    except Exception as e:
        print(f"[WARN] Failed to fetch GitHub data for {cid}: {e}")

    write_text(out_dir / "manifest.json", json.dumps(manifest, indent=2))
    return {
        "company_id": cid,
        "company_name": name,
        "manifest_path": str(out_dir / "manifest.json"),
        "sections": manifest["sections"],
        "linkedin_data": linkedin_data,  # Return LinkedIn info
        "status": "success",
    }


def scrape_company(
    company_id=None,
    out_dir=None,
    *,
    company=None,
    overrides=None,
    output_dir=None,
    sections=None,
    **_,
):
    if out_dir is None and output_dir is not None:
        out_dir = output_dir
    if out_dir is None:
        raise ValueError("scrape_company requires out_dir or output_dir")

    record = _resolve_company_inputs(company_id=company_id, company=company, overrides=overrides)
    out_path = pathlib.Path(out_dir)
    try:
        return _scrape_company_to_dir(record, out_path, sections_to_scrape=sections)
    except ScrapeCompanyError as exc:
        ensure_dir(out_path)
        failure_manifest = {
            "company_id": record["company_id"],
            "company_name": record["company_name"],
            "status": "failed",
            "reason": exc.reason,
            "message": str(exc),
            "crawled_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        write_text(out_path / "manifest.json", json.dumps(failure_manifest, indent=2))
        if not (out_path / "pages.jsonl").exists():
            write_text(out_path / "pages.jsonl", "")
        return failure_manifest


def main():
    ap = argparse.ArgumentParser(description="Fixed Lab 1: Scrape & Store (with LinkedIn)")
    ap.add_argument("--seed", default="data/forbes_ai50_seed.json")
    ap.add_argument("--overrides", help="JSON map: company_id -> official base URL")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--company")
    ap.add_argument("--out", default="data/raw")
    ap.add_argument("--run-mode", choices=["initial", "run"], default="initial")
    ap.add_argument("--gcs-bucket")
    ap.add_argument("--sections", help="Comma-separated list of sections to scrape")
    ap.add_argument("--skip-dns-check", action="store_true", help="Skip companies with DNS errors")
    args = ap.parse_args()

    companies = read_seed(args.seed)
    if args.company:
        companies = [c for c in companies if c["company_id"] == args.company]
    if args.limit and args.limit > 0:
        companies = companies[:args.limit]

    overrides = {}
    if args.overrides and os.path.exists(args.overrides):
        overrides = read_json(args.overrides)

    sections_to_scrape = None
    if args.sections:
        sections_to_scrape = [s.strip() for s in args.sections.split(",")]

    success_count = 0
    linkedin_summary = []  # Track LinkedIn findings
    
    for idx, c in enumerate(companies, 1):
        cid = c["company_id"]
        name = c["company_name"]

        if args.run_mode == "initial":
            out_dir = pathlib.Path(args.out) / cid / "initial"
        else:
            ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
            out_dir = pathlib.Path(args.out) / cid / "runs" / ts

        base_display = overrides.get(cid) or c.get("website") or "N/A"
        print(f"\n[{idx}/{len(companies)}] {name}")
        print(f"  Website: {base_display}")

        result = scrape_company(
            company=c, 
            out_dir=str(out_dir), 
            overrides=overrides,
            sections=sections_to_scrape
        )
        
        if result.get("status") != "success":
            reason = result.get("reason", "unknown")
            msg = result.get("message", "")
            print(f"  ✗ Failed: {reason}")
            if args.skip_dns_check and "DNS" in msg or "resolve" in msg:
                print(f"    (skipping DNS error)")
            continue
        
        # Show what was found
        sections = result.get("sections", {})
        for section_key in SECTION_PRIORITY:
            if section_key == "homepage":
                continue
            if sections.get(section_key):
                print(f"    ✓ {section_key}: {sections[section_key]}")
        
        # Show LinkedIn if found
        linkedin_data = result.get("linkedin_data", {})
        if linkedin_data.get("company_profile"):
            print(f"    🔗 LinkedIn: {linkedin_data['company_profile']}")
            linkedin_summary.append({
                "company_id": cid,
                "company_name": name,
                "linkedin": linkedin_data["company_profile"],
                "other_social": linkedin_data.get("other_social", {}),
            })
        
        success_count += 1

        if args.gcs_bucket:
            prefix = f"raw/{cid}/" + ("initial" if args.run_mode == "initial" else f"runs/{out_dir.name}")
            print(f"  ↥ uploading to gs://{args.gcs_bucket}/{prefix}")
            upload_dir_to_gcs(out_dir, args.gcs_bucket, prefix=prefix)

        time.sleep(1.0)

    print(f"\n✓ Successfully scraped {success_count}/{len(companies)} companies")
    
    # Save LinkedIn summary
    if linkedin_summary:
        summary_path = pathlib.Path(args.out) / "linkedin_profiles.json"
        with open(summary_path, "w") as f:
            json.dump(linkedin_summary, f, indent=2)
        print(f"✓ Saved {len(linkedin_summary)} LinkedIn profiles to: {summary_path}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())