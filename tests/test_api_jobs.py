import os
import tempfile
import unittest
from pathlib import Path

import pymupdf
from fastapi.testclient import TestClient

from udap.api import create_app


class ApiJobsTest(unittest.TestCase):
    def test_workflow_ui_is_served(self):
        client = TestClient(create_app())

        page_response = client.get("/")
        css_response = client.get("/static/app.css")
        js_response = client.get("/static/app.js")

        self.assertEqual(page_response.status_code, 200)
        self.assertIn("Document Accessibility Workflow", page_response.text)
        self.assertIn("/static/app.css", page_response.text)
        self.assertIn("Existing job ID", page_response.text)
        self.assertIn("remediation-summary", page_response.text)
        self.assertIn("Report", page_response.text)
        self.assertIn("report-details", page_response.text)
        self.assertEqual(css_response.headers["content-type"], "text/css; charset=utf-8")
        self.assertIn("workflow-grid", css_response.text)
        self.assertIn("inline-form", css_response.text)
        self.assertIn("report-grid", css_response.text)
        self.assertEqual(
            js_response.headers["content-type"],
            "application/javascript",
        )
        self.assertIn("/documents/analyse", js_response.text)
        self.assertIn("visibleSuggestions", js_response.text)
        self.assertIn("Remediation Report", js_response.text)
        self.assertIn("Fixed issues", js_response.text)
        self.assertIn("PDF/UA", js_response.text)

    def test_upload_get_and_review_job(self):
        with tempfile.TemporaryDirectory() as job_dir:
            previous = os.environ.get("UDAP_JOB_STORE_DIR")
            os.environ["UDAP_JOB_STORE_DIR"] = job_dir
            try:
                client = TestClient(create_app())
            finally:
                if previous is None:
                    os.environ.pop("UDAP_JOB_STORE_DIR", None)
                else:
                    os.environ["UDAP_JOB_STORE_DIR"] = previous

            pdf_path = _build_single_issue_pdf()
            with pdf_path.open("rb") as handle:
                response = client.post(
                    "/documents/analyse",
                    files={"file": ("sample.pdf", handle, "application/pdf")},
                )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            job_id = payload["job"]["id"]
            self.assertEqual(payload["file"], "sample.pdf")
            self.assertEqual(payload["summary"]["initial_issue_count"], 1)
            self.assertEqual(payload["summary"]["suggestion_count"], 1)

            get_response = client.get(f"/jobs/{job_id}")
            self.assertEqual(get_response.status_code, 200)
            self.assertEqual(get_response.json()["job"]["id"], job_id)

            suggestion = payload["suggestions"][0]
            review_response = client.post(
                f"/jobs/{job_id}/review",
                json=[
                    {
                        "suggestion_id": suggestion["id"],
                        "issue_id": suggestion["issue_id"],
                        "decision": "accept",
                    }
                ],
            )

            self.assertEqual(review_response.status_code, 200)
            reviewed = review_response.json()
            self.assertEqual(reviewed["job"]["status"], "reviewed")
            self.assertEqual(reviewed["issues"][0]["final_status"], "accepted")
            self.assertEqual(reviewed["audit_events"][-1]["type"], "user_decision_recorded")

            output_response = client.post(f"/jobs/{job_id}/outputs/pdf")
            self.assertEqual(output_response.status_code, 200)
            output_payload = output_response.json()
            self.assertEqual(output_payload["job"]["status"], "output_generated")
            self.assertEqual(len(output_payload["output_artifacts"]), 2)
            artifact = next(
                item
                for item in output_payload["output_artifacts"]
                if item["type"] == "accessible_pdf"
            )
            report_artifact = next(
                item
                for item in output_payload["output_artifacts"]
                if item["type"] == "accessibility_report"
            )
            self.assertEqual(artifact["filename"], "sample_accessible.pdf")
            self.assertEqual(report_artifact["filename"], "sample_accessibility_report.json")

            download_response = client.get(f"/jobs/{job_id}/outputs/{artifact['id']}")
            self.assertEqual(download_response.status_code, 200)
            self.assertEqual(download_response.headers["content-type"], "application/pdf")

            report_response = client.get(f"/jobs/{job_id}/outputs/{report_artifact['id']}")
            self.assertEqual(report_response.status_code, 200)
            self.assertEqual(report_response.headers["content-type"], "application/json")
            self.assertIn("remediation_summary", report_response.json()["validation_report"])


def _build_single_issue_pdf() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        path = Path(tmp.name)

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Annual Report 2026", fontsize=18)
    doc.set_metadata({"title": "API Job Sample"})
    doc.xref_set_key(doc.pdf_catalog(), "Lang", "(en-AU)")
    doc.save(path)
    doc.close()
    return path


if __name__ == "__main__":
    unittest.main()
