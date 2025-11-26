"""
External Data Collector Module
Fetches news from Google News RSS feeds with deduplication and date filtering.
Includes rate limiting to avoid throttling/IP blocking.
"""

import os
import json
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse, quote_plus

import requests

try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False
    print("[WARN] feedparser not available. Install with: pip install feedparser")

HTTP_TIMEOUT = 15
USER_AGENT = "PE-Dashboard-Bot/1.0"

# Rate limiting: delay between requests (seconds)
# Recommended: 1-2 seconds to avoid throttling
# For 50 companies: ~50-100 seconds total (acceptable for daily refresh)
import random
REQUEST_DELAY = random.uniform(2, 4)  # 2-4 seconds between requests

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY_BASE = 2  # Base delay for exponential backoff


def _parse_date(date_str: str) -> Optional[datetime]:
    """Parse various date formats from RSS feeds."""
    if not date_str:
        return None
    
    # Try feedparser's date parsing first (handles RFC 822, RFC 3339, etc.)
    if HAS_FEEDPARSER:
        try:
            parsed = feedparser._parse_date(date_str)
            if parsed:
                return datetime(*parsed[:6], tzinfo=timezone.utc)
        except:
            pass
    
    # Try RFC 822 format (used by Google News): "Wed, 19 Nov 2025 02:00:37 GMT"
    rfc822_formats = [
        "%a, %d %b %Y %H:%M:%S %Z",  # With timezone name
        "%a, %d %b %Y %H:%M:%S %z",  # With timezone offset
        "%a, %d %b %Y %H:%M:%S GMT",  # Explicit GMT
    ]
    
    for fmt in rfc822_formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except:
            continue
    
    # Try common ISO formats
    iso_formats = [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%d %b %Y %H:%M:%S",
    ]
    
    for fmt in iso_formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except:
            continue
    
    return None


def _normalize_url(url: str) -> str:
    """Normalize URL for deduplication."""
    if not url:
        return ""
    # Remove common tracking parameters
    url = url.split("?")[0] if "?" in url else url
    url = url.split("#")[0] if "#" in url else url
    # Remove trailing slash
    url = url.rstrip("/")
    return url.lower()


def _is_recent_article(article_date: Optional[datetime], days_back: int = 1) -> bool:
    """Check if article is within the specified number of days."""
    if not article_date:
        return False
    
    # Calculate cutoff: now minus days_back (e.g., 1 day ago)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    # Article is recent if it's published on or after the cutoff
    return article_date >= cutoff


def fetch_external_news(
    company_name: str, 
    website: str = "", 
    days_back: int = 1,
    delay: float = REQUEST_DELAY
) -> List[Dict]:
    """
    Fetch external news articles from Google News RSS feed about the company.
    
    Includes rate limiting to avoid throttling/IP blocking.
    
    Args:
        company_name: Company name to search for
        website: Company website URL (optional, not used but kept for API compatibility)
        days_back: Number of days to look back (default: 1 for daily refresh)
        delay: Delay in seconds before making request (for rate limiting)
    
    Returns:
        List of news articles: [{"title": "...", "url": "...", "published_at": "...", "source": "..."}]
    """
    if not HAS_FEEDPARSER:
        print("[WARN] feedparser not available. Cannot fetch RSS feeds.")
        return []
    
    all_articles = []
    seen_urls: Set[str] = set()
    
    # Rate limiting: delay before request
    if delay > 0:
        time.sleep(delay)
    
    # Construct Google News RSS URL
    google_news_url = f'https://news.google.com/rss/search?q="{quote_plus(company_name)}"&hl=en-US&gl=US&ceid=US:en'
    
    # Retry logic with exponential backoff
    for attempt in range(MAX_RETRIES):
        try:
            feed = feedparser.parse(google_news_url)
            
            # Check for parse errors
            if feed.bozo and feed.bozo_exception:
                error_msg = str(feed.bozo_exception)
                # Check if it's a rate limit error (429 or similar)
                if "429" in error_msg or "too many" in error_msg.lower() or "rate limit" in error_msg.lower():
                    if attempt < MAX_RETRIES - 1:
                        wait_time = RETRY_DELAY_BASE * (2 ** attempt)
                        print(f"[WARN] Rate limit detected, waiting {wait_time}s before retry {attempt + 1}/{MAX_RETRIES}")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"[ERROR] Rate limited after {MAX_RETRIES} attempts")
                        return []
                else:
                    print(f"[WARN] Google News RSS parse error: {error_msg}")
                    return []
            
            # Process feed entries
            for entry in feed.entries:
                article_url = entry.get("link", "").strip()
                if not article_url:
                    continue
                
                # Deduplicate
                normalized_url = _normalize_url(article_url)
                if normalized_url in seen_urls:
                    continue
                seen_urls.add(normalized_url)
                
                # Parse published date (Google News uses RFC 822 format)
                published_at = None
                published_str = entry.get("published", "") or entry.get("updated", "")
                if published_str:
                    published_at = _parse_date(published_str)
                
                # Filter by date (only recent articles)
                if not _is_recent_article(published_at, days_back=days_back):
                    continue
                
                # Extract article data
                title = entry.get("title", "")
                description = entry.get("description", "") or entry.get("summary", "")
                
                # Extract source from Google News entry
                source = "Google News"
                if hasattr(entry, "source") and entry.source:
                    source = entry.source.get("title", "Google News")
                
                article = {
                    "title": title,
                    "url": article_url,
                    "published_at": published_at.isoformat() if published_at else "",
                    "source": source,
                    "description": description[:500] if description else "",
                    "feed_url": google_news_url,
                }
                
                all_articles.append(article)
            
            # Success - break out of retry loop
            break
            
        except Exception as e:
            error_msg = str(e)
            # Check for rate limiting or network errors
            if "429" in error_msg or "too many" in error_msg.lower() or "rate limit" in error_msg.lower():
                if attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_DELAY_BASE * (2 ** attempt)
                    print(f"[WARN] Rate limit error, waiting {wait_time}s before retry {attempt + 1}/{MAX_RETRIES}")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"[ERROR] Rate limited after {MAX_RETRIES} attempts: {e}")
                    return []
            else:
                print(f"[WARN] Error fetching Google News RSS: {e}")
                return []
    
    # Sort by published date (most recent first)
    all_articles.sort(
        key=lambda x: _parse_date(x.get("published_at", "")) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True
    )
    
    # Limit to top 20 most relevant
    all_articles = all_articles[:20]
    
    return all_articles


def fetch_linkedin_data(linkedin_url: str) -> Dict:
    """
    Fetch LinkedIn company data.
    
    Note: LinkedIn API requires OAuth and is complex. This is a placeholder
    for future implementation. For now, returns basic structure.
    
    Args:
        linkedin_url: LinkedIn company page URL
    
    Returns:
        Dict with LinkedIn data (currently minimal)
    """
    # TODO: Implement LinkedIn API integration when credentials are available
    # For now, return empty structure
    return {
        "linkedin_url": linkedin_url,
        "follower_count": None,
        "employee_count": None,
        "description": None,
        "recent_posts": [],
        "api_source": "none"
    }


def fetch_github_data(company_name: str, github_url: Optional[str] = None) -> Dict:
    """
    Fetch GitHub organization data using GitHub REST API.
    
    Args:
        company_name: Company name to search for
        github_url: Optional GitHub organization URL
    
    Returns:
        Dict with GitHub data
    """
    github_data = {
        "organization": None,
        "repos_count": 0,
        "stars_total": 0,
        "recent_activity": [],
        "top_repos": [],
        "api_source": "github_rest"
    }
    
    # GitHub API doesn't require auth for public data, but has rate limits
    github_token = os.getenv("GITHUB_TOKEN", "")
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": USER_AGENT
    }
    if github_token:
        headers["Authorization"] = f"token {github_token}"
    
    try:
        # If github_url provided, extract org name
        org_name = None
        if github_url:
            # Extract org name from URL like https://github.com/companyname
            match = re.search(r"github\.com/([^/]+)", github_url)
            if match:
                org_name = match.group(1)
        
        # If no org name, try searching by company name
        if not org_name:
            # Try searching for organization
            search_url = f"https://api.github.com/search/users?q={quote_plus(company_name)}+type:org&per_page=1"
            search_response = requests.get(search_url, headers=headers, timeout=HTTP_TIMEOUT)
            if search_response.status_code == 200:
                search_data = search_response.json()
                if search_data.get("items"):
                    org_name = search_data["items"][0].get("login")
        
        if org_name:
            # Get organization details
            org_url = f"https://api.github.com/orgs/{org_name}"
            org_response = requests.get(org_url, headers=headers, timeout=HTTP_TIMEOUT)
            if org_response.status_code == 200:
                org_data = org_response.json()
                github_data["organization"] = org_name
                github_data["repos_count"] = org_data.get("public_repos", 0)
                
                # Get repositories
                repos_url = f"https://api.github.com/orgs/{org_name}/repos?sort=updated&per_page=10"
                repos_response = requests.get(repos_url, headers=headers, timeout=HTTP_TIMEOUT)
                if repos_response.status_code == 200:
                    repos_data = repos_response.json()
                    github_data["top_repos"] = [
                        {
                            "name": repo.get("name", ""),
                            "stars": repo.get("stargazers_count", 0),
                            "url": repo.get("html_url", ""),
                            "description": repo.get("description", "")
                        }
                        for repo in repos_data[:5]
                    ]
                    github_data["stars_total"] = sum(repo.get("stargazers_count", 0) for repo in repos_data)
    except Exception as e:
        print(f"[WARN] GitHub API request failed: {e}")
    
    return github_data
