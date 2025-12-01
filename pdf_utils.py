import re
import pdfplumber

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from all pages of a PDF."""
    with pdfplumber.open(pdf_path) as pdf:
        pages_text = [page.extract_text() or "" for page in pdf.pages]
    return "\n".join(pages_text)


def split_into_references(raw_text: str) -> list[str]:
    """
    Split bibliography into individual references.
    Tuned for style: [Hill '79] ...
    """
    lines = raw_text.splitlines()
    cleaned_lines = [
        line for line in lines
        if not line.strip().startswith("Bibliography")
        and not line.strip().startswith("———")
    ]
    cleaned_text = "\n".join(cleaned_lines)

    # Split on lines starting with '['
    parts = re.split(r'\n(?=\[)', cleaned_text)
    refs = [p.strip() for p in parts if p.strip().startswith("[") and len(p.strip()) > 30]
    return refs
