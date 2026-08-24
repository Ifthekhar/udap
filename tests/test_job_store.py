import tempfile
import unittest
from pathlib import Path

from udap.job_store import LocalJobStore
from udap.models import (
    DocumentElement,
    DocumentModel,
    ElementType,
    JobStatus,
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


if __name__ == "__main__":
    unittest.main()
