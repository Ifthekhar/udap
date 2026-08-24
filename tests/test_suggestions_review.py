import unittest

from udap.models import (
    DocumentElement,
    DocumentModel,
    ElementType,
    ReviewDecision,
    SuggestionAction,
    UserDecision,
)
from udap.pipeline import analyse_document, build_validation_report
from udap.review import ReviewWorkflowError, record_user_decisions


class SuggestionsReviewTest(unittest.TestCase):
    def test_analysis_generates_suggestions_for_each_issue(self):
        document = DocumentModel(
            original_filename="sample.pdf",
            source_format="pdf",
            elements=[DocumentElement(type=ElementType.PARAGRAPH, text="Annual Report 2026")],
        )

        result = analyse_document(document)

        self.assertEqual(len(result.suggestions), len(result.issues))
        self.assertEqual(len(result.audit_events), len(result.suggestions))
        self.assertTrue(
            any(
                suggestion.action == SuggestionAction.SET_DOCUMENT_TITLE
                for suggestion in result.suggestions
            )
        )

    def test_image_alt_text_suggestion_uses_nearby_text(self):
        document = DocumentModel(
            original_filename="image.pdf",
            source_format="pdf",
            title="Image Sample",
            language="en-AU",
            elements=[
                DocumentElement(
                    type=ElementType.IMAGE,
                    metadata={"nearby_text": "Chart showing transport growth from 2021 to 2026"},
                )
            ],
        )

        result = analyse_document(document)
        suggestion = next(
            suggestion
            for suggestion in result.suggestions
            if suggestion.action == SuggestionAction.GENERATE_ALT_TEXT
        )

        self.assertTrue(suggestion.requires_user_confirmation)
        self.assertIn("transport growth", suggestion.proposed_value)

    def test_link_text_suggestion_uses_destination_when_context_missing(self):
        document = DocumentModel(
            original_filename="link.pdf",
            source_format="pdf",
            title="Link Sample",
            language="en-AU",
            elements=[
                DocumentElement(
                    type=ElementType.LINK,
                    text="https://example.com/report",
                    href="https://example.com/report",
                )
            ],
        )

        result = analyse_document(document)
        suggestion = next(
            suggestion
            for suggestion in result.suggestions
            if suggestion.action == SuggestionAction.IMPROVE_LINK_TEXT
        )

        self.assertEqual(suggestion.proposed_value, "Open example.com")

    def test_user_can_accept_suggestion(self):
        document = DocumentModel(
            original_filename="sample.pdf",
            source_format="pdf",
            elements=[DocumentElement(type=ElementType.PARAGRAPH, text="Annual Report 2026")],
        )
        result = analyse_document(document)
        suggestion = result.suggestions[0]

        reviewed = record_user_decisions(
            result,
            [
                UserDecision(
                    suggestion_id=suggestion.id,
                    issue_id=suggestion.issue_id,
                    decision=ReviewDecision.ACCEPT,
                )
            ],
        )

        issue = next(issue for issue in reviewed.issues if issue.id == suggestion.issue_id)
        self.assertEqual(issue.final_status.value, "accepted")
        self.assertGreater(len(reviewed.audit_events), len(result.audit_events))

    def test_user_can_edit_suggestion_value(self):
        document = DocumentModel(
            original_filename="image.pdf",
            source_format="pdf",
            title="Image Sample",
            language="en-AU",
            elements=[DocumentElement(type=ElementType.IMAGE)],
        )
        result = analyse_document(document)
        suggestion = result.suggestions[0]

        reviewed = record_user_decisions(
            result,
            [
                UserDecision(
                    suggestion_id=suggestion.id,
                    issue_id=suggestion.issue_id,
                    decision=ReviewDecision.EDIT,
                    final_value="Chart showing annual transport growth.",
                )
            ],
        )

        event = reviewed.audit_events[-1]
        self.assertEqual(event.metadata["decision"], "edit")
        self.assertEqual(event.metadata["final_value"], "Chart showing annual transport growth.")

    def test_invalid_review_decision_is_rejected(self):
        document = DocumentModel(
            original_filename="sample.pdf",
            source_format="pdf",
            elements=[DocumentElement(type=ElementType.PARAGRAPH, text="Annual Report 2026")],
        )
        result = analyse_document(document)

        with self.assertRaises(ReviewWorkflowError):
            record_user_decisions(
                result,
                [
                    UserDecision(
                        suggestion_id="missing",
                        issue_id=result.issues[0].id,
                        decision=ReviewDecision.ACCEPT,
                    )
                ],
            )

    def test_report_includes_suggestions_and_audit_events(self):
        document = DocumentModel(
            original_filename="sample.pdf",
            source_format="pdf",
            elements=[DocumentElement(type=ElementType.PARAGRAPH, text="Annual Report 2026")],
        )

        report = build_validation_report(analyse_document(document))

        self.assertEqual(report["summary"]["suggestion_count"], len(report["suggestions"]))
        self.assertEqual(len(report["audit_events"]), len(report["suggestions"]))


if __name__ == "__main__":
    unittest.main()
