import tempfile
import unittest
from pathlib import Path

from demo.create_demo_pdfs import create_demo_pdfs
from demo.rehearse_demo import rehearse_demo
from udap.extractors import load_pdf
from udap.pipeline import analyse_document


class DemoRehearsalTest(unittest.TestCase):
    def test_demo_samples_generate_expected_analysis_mix(self):
        with tempfile.TemporaryDirectory() as tmp:
            samples = create_demo_pdfs(tmp)
            by_name = {path.name: path for path in samples}

            foundation = analyse_document(load_pdf(by_name["udap-demo-foundation.pdf"]))
            needs_review = analyse_document(load_pdf(by_name["udap-demo-needs-review.pdf"]))

        self.assertEqual(foundation.counts_by_issue_type(), {"untagged_pdf": 1})
        self.assertEqual(
            needs_review.counts_by_issue_type(),
            {
                "untagged_pdf": 1,
                "missing_document_title": 1,
                "missing_document_language": 1,
                "missing_image_alt_text": 1,
                "weak_link_text": 1,
            },
        )

    def test_rehearsal_runs_upload_review_generate_download_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = rehearse_demo(Path(tmp))

        self.assertEqual(result["initial_issue_count"], 5)
        self.assertEqual(result["suggestion_count"], 5)
        self.assertEqual(result["final_status"], "output_generated")
        self.assertEqual(result["pdf_structure_status"], "passed")
        self.assertEqual(result["reading_order_status"], "passed")
        self.assertIn("udap-demo-needs-review_accessible.pdf", result["artifact_filenames"])
        self.assertIn("udap-demo-needs-review_accessibility_report.json", result["artifact_filenames"])
        self.assertGreaterEqual(result["remediation_summary"]["fixed_issue_count"], 4)


if __name__ == "__main__":
    unittest.main()
