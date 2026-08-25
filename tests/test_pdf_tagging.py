import tempfile
import unittest
from pathlib import Path

import pymupdf

from udap.pdf_inspection import inspect_pdf
from udap.pdf_tagging import apply_minimal_structure_tree


class PdfTaggingTest(unittest.TestCase):
    def test_apply_minimal_structure_tree_marks_pdf_as_tagged(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            path = Path(tmp.name)

        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Tagged smoke")
        doc.set_metadata({"title": "Tagged smoke"})
        doc.xref_set_key(doc.pdf_catalog(), "Lang", "(en-AU)")
        doc.save(path)
        doc.close()

        apply_minimal_structure_tree(
            path,
            {
                "mappings": [
                    {
                        "element_id": "1",
                        "element_type": "heading",
                        "pdf_role": "H1",
                        "text_preview": "Tagged smoke",
                    }
                ]
            },
        )

        inspection = inspect_pdf(path)

        self.assertTrue(inspection.has_struct_tree)
        self.assertTrue(inspection.mark_info_marked)
        self.assertTrue(inspection.is_tagged)


if __name__ == "__main__":
    unittest.main()
