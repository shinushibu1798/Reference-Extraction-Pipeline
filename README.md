# Reference Extraction Pipeline

Parse references from a PDF, match them to OpenAlex (with Semantic Scholar fallback), and export structured author metadata to Excel.

## What it extracts
- Paper title and publication year
- First/last author names, affiliations, and emails (from OpenAlex, Semantic Scholar, or parsed text fallbacks)
- Raw reference text and processing notes

## Project layout
```
config.py                 # API endpoints, model config, keys
dspy_models.py            # DSPy signatures + parsing helpers
openalex_client.py        # OpenAlex search + author extraction
semantic_scholar_client.py# Semantic Scholar fallback search
pdf_utils.py              # PDF text extraction and reference splitting
pipeline.py               # End-to-end processing logic
main.py                   # CLI entrypoint
References.pdf            # Sample input
output.xlsx               # Sample output
```

## Setup
1) Create/activate a venv
```bash
python -m venv .venv
.\.venv\Scripts\activate
```
2) Install dependencies
```bash
pip install -r requirements.txt
```
3) Configure keys in `config.py`
- `HUGGINGFACEHUB_API_TOKEN` (required for LLM)
- `OPENALEX_MAILTO` (your contact email)
- `SEMANTIC_SCHOLAR_API_KEY` (recommended to avoid 429s; fallback works without but may throttle)

## Run
```bash
python main.py --pdf References.pdf --out output.xlsx
```
Limit processed references (useful for testing):
```bash
python main.py --pdf References.pdf --out output.xlsx --max_refs 10
```

## How it works
1) `pdf_utils.py` extracts text and splits it into individual references.  
2) `dspy_models.py` uses the LLM to pull title/year/authors/emails and structured author hints (affiliations/emails).  
3) `openalex_client.py` searches OpenAlex (title/type/year + fallbacks) and extracts author names/affiliations when matched.  
4) If OpenAlex fails, `semantic_scholar_client.py` queries Semantic Scholar (with API key support) to fill author names/affiliations.  
5) `pipeline.py` reconciles data, fills missing fields with DSPy regex/heuristics, and writes rows to Excel with notes.

## Output columns
- `paper_title`, `year`
- `first_author_name`, `first_author_affiliations`, `first_author_emails`
- `last_author_name`, `last_author_affiliations`, `last_author_emails`
- `reference_raw`, `notes`

## Tips for better results
- Use `SEMANTIC_SCHOLAR_API_KEY` to reduce rate limits; without it, expect occasional skips.
- Use smaller `--max_refs` while iterating.
- Clean PDFs (good OCR) yield better title/author parsing and matches.
