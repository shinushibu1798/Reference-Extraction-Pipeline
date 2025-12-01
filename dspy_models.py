import dspy
import re
import json

from typing import List, Dict, Any, Optional, Tuple
#from config import MODEL_NAME, API_BASE ## uncomment if using ollama local server
from config import MODEL_NAME, HUGGINGFACEHUB_API_TOKEN as HF_TOKEN

# ===================== DSPY INITIALIZATION =====================


lm = dspy.LM(
    model=MODEL_NAME,
    #api_base=API_BASE, ## uncomment if using ollama local server
    api_key=HF_TOKEN,
    temperature=0.0,
    max_tokens=512,
)

dspy.configure(lm=lm)

# ===================== DSPY SIGNATURES =====================

class ParseReference(dspy.Signature):
    """Parse a bibliography reference into structured fields."""
    ref_text = dspy.InputField(desc="One bibliographic reference as text.")
    paper_title = dspy.OutputField(desc="Title of the work.")
    year = dspy.OutputField(desc="Four-digit year or 'null' if unsure.")
    authors_json = dspy.OutputField(desc='JSON array of author names, e.g. ["A. Author"].')
    emails_json = dspy.OutputField(desc="JSON array of emails in the reference (empty if none).")


class InferWorkType(dspy.Signature):
    """Infer OpenAlex work type from a reference."""
    ref_text = dspy.InputField(desc="One bibliographic reference as text.")
    work_type = dspy.OutputField(
        desc='One of: "book", "journal-article", "proceedings-article", "book-chapter", "unknown".'
    )


class ChooseOpenAlexMatch(dspy.Signature):
    """
    Given a reference and a list of OpenAlex candidates, choose the best match.

    Inputs:
    - ref_text: the raw reference from the PDF.
    - parsed_title: title extracted from the reference (may be imperfect).
    - parsed_year: year extracted from the reference, as a string or "null".
    - parsed_authors_json: JSON array of author names from the reference.
    - inferred_work_type: DSPy-inferred OpenAlex work type (or "unknown"/null).
    - candidates_json: JSON array of candidate works from OpenAlex, each with:
        - id (OpenAlex work id)
        - title
        - publication_year
        - type
        - authors: list of author display_names.

    Task:
    1) For each candidate, compare title, authors, year, and type.
    2) If a few things match but not all, explain the reasoning in the rationale and choose the candidate that fits best.  
    3) There will be lots of discrepancies; evenso, try to pick an approximate match.  
    4) If the title is an approximate match but year/authors/type are way off, you should still choose that candidate.

    Output:
    - chosen_id: OpenAlex work id of the chosen candidate, or "none".
    - rationale: reasoning explaining the choice.
    """

    ref_text = dspy.InputField()
    parsed_title = dspy.InputField()
    parsed_year = dspy.InputField()
    parsed_authors_json = dspy.InputField()
    inferred_work_type = dspy.InputField()
    candidates_json = dspy.InputField()

    chosen_id = dspy.OutputField(desc="OpenAlex work id or 'none'.")
    rationale = dspy.OutputField(desc="Reasoning for the choice (for debugging).")


# ===================== DSPY MODULES =====================

parse_ref_module = dspy.Predict(ParseReference)
infer_type_module = dspy.Predict(InferWorkType)
choose_match_module = dspy.Predict(ChooseOpenAlexMatch)

# ===================== DSPY HELPERS =====================

def parse_reference_with_dspy(ref_text: str) -> dict[str, Any]:
    """Parse a reference using DSPy."""
    pred = parse_ref_module(ref_text=ref_text)

    paper_title = (pred.paper_title or "").strip()
    year_raw = (pred.year or "").strip()

    # Parse JSON fields
    authors: list[str] = []
    emails: list[str] = []
    for field, target in [(pred.authors_json, authors), (pred.emails_json, emails)]:
        if field:
            try:
                parsed = json.loads(field)
                if isinstance(parsed, list):
                    target.extend(parsed)
            except Exception:
                pass

    # Extract year
    year: Optional[int] = None
    if year_raw and year_raw.lower() != "null":
        m = re.search(r"\b(1[5-9]\d{2}|20\d{2})\b", year_raw)
        if m:
            year = int(m.group(1))

    return {"paper_title": paper_title, "year": year, "authors": authors, "emails": emails}


def infer_work_type(ref_text: str) -> Optional[str]:
    """Infer work type using DSPy."""
    pred = infer_type_module(ref_text=ref_text)
    raw = (pred.work_type or "").strip().lower()

    mapping = {
        "book": "book", "books": "book",
        "journal-article": "journal-article", "journal article": "journal-article",
        "article": "journal-article", "paper": "journal-article",
        "proceedings-article": "proceedings-article", "conference paper": "proceedings-article",
        "book-chapter": "book-chapter", "chapter": "book-chapter",
    }
    if raw in mapping:
        return mapping[raw]
    compact = raw.replace(" ", "-")
    return mapping.get(compact)


def pick_best_match(ref_text: str,
                    parsed_title: str,
                    parsed_year: Optional[int],
                    parsed_authors: list[str],
                    candidates: list[dict[str, Any]],
                    work_type: Optional[str]) -> tuple[Optional[dict[str, Any]], str]:
    """
    Use DSPy to filter and choose the best OpenAlex candidate (or none).
    Returns (best_work_dict_or_None, rationale_string).
    """
    if not candidates:
        return None, ""

    simple = []
    for c in candidates:
        auth_names = [
            (a.get("author") or {}).get("display_name", "")
            for a in (c.get("authorships") or [])
        ]
        simple.append({
            "id": c.get("id", ""),
            "title": c.get("title", ""),
            "publication_year": c.get("publication_year"),
            "type": c.get("type", ""),
            "authors": auth_names,
        })

    out = choose_match_module(
        ref_text=ref_text,
        parsed_title=parsed_title,
        parsed_year=str(parsed_year) if parsed_year else "null",
        parsed_authors_json=json.dumps(parsed_authors, ensure_ascii=False),
        inferred_work_type=work_type or "unknown",
        candidates_json=json.dumps(simple, ensure_ascii=False),
    )

    chosen_id = (out.chosen_id or "").strip()
    rationale = (out.rationale or "").strip()
    print("  DSPy rationale:", rationale)

    if not chosen_id or chosen_id.lower() == "none":
        return None, rationale

    best = next((c for c in candidates if c.get("id") == chosen_id), None)
    return best, rationale
