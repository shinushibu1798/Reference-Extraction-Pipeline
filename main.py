import argparse
from pipeline import process_pdf_to_excel

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract first/last author affiliation + contact info from a references PDF using DSPy + OpenAlex."
    )
    parser.add_argument(
        "--pdf",
        required=True,
        help="Path to the input PDF containing references.",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Path to the output Excel file (.xlsx).",
    )
    parser.add_argument(
        "--max_refs",
        type=int,
        default=None,
        help="Optional limit on number of references to process (for debugging).",
    )

    args = parser.parse_args()

    process_pdf_to_excel(
        pdf_path=args.pdf,
        output_path=args.out,
        max_refs=args.max_refs,
    )


if __name__ == "__main__":
    main()
