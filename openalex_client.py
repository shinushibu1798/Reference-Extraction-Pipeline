import requests
import re
from typing import List, Dict, Any, Optional, Tuple
from config import OPENALEX_BASE_URL, OPENALEX_MAILTO

def fetch_openalex_candidates(title: str,
                              year: Optional[int] = None,
                              first_author: Optional[str] = None,
                              work_type: Optional[str] = None,
                              per_page: int = 10) -> List[Dict[str, Any]]:
    """
    Two-stage OpenAlex search with robust fallbacks:

      Stage 1a: precise title.search + optional type
      Stage 1b: title.search only (no type) if 1a returns nothing

      Stage 2a: broader 'search=' with year window
      Stage 2b: 'search=' without year filter if 2a returns nothing
    """
    if not title:
        return []

    def normalize_last_name(name: str) -> str:
        cleaned = re.sub(r"[^A-Za-z\s'-]", " ", name or "")
        tokens = [t for t in cleaned.split() if t]
        return tokens[-1] if tokens else ""

    clean_title = re.sub(r"[^\w\s]", " ", title)
    clean_title = " ".join(clean_title.split())

    base_url = f"{OPENALEX_BASE_URL}/works"

    # ---------- Stage 1a: title.search + type (if given) ----------
    filter_parts = [f"title.search:{clean_title}"]
    if work_type:
        filter_parts.append(f"type:{work_type}")  # e.g. 'book', 'journal-article'

    params1 = {
        "mailto": OPENALEX_MAILTO,
        "per_page": per_page,
        "sort": "cited_by_count:desc",
        "filter": ",".join(filter_parts),
    }

    print("  OpenAlex Stage 1a query:", params1)
    try:
        resp1 = requests.get(base_url, params=params1, timeout=30)
        resp1.raise_for_status()
        results1 = resp1.json().get("results", []) or []
    except Exception as e:
        print("  Stage 1a OpenAlex error:", e)
        results1 = []

    # If we got hits, we're done
    if results1:
        return results1

    # ---------- Stage 1b: title.search only (no type filter) ----------
    if work_type:
        params1b = params1.copy()
        # rebuild filter without type
        params1b["filter"] = f"title.search:{clean_title}"
        print("  OpenAlex Stage 1b query (no type):", params1b)
        try:
            resp1b = requests.get(base_url, params=params1b, timeout=30)
            resp1b.raise_for_status()
            results1b = resp1b.json().get("results", []) or []
        except Exception as e:
            print("  Stage 1b OpenAlex error:", e)
            results1b = []

        if results1b:
            return results1b

    # ---------- Stage 2a: broader 'search=' with year window ----------
    search_query = clean_title
    if first_author:
        # still append only last token, but this is just a hint
        last_name = normalize_last_name(first_author)
        search_query = f"{clean_title} {last_name}"

    params2 = {
        "search": search_query,
        "per_page": per_page,
        "mailto": OPENALEX_MAILTO,
    }

    if year:
        params2["filter"] = (
            f"from_publication_date:{year-3}-01-01,"
            f"to_publication_date:{year+3}-12-31"
        )

    print("  OpenAlex Stage 2a query:", params2)
    try:
        resp2 = requests.get(base_url, params=params2, timeout=30)
        resp2.raise_for_status()
        results2 = resp2.json().get("results", []) or []
    except Exception as e:
        print("  Stage 2a OpenAlex error:", e)
        results2 = []

    if results2:
        return results2

    # ---------- Stage 2b: 'search=' with NO year filter ----------
    if year and "filter" in params2:
        params2b = params2.copy()
        params2b.pop("filter", None)
        print("  OpenAlex Stage 2b query (no year filter):", params2b)
        try:
            resp2b = requests.get(base_url, params=params2b, timeout=30)
            resp2b.raise_for_status()
            results2b = resp2b.json().get("results", []) or []
        except Exception as e:
            print("  Stage 2b OpenAlex error:", e)
            results2b = []

        return results2b

    # If absolutely nothing worked, return empty list
    return []



def extract_authors_from_work(work: dict[str, Any]) -> tuple[dict, dict]:
    """Extract first and last author info from an OpenAlex work."""
    authorships = work.get("authorships", []) or []
    if not authorships:
        return {}, {}

    def summarize(authorship):
        author = authorship.get("author", {}) or {}
        institutions = authorship.get("institutions", []) or []
        return {
            "name": author.get("display_name", ""),
            "openalex_id": author.get("id", ""),
            "affiliations": [
                i.get("display_name", "")
                for i in institutions
                if i.get("display_name")
            ],
        }

    return summarize(authorships[0]), summarize(authorships[-1])