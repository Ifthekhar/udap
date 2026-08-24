"""Developer CLI for running the analysis pipeline against local files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .extractors import MissingExtractorDependencyError, UnsupportedDocumentError, load_document
from .pipeline import analyse_document, build_validation_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyse a DOCX or PDF for MVP accessibility issues.")
    parser.add_argument("path", help="Path to a DOCX or PDF file.")
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    args = parser.parse_args()

    try:
        document = load_document(Path(args.path))
        result = analyse_document(document)
    except (MissingExtractorDependencyError, UnsupportedDocumentError) as exc:
        parser.error(str(exc))

    indent = 2 if args.pretty else None
    print(json.dumps(build_validation_report(result), indent=indent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
