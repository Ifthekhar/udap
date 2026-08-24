import unittest

from udap.models import DocumentElement, DocumentModel, ElementType, PdfInspection, SourceLocation
from udap.pipeline import analyse_document, build_validation_report


class RuleEngineTest(unittest.TestCase):
    def test_missing_title_and_language_are_reported(self):
        document = DocumentModel(
            original_filename="sample.pdf",
            source_format="pdf",
            elements=[DocumentElement(type=ElementType.PARAGRAPH, text="Annual report 2026")],
        )

        result = analyse_document(document)
        issue_types = {issue.issue_type for issue in result.issues}

        self.assertIn("missing_document_title", issue_types)
        self.assertIn("missing_document_language", issue_types)

    def test_heading_level_jump_is_reported(self):
        document = DocumentModel(
            original_filename="sample.docx",
            source_format="docx",
            title="Sample",
            language="en-AU",
            elements=[
                DocumentElement(type=ElementType.HEADING, text="Overview", heading_level=1),
                DocumentElement(type=ElementType.HEADING, text="Details", heading_level=3),
            ],
        )

        result = analyse_document(document)

        self.assertTrue(any(issue.issue_type == "skipped_heading_level" for issue in result.issues))

    def test_image_without_alt_text_needs_user_confirmation(self):
        document = DocumentModel(
            original_filename="sample.pdf",
            source_format="pdf",
            title="Sample",
            language="en-AU",
            elements=[
                DocumentElement(
                    type=ElementType.IMAGE,
                    source=SourceLocation(page_number=2, description="chart image"),
                )
            ],
        )

        result = analyse_document(document)
        issue = next(
            issue for issue in result.issues if issue.issue_type == "missing_image_alt_text"
        )

        self.assertEqual(issue.automation_status.value, "needs_user_confirmation")

    def test_decorative_image_is_not_flagged(self):
        document = DocumentModel(
            original_filename="sample.pdf",
            source_format="pdf",
            title="Sample",
            language="en-AU",
            elements=[DocumentElement(type=ElementType.IMAGE, decorative=True)],
        )

        result = analyse_document(document)

        self.assertEqual(result.issues, [])

    def test_report_avoids_legal_compliance_claims(self):
        document = DocumentModel(
            original_filename="sample.pdf",
            source_format="pdf",
            title="Sample",
            language="en-AU",
            elements=[],
        )

        report = build_validation_report(analyse_document(document))

        self.assertIn(
            "legal compliance is not guaranteed",
            report["summary"]["validation_statement"],
        )
        self.assertEqual(report["summary"]["severity_counts"], {})

    def test_untagged_pdf_is_critical_issue(self):
        document = DocumentModel(
            original_filename="untagged.pdf",
            source_format="pdf",
            title="Untagged sample",
            language="en-AU",
            pdf=PdfInspection(
                page_count=2,
                has_struct_tree=False,
                mark_info_marked=False,
                text_block_count=8,
            ),
        )

        result = analyse_document(document)
        issue = next(issue for issue in result.issues if issue.issue_type == "untagged_pdf")

        self.assertEqual(issue.severity.value, "critical")
        self.assertEqual(issue.automation_status.value, "auto_fixable")

    def test_encrypted_pdf_blocks_automation(self):
        document = DocumentModel(
            original_filename="locked.pdf",
            source_format="pdf",
            title="Locked",
            language="en-AU",
            pdf=PdfInspection(page_count=1, is_encrypted=True),
        )

        result = analyse_document(document)
        issue = next(issue for issue in result.issues if issue.issue_type == "encrypted_pdf")

        self.assertEqual(issue.severity.value, "critical")
        self.assertEqual(issue.automation_status.value, "cannot_automate")

    def test_image_only_pdf_requires_ocr_or_better_source(self):
        document = DocumentModel(
            original_filename="scan.pdf",
            source_format="pdf",
            title="Scanned",
            language="en-AU",
            pdf=PdfInspection(
                page_count=4,
                has_struct_tree=False,
                mark_info_marked=False,
                image_count=4,
                text_block_count=0,
            ),
        )

        result = analyse_document(document)
        issue_types = {issue.issue_type for issue in result.issues}

        self.assertIn("no_extractable_pdf_text", issue_types)

    def test_report_includes_pdf_inspection_summary(self):
        document = DocumentModel(
            original_filename="sample.pdf",
            source_format="pdf",
            title="Sample",
            language="en-AU",
            pdf=PdfInspection(
                page_count=3,
                has_struct_tree=True,
                mark_info_marked=True,
                text_block_count=12,
            ),
        )

        report = build_validation_report(analyse_document(document))

        self.assertEqual(report["source"]["pdf"]["page_count"], 3)
        self.assertTrue(report["source"]["pdf"]["has_struct_tree"])
        self.assertIn("issue_type_counts", report["summary"])

    def test_multi_column_pdf_requires_reading_order_review(self):
        document = DocumentModel(
            original_filename="columns.pdf",
            source_format="pdf",
            title="Columns",
            language="en-AU",
            pdf=PdfInspection(
                page_count=1,
                has_struct_tree=False,
                mark_info_marked=False,
                text_block_count=8,
                pages_with_multiple_columns=[1],
            ),
        )

        result = analyse_document(document)

        self.assertTrue(
            any(issue.issue_type == "multi_column_reading_order_review" for issue in result.issues)
        )


if __name__ == "__main__":
    unittest.main()
