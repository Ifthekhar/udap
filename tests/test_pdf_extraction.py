import tempfile
import unittest
from pathlib import Path

import pymupdf

from udap.extractors import load_pdf
from udap.models import ElementType


class PdfExtractionTest(unittest.TestCase):
    def test_load_pdf_extracts_metadata_headings_links_and_layout(self):
        pdf_path = _build_pdf(
            title="Extraction Sample",
            language="en-AU",
            rows=[
                ("Annual Report 2026", 22, 72, 72),
                ("Visit the project website", 11, 72, 120),
                ("Body paragraph for the accessibility analysis.", 11, 72, 160),
            ],
            link_rect=(72, 110, 220, 132),
        )

        document = load_pdf(pdf_path)

        self.assertEqual(document.title, "Extraction Sample")
        self.assertEqual(document.language, "en-AU")
        self.assertIsNotNone(document.pdf)
        self.assertGreaterEqual(document.pdf.text_block_count, 3)
        self.assertEqual(document.pdf.link_count, 1)
        self.assertGreaterEqual(document.pdf.heading_candidate_count, 1)
        self.assertTrue(any(element.type == ElementType.HEADING for element in document.elements))
        self.assertTrue(any(element.type == ElementType.LINK for element in document.elements))

    def test_load_pdf_marks_multi_column_pages_as_lower_confidence(self):
        rows = []
        for index in range(4):
            rows.append((f"Left column {index}", 11, 72, 72 + index * 28))
            rows.append((f"Right column {index}", 11, 330, 72 + index * 28))

        pdf_path = _build_pdf(title="Columns", language="en-AU", rows=rows)

        document = load_pdf(pdf_path)

        self.assertIsNotNone(document.pdf)
        self.assertIn(1, document.pdf.pages_with_multiple_columns)


def _build_pdf(
    *,
    title: str,
    language: str,
    rows: list[tuple[str, int, int, int]],
    link_rect: tuple[int, int, int, int] | None = None,
) -> Path:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        pass
    path = Path(tmp.name)

    doc = pymupdf.open()
    page = doc.new_page()

    for text, size, x, y in rows:
        page.insert_text((x, y), text, fontsize=size)

    if link_rect is not None:
        page.insert_link(
            {
                "kind": pymupdf.LINK_URI,
                "from": pymupdf.Rect(*link_rect),
                "uri": "https://example.com/project",
            }
        )

    doc.set_metadata({"title": title})
    catalog = doc.pdf_catalog()
    doc.xref_set_key(catalog, "Lang", f"({language})")
    doc.save(path)
    doc.close()
    return path


if __name__ == "__main__":
    unittest.main()
