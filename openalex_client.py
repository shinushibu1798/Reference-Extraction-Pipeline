import requests
import re
from typing import List, Dict, Any, Optional, Tuple
from config import OPENALEX_BASE_URL, OPENALEX_MAILTO

def fetch_openalex_candidates(title: str,
                              year: Optional[int] = None,
                              first_author: Optional[str] = None,
                              work_type: Optional[str] = None,
                              per_page: int = 10) -> list[dict[str, Any]]:
    """
    Two-stage OpenAlex search:
      Stage 1: precise title.search (and optional type) to find exact works.
      Stage 2: fallback to broader search if stage 1 returns nothing.
    """
    if not title:
        return []

    clean_title = re.sub(r'[^\w\s]', ' ', title)
    clean_title = ' '.join(clean_title.split())

    base_url = f"{OPENALEX_BASE_URL}/works"

    # ---------- Stage 1: title.search + optional type ----------
    filter_parts = [f"title.search:{clean_title}"]

    if work_type:
        filter_parts.append(f"type:{work_type}")   # e.g. 'book', 'journal-article'

    params1 = {
        "mailto": OPENALEX_MAILTO,
        "per_page": per_page,
        "sort": "cited_by_count:desc",
        "filter": ",".join(filter_parts),
    }

    print("  OpenAlex Stage 1 query:", params1)
    try:
        resp1 = requests.get(base_url, params=params1, timeout=30)
        resp1.raise_for_status()
        results1 = resp1.json().get("results", []) or []
    except Exception as e:
        print("  Stage 1 OpenAlex error:", e)
        results1 = []

    if results1:
        return results1

    # ---------- Stage 2: broader search with year window ----------
    search_query = clean_title
    if first_author:
        last_name = first_author.split()[-1]
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

    print("  OpenAlex Stage 2 query:", params2)
    try:
        resp2 = requests.get(base_url, params=params2, timeout=30)
        resp2.raise_for_status()
        results2 = resp2.json().get("results", []) or []
    except Exception as e:
        print("  Stage 2 OpenAlex error:", e)
        results2 = []

    return results2


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
