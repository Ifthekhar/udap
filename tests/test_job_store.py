import tempfile
import unittest
from pathlib import Path

from udap.job_store import LocalJobStore
from udap.models import (
    DocumentElement,
    DocumentModel,
    ElementType,
    JobStatus,
    OutputArtifact,
    OutputArtifactType,
    ReviewDecision,
    UserDecision,
)
from udap.pipeline import analyse_document


class JobStoreTest(unittest.TestCase):
    def test_job_store_persists_and_reloads_analysis_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalJobStore(Path(tmp))
            result = analyse_document(
                DocumentModel(
                    original_filename="sample.pdf",
                    source_format="pdf",
                    elements=[DocumentElement(type=ElementType.PARAGRAPH, text="Annual Report")],
                )
            )

            job = store.create(result)
            reloaded = store.get(job.id)

            self.assertEqual(reloaded.id, job.id)
            self.assertEqual(reloaded.status, JobStatus.AWAITING_REVIEW)
            self.assertEqual(len(reloaded.result.issues), len(result.issues))
            self.assertEqual(len(reloaded.result.suggestions), len(result.suggestions))

    def test_job_store_applies_review_decisions_and_updates_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalJobStore(Path(tmp))
            result = analyse_document(
                DocumentModel(
                    original_filename="sample.pdf",
                    source_format="pdf",
                    title="Sample",
                    language="en-AU",
                    elements=[DocumentElement(type=ElementType.IMAGE)],
                )
            )
            job = store.create(result)
            decisions = [
                UserDecision(
                    suggestion_id=suggestion.id,
                    issue_id=suggestion.issue_id,
                    decision=ReviewDecision.ACCEPT,
                )
                for suggestion in job.result.suggestions
            ]

            updated = store.apply_decisions(job.id, decisions)
            reloaded = store.get(job.id)

            self.assertEqual(updated.status, JobStatus.REVIEWED)
            self.assertEqual(reloaded.status, JobStatus.REVIEWED)
            self.assertTrue(all(issue.final_status.value == "accepted" for issue in reloaded.result.issues))

    def test_job_store_persists_multiple_output_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalJobStore(Path(tmp))
            result = analyse_document(
                DocumentModel(
                    original_filename="sample.pdf",
                    source_format="pdf",
                    title="Sample",
                    language="en-AU",
                    elements=[DocumentElement(type=ElementType.PARAGRAPH, text="Body")],
                )
            )
            job = store.create(result)
            pdf = OutputArtifact(
                id="pdf-1",
                type=OutputArtifactType.ACCESSIBLE_PDF,
                filename="sample_accessible.pdf",
                path="/tmp/sample_accessible.pdf",
                created_at="2026-08-25T00:00:00+00:00",
                validation_report={},
            )
            report = OutputArtifact(
                id="report-1",
                type=OutputArtifactType.ACCESSIBILITY_REPORT,
                filename="sample_accessibility_report.json",
                path="/tmp/sample_accessibility_report.json",
                created_at="2026-08-25T00:00:00+00:00",
                validation_report={"artifact_type": "accessibility_report"},
            )

            updated = store.add_output_artifacts(job.id, [pdf, report])
            reloaded = store.get(job.id)

        self.assertEqual(updated.status, JobStatus.OUTPUT_GENERATED)
        self.assertEqual([artifact.type for artifact in reloaded.output_artifacts], [pdf.type, report.type])


if __name__ == "__main__":
    unittest.main()
