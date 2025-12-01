import re
import requests
import time
from typing import Any, Dict, List, Optional, Tuple
from config import (
    SEMANTIC_SCHOLAR_BASE_URL,
    SEMANTIC_SCHOLAR_TIMEOUT,
    SEMANTIC_SCHOLAR_API_KEY,
)


def _normalize_title(title: str) -> str:
    cleaned = re.sub(r"[^\w\s]", " ", title or "")
    return " ".join(cleaned.split())


def _s2_get(url: str, params: Dict[str, Any], max_retries: int = 2, base_delay: float = 0.5) -> Dict[str, Any]:
    """Call Semantic Scholar with retry/backoff on 429s."""
    headers = {"User-Agent": "reference-extractor/1.0"}
    if SEMANTIC_SCHOLAR_API_KEY and "SET_YOUR_S2_KEY_HERE" not in SEMANTIC_SCHOLAR_API_KEY:
        headers["x-api-key"] = SEMANTIC_SCHOLAR_API_KEY
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, params=params, timeout=SEMANTIC_SCHOLAR_TIMEOUT, headers=headers)
            if resp.status_code == 429 and attempt < max_retries:
                wait = base_delay * attempt
                print(f"  Semantic Scholar rate limit (429), retrying in {wait:.1f}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json() or {}
        except Exception as e:
            if getattr(e, "response", None) is not None and getattr(e.response, "status_code", None) == 429:
                if attempt >= max_retries:
                    print("  Semantic Scholar rate limit (429) final attempt; skipping.")
                    return {"rate_limited": True}
            if attempt >= max_retries:
                raise
            time.sleep(base_delay * attempt)
    return {}


def fetch_semantic_scholar_candidates(title: str,
                                      year: Optional[int] = None,
                                      per_page: int = 5) -> List[Dict[str, Any]]:
    """Search Semantic Scholar by title (+/- year) to fetch papers with author affiliations."""
    if not title:
        return []

    base_url = f"{SEMANTIC_SCHOLAR_BASE_URL}/paper/search"
    clean_title = _normalize_title(title)

    params = {
        "query": clean_title,
        "limit": per_page,
        "fields": "title,year,authors.name,authors.affiliations",
    }
    if year:
        params["year"] = year

    print("  Semantic Scholar query:", params)
    base_delay = 0.5 if SEMANTIC_SCHOLAR_API_KEY else 2.0

    try:
        data = _s2_get(base_url, params=params, base_delay=base_delay)
        if data.get("rate_limited"):
            return []
        results = data.get("data", []) or []
    except Exception as e:
        print("  Semantic Scholar error:", e)
        results = []

    if not results and year:
        params.pop("year", None)
        print("  Semantic Scholar fallback query (no year):", params)
        try:
            data = _s2_get(base_url, params=params, base_delay=base_delay)
            if data.get("rate_limited"):
                return []
            results = data.get("data", []) or []
        except Exception as e:
            print("  Semantic Scholar fallback error:", e)
            results = []

    return results


def extract_authors_from_s2_paper(paper: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Extract first/last author summaries from a Semantic Scholar paper result."""
    authors = paper.get("authors", []) or []
    if not authors:
        return {}, {}

    def summarize(author: Dict[str, Any]) -> Dict[str, Any]:
        affs = author.get("affiliations") or []
        return {
            "name": author.get("name", "") or "",
            "affiliations": [a for a in affs if a],
        }

    return summarize(authors[0]), summarize(authors[-1])
