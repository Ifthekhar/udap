import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from udap.pdf_validation import validate_pdf_ua


class PdfValidationTest(unittest.TestCase):
    @patch("udap.pdf_validation.shutil.which", return_value=None)
    def test_validate_pdf_ua_reports_unavailable_without_verapdf(self, _which):
        result = validate_pdf_ua(Path("missing.pdf"))

        self.assertEqual(result.status, "unavailable")
        self.assertIsNone(result.passed)
        self.assertIn("not installed", result.details)

    @patch("udap.pdf_validation.shutil.which", return_value="/usr/local/bin/verapdf")
    @patch("udap.pdf_validation.subprocess.run")
    def test_validate_pdf_ua_parses_json_result(self, run, _which):
        run.return_value = Mock(
            returncode=0,
            stdout='{"jobs":[{"validationResult":{"isCompliant":true}}]}',
            stderr="",
        )

        result = validate_pdf_ua(Path("sample.pdf"))

        self.assertEqual(result.status, "completed")
        self.assertTrue(result.passed)


if __name__ == "__main__":
    unittest.main()
