#!/usr/bin/env python3
# src/seed_cleaner.py
import json, re, sys, time
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0"}
REQ_TIMEOUT = 20

# Hosts we never want as the official website
BLOCK_HOSTS = {
    "forbes.com", "www.forbes.com",
    "w1.buysub.com", "buysub.com", "subscribe.forbes.com",
    "twitter.com", "x.com", "linkedin.com", "www.linkedin.com",
    "facebook.com", "instagram.com", "medium.com", "substack.com",
    "youtube.com", "tiktok.com", "linktr.ee"
}

VALID_TLDS = re.compile(r"\.(com|ai|io|co|org|net|dev|app|tech|cloud|systems|software|studio|labs)(/|$)", re.I)

# Optional manual overrides for stubborn cases
OVERRIDES = {
    "OpenAI": "https://openai.com",
    "Anthropic": "https://www.anthropic.com",
    "Databricks": "https://www.databricks.com",
    "Cohere": "https://cohere.com",
    "Perplexity AI": "https://www.perplexity.ai",
    "Mistral AI": "https://mistral.ai",
    "Runway": "https://runwayml.com",
    "Midjourney": "https://www.midjourney.com",
    "Baseten": "https://www.baseten.co",
    "SambaNova": "https://sambanova.ai",
    "Glean": "https://www.glean.com",
    "Fig​ure AI": "https://figure.ai",  # in case of unicode/space variants
    "Figure AI": "https://figure.ai",
    "Suno": "https://www.suno.com",
    "Sakana AI": "https://sakana.ai",
    "Together AI": "https://www.together.ai",
    "VAST Data": "https://www.vastdata.com",
    "Snorkel AI": "https://www.snorkel.ai",
    "ElevenLabs": "https://elevenlabs.io",
    "DeepL": "https://www.deepl.com",
}

def norm_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())

def is_blocked(host: str) -> bool:
    host = (host or "").lower()
    return host in BLOCK_HOSTS or any(host.endswith("." + b) for b in BLOCK_HOSTS)

def is_valid_candidate(url: str) -> bool:
    try:
        p = urlparse(url)
        if not p.scheme.startswith("http"):
            return False
        if is_blocked(p.netloc):
            return False
        if not VALID_TLDS.search(url):
            return False
        return True
    except Exception:
        return False

def fetch(url: str):
    return requests.get(url, headers=HEADERS, timeout=REQ_TIMEOUT, allow_redirects=True)

def extract_jsonld_urls(html: str, base: str):
    urls = []
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "{}")
        except Exception:
            continue
        # could be list or object
        items = data if isinstance(data, list) else [data]
        for item in items:
            # organization/website often has 'url' or 'sameAs'
            for key in ("url", "mainEntityOfPage"):
                u = item.get(key)
                if isinstance(u, str):
                    urls.append(urljoin(base, u))
            same = item.get("sameAs")
            if isinstance(same, list):
                for u in same:
                    if isinstance(u, str):
                        urls.append(urljoin(base, u))
            elif isinstance(same, str):
                urls.append(urljoin(base, same))
    # Dedup while preserving order
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u); out.append(u)
    return out

def extract_links(html: str, base: str):
    soup = BeautifulSoup(html, "html.parser")
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = urljoin(base, a["href"].strip())
        if href not in seen:
            seen.add(href); out.append(href)
    return out

def score_candidate(url: str, company_slug: str) -> float:
    """
    Higher is better. Prefer:
    - domain containing company slug
    - short path
    - https
    - no query params
    """
    try:
        p = urlparse(url)
        score = 0.0
        host = p.netloc.lower()
        path = p.path or "/"
        if url.startswith("https://"):
            score += 1.0
        if company_slug and company_slug in host.replace("www.", ""):
            score += 3.5
        # Short path is better
        if path == "/" or len(path) <= 8:
            score += 1.0
        # fewer segments better
        segs = [s for s in path.split("/") if s]
        score += max(0, 1.0 - 0.25 * (len(segs)))
        # query/fragment are suspicious
        if p.query:
            score -= 0.5
        if p.fragment:
            score -= 0.2
        return score
    except Exception:
        return -1.0

def quick_head_ok(url: str) -> bool:
    try:
        r = requests.get(url, headers=HEADERS, timeout=REQ_TIMEOUT, allow_redirects=True)
        ct = r.headers.get("Content-Type","").lower()
        return r.status_code == 200 and ("text/html" in ct)
    except Exception:
        return False

def guess_domains(company_slug: str):
    guesses = [f"https://{company_slug}.{tld}" for tld in ("com","ai","io","co")]
    return [u for u in guesses if quick_head_ok(u)]

def pick_official_site(forbes_profile_url: str, company_name: str):
    """
    Try (in order):
      1) Overrides
      2) JSON-LD 'url'/'sameAs' filtered and scored
      3) On-page links filtered and scored
      4) Guessed domains (slug .com/.ai/.io/.co)
    """
    if company_name in OVERRIDES:
        return OVERRIDES[company_name]

    company_slug = norm_slug(company_name)
    try:
        r = fetch(forbes_profile_url)
        r.raise_for_status()
    except Exception:
        return None

    candidates = []
    # From JSON-LD
    for u in extract_jsonld_urls(r.text, forbes_profile_url):
        if is_valid_candidate(u):
            candidates.append(u)
    # From page links
    for u in extract_links(r.text, forbes_profile_url):
        if is_valid_candidate(u):
            candidates.append(u)

    # De-dup
    seen, uniq = set(), []
    for u in candidates:
        if u not in seen:
            seen.add(u); uniq.append(u)

    # Score
    scored = sorted(uniq, key=lambda u: score_candidate(u, company_slug), reverse=True)
    if scored:
        # sanity: HEAD check top few
        for u in scored[:6]:
            if quick_head_ok(u):
                return u

    # Fallback: guess
    for u in guess_domains(company_slug):
        return u

    return None

def normalize(u):
    if not u.startswith("http"):
        u = "https://" + u
    return u.rstrip("/")

def main(seed_path="data/forbes_ai50_seed.json", out_path=None):
    with open(seed_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Support list or {"companies": [...]}
    if isinstance(data, dict) and "companies" in data:
        items = data["companies"]
        wrapper = "dict"
    else:
        items = data
        wrapper = "list"

    changed = 0
    for row in items:
        name = row.get("company_name") or row.get("name") or row.get("company") or ""
        site = row.get("website", "") or row.get("site", "")
        if not name:
            continue

        # If already looks like a legit site, keep it
        try:
            ph = urlparse(site)
            if ph.scheme and not is_blocked(ph.netloc) and VALID_TLDS.search(site):
                # keep as-is
                continue
        except Exception:
            pass

        # If seed website is a Forbes link or busted, try to discover
        profile = site if "forbes.com" in (site or "").lower() else None
        if not profile:
            # also accept a separate field like 'forbes_url'
            f_url = row.get("forbes_url") or row.get("profile_url")
            if isinstance(f_url, str) and "forbes.com" in f_url.lower():
                profile = f_url

        new_site = None
        if profile:
            new_site = pick_official_site(profile, name)

        if not new_site:
            # Last resort: guesses
            new_site = next(iter(guess_domains(norm_slug(name))), None)

        if new_site:
            row["website"] = normalize(new_site)
            changed += 1
            print(f"✓ {name} -> {row['website']}")
        else:
            print(f"! {name}: could not find official site (left as-is)")

        # Be a little polite if we’re hitting many pages
        time.sleep(0.25)

    out_path = out_path or seed_path
    with open(out_path, "w", encoding="utf-8") as f:
        if wrapper == "dict":
            json.dump({"companies": items}, f, indent=2)
        else:
            json.dump(items, f, indent=2)
    print(f"\nUpdated {changed} entrie(s). Wrote: {out_path}")

if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else "data/forbes_ai50_seed.json"
    main(p)
