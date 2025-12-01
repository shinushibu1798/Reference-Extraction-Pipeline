import pandas as pd
from typing import Optional, Any
from pdf_utils import extract_text_from_pdf, split_into_references
from dspy_models import parse_reference_with_dspy, infer_work_type, pick_best_match
from openalex_client import fetch_openalex_candidates, extract_authors_from_work
from semantic_scholar_client import (
    fetch_semantic_scholar_candidates,
    extract_authors_from_s2_paper,
)


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
    parsed_first_affs = parsed.get("first_affiliations", []) or []
    parsed_last_affs = parsed.get("last_affiliations", []) or []
    parsed_first_emails = parsed.get("first_author_emails", []) or []
    parsed_last_emails = parsed.get("last_author_emails", []) or []
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
    last_author_info = {"name": "", "affiliations": [], "emails": parsed_last_emails}
    notes_parts: list[str] = []

    if best_work:
        matched_title = best_work.get("title", "") or ""
        print(f"  Matched OpenAlex work: {matched_title!r}")
        fa, la = extract_authors_from_work(best_work)
        first_author_info = {
            "name": fa.get("name", ""),
            "affiliations": fa.get("affiliations", []),
            "emails": parsed_first_emails or emails,  # attach emails seen in the reference
        }
        last_author_info = {
            "name": la.get("name", ""),
            "affiliations": la.get("affiliations", []),
            "emails": parsed_last_emails,
        }
        notes_parts.append(f"Matched to {best_work.get('id', '')}")
    else:
        # Use DSPy-derived affiliations/emails as fallbacks when OpenAlex doesn't match
        first_author_info["affiliations"] = parsed_first_affs
        last_author_info["affiliations"] = parsed_last_affs
        if parsed_first_emails:
            first_author_info["emails"] = parsed_first_emails
        if parsed_last_emails:
            last_author_info["emails"] = parsed_last_emails
        notes_parts.append("DSPy could not confidently match this reference to any OpenAlex work.")

    # Secondary lookup: Semantic Scholar if no OpenAlex match
    if not best_work:
        print("  -> Semantic Scholar fallback search...")
        s2_candidates = []
        try:
            s2_candidates = fetch_semantic_scholar_candidates(
                paper_title, year
            )
        except Exception as e:
            print(f"  Semantic Scholar error: {e}")
            notes_parts.append(f"Semantic Scholar error: {e}")

        if s2_candidates:
            s2 = s2_candidates[0]
            fa_s2, la_s2 = extract_authors_from_s2_paper(s2)
            if fa_s2.get("name"):
                first_author_info["name"] = first_author_info["name"] or fa_s2["name"]
            if la_s2.get("name"):
                last_author_info["name"] = last_author_info["name"] or la_s2["name"]
            if fa_s2.get("affiliations"):
                first_author_info["affiliations"] = first_author_info["affiliations"] or fa_s2["affiliations"]
            if la_s2.get("affiliations"):
                last_author_info["affiliations"] = last_author_info["affiliations"] or la_s2["affiliations"]
            notes_parts.append("Filled from Semantic Scholar fallback.")
            print("  Semantic Scholar fallback filled author info.")
        else:
            notes_parts.append("Semantic Scholar did not return matches (or was rate limited).")

    if not last_author_info["emails"] and emails:
        # If we saw emails but could not map to last author, at least surface them
        last_author_info["emails"] = emails

    # Final fallbacks to avoid empty columns
    if not first_author_info["name"] and authors:
        first_author_info["name"] = authors[0]
    if not last_author_info["name"] and len(authors) > 1:
        last_author_info["name"] = authors[-1]

    if not first_author_info["affiliations"] and parsed_first_affs:
        first_author_info["affiliations"] = parsed_first_affs
    if not last_author_info["affiliations"] and parsed_last_affs:
        last_author_info["affiliations"] = parsed_last_affs

    if not first_author_info["emails"]:
        first_author_info["emails"] = parsed_first_emails or emails
    if not last_author_info["emails"] and parsed_last_emails:
        last_author_info["emails"] = parsed_last_emails

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
