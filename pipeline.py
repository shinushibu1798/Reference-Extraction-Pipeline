from typing import Optional, Any
import pandas as pd
from pdf_utils import extract_text_from_pdf, split_into_references
from dspy_models import parse_reference_with_dspy, infer_work_type, pick_best_match
from openalex_client import fetch_openalex_candidates, extract_authors_from_work


def process_single_reference(ref_text: str) -> dict[str, Any]:
    """Process one reference through the full DSPy + OpenAlex pipeline."""
    print("\nProcessing:", ref_text[:150].replace("\n", " "), "...")

    # 1) Parse reference with DSPy
    print("  -> Parsing...")
    parsed = parse_reference_with_dspy(ref_text)
    paper_title = parsed.get("paper_title", "")
    year = parsed.get("year")
    authors = parsed.get("authors", []) or []
    emails = parsed.get("emails", []) or []
    print(f"  Title: {paper_title!r}, Year: {year}, Authors: {authors}")

    # 2) Infer work type (for DSPy matching context / reporting)
    print("  -> Inferring work type...")
    work_type = infer_work_type(ref_text) or "unknown"
    print(f"  Work type: {work_type}")

    # 3) Fetch candidates from OpenAlex
    print("  -> Searching OpenAlex...")
    first_author = authors[0] if authors else None
    try:
        candidates = fetch_openalex_candidates(
            paper_title, year, first_author, work_type=work_type
        )
    except Exception as e:
        print(f"  OpenAlex error: {e}")
        candidates = []

    print(f"  -> {len(candidates)} raw candidates from OpenAlex")

    # 4) Let DSPy filter + choose the best match (if any)
    best_work = None
    match_rationale = ""
    if candidates:
        print("  -> Choosing best match with DSPy...")
        best_work, match_rationale = pick_best_match(
            ref_text, paper_title, year, authors, candidates, work_type
        )
    else:
        print("  -> No candidates to choose from.")

    # 5) Extract author info (OpenAlex or fallback)
    first_author_info = {"name": "", "affiliations": [], "emails": emails}
    last_author_info = {"name": "", "affiliations": [], "emails": []}
    notes_parts: list[str] = []

    if best_work:
        matched_title = best_work.get("title", "") or ""
        print(f"  Matched OpenAlex work: {matched_title!r}")
        fa, la = extract_authors_from_work(best_work)
        first_author_info = {
            "name": fa.get("name", ""),
            "affiliations": fa.get("affiliations", []),
            "emails": emails,  # attach any emails from the reference
        }
        last_author_info = {
            "name": la.get("name", ""),
            "affiliations": la.get("affiliations", []),
            "emails": [],
        }
        notes_parts.append(f"Matched to {best_work.get('id', '')}")
    else:
        notes_parts.append("DSPy could not confidently match this reference to any OpenAlex work.")

    if match_rationale:
        notes_parts.append(f"DSPy rationale: {match_rationale}")

    # Fallbacks so rows are never "empty"
    if not paper_title:
        paper_title = ref_text[:120].replace("\n", " ")
        if len(ref_text) > 120:
            paper_title += "..."

    if not first_author_info["name"] and authors:
        first_author_info["name"] = authors[0]
    if not last_author_info["name"] and len(authors) > 1:
        last_author_info["name"] = authors[-1]

    notes = " | ".join([p for p in notes_parts if p])

    return {
        "paper_title": paper_title,
        "year": year,
        "first_author_name": first_author_info["name"],
        "first_author_affiliations": "; ".join(first_author_info["affiliations"]),
        "first_author_emails": "; ".join(first_author_info["emails"]),
        "last_author_name": last_author_info["name"],
        "last_author_affiliations": "; ".join(last_author_info["affiliations"]),
        "last_author_emails": "; ".join(last_author_info["emails"]),
        "reference_raw": ref_text,
        "notes": notes,
    }


def process_pdf_to_excel(pdf_path: str, output_path: str, max_refs: Optional[int] = None) -> None:
    """Full pipeline: PDF -> references -> DSPy + OpenAlex -> Excel."""
    print(f"Reading PDF: {pdf_path}")
    raw_text = extract_text_from_pdf(pdf_path)

    print("Splitting into references...")
    references = split_into_references(raw_text)
    print(f"Found {len(references)} references.")

    if max_refs:
        references = references[:max_refs]
        print(f"Limiting to {max_refs} references.")

    records: list[dict[str, Any]] = []
    for idx, ref in enumerate(references, 1):
        print(f"\n=== Reference {idx}/{len(references)} ===")
        try:
            records.append(process_single_reference(ref))
        except Exception as e:
            print(f"Error: {e}")
            records.append({
                "paper_title": ref[:120].replace("\n", " ") + ("..." if len(ref) > 120 else ""),
                "year": None,
                "first_author_name": "",
                "first_author_affiliations": "",
                "first_author_emails": "",
                "last_author_name": "",
                "last_author_affiliations": "",
                "last_author_emails": "",
                "reference_raw": ref,
                "notes": f"Error during processing: {e}",
            })

    print("\nWriting Excel...")
    df = pd.DataFrame(records).fillna("")
    df.to_excel(output_path, index=False)
    print(f"Done. Saved to {output_path}")
