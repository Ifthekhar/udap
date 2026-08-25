"""Run the customer-demo workflow end to end against the local FastAPI app."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from fastapi.testclient import TestClient

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from demo.create_demo_pdfs import create_demo_pdfs
from udap.api import create_app

NEEDS_REVIEW_SAMPLE = "udap-demo-needs-review.pdf"


def rehearse_demo(sample_dir: str | Path | None = None) -> dict[str, Any]:
    sample_paths = create_demo_pdfs(sample_dir) if sample_dir else create_demo_pdfs()
    sample = next(path for path in sample_paths if path.name == NEEDS_REVIEW_SAMPLE)

    with TemporaryDirectory() as job_dir:
        previous = os.environ.get("UDAP_JOB_STORE_DIR")
        os.environ["UDAP_JOB_STORE_DIR"] = job_dir
        try:
            client = TestClient(create_app())
        finally:
            if previous is None:
                os.environ.pop("UDAP_JOB_STORE_DIR", None)
            else:
                os.environ["UDAP_JOB_STORE_DIR"] = previous

        with sample.open("rb") as handle:
            analysis = client.post(
                "/documents/analyse",
                files={"file": (sample.name, handle, "application/pdf")},
            )
        analysis.raise_for_status()
        analysed = analysis.json()
        job_id = analysed["job"]["id"]

        decisions = [_decision_for_suggestion(item) for item in analysed["suggestions"]]
        review = client.post(f"/jobs/{job_id}/review", json=decisions)
        review.raise_for_status()

        output = client.post(f"/jobs/{job_id}/outputs/pdf")
        output.raise_for_status()
        completed = output.json()

        artifacts = completed["output_artifacts"]
        pdf_artifact = next(item for item in artifacts if item["type"] == "accessible_pdf")
        report_artifact = next(item for item in artifacts if item["type"] == "accessibility_report")

        pdf_download = client.get(f"/jobs/{job_id}/outputs/{pdf_artifact['id']}")
        report_download = client.get(f"/jobs/{job_id}/outputs/{report_artifact['id']}")
        pdf_download.raise_for_status()
        report_download.raise_for_status()

        return {
            "sample": str(sample),
            "job_id": job_id,
            "initial_issue_count": analysed["summary"]["initial_issue_count"],
            "suggestion_count": analysed["summary"]["suggestion_count"],
            "final_status": completed["job"]["status"],
            "artifact_filenames": [item["filename"] for item in artifacts],
            "pdf_structure_status": pdf_artifact["validation_report"]["pdf_structure"]["status"],
            "reading_order_status": pdf_artifact["validation_report"]["pdf_structure"]["reading_order"][
                "status"
            ],
            "remediation_summary": pdf_artifact["validation_report"]["remediation_summary"],
        }


def _decision_for_suggestion(suggestion: dict[str, Any]) -> dict[str, str]:
    action = suggestion["action"]
    final_value = suggestion.get("proposed_value") or ""
    decision = "accept"

    if action == "set_document_language":
        decision = "edit"
        final_value = "en-AU"
    elif action == "generate_alt_text":
        decision = "edit"
        final_value = "Bar chart showing quarterly accessibility progress."
    elif action == "improve_link_text":
        decision = "edit"
        final_value = "Read the quarterly accessibility report"

    return {
        "suggestion_id": suggestion["id"],
        "issue_id": suggestion["issue_id"],
        "decision": decision,
        "final_value": final_value,
    }


if __name__ == "__main__":
    result = rehearse_demo()
    print(f"Sample: {result['sample']}")
    print(f"Job: {result['job_id']}")
    print(f"Issues found: {result['initial_issue_count']}")
    print(f"Suggestions reviewed: {result['suggestion_count']}")
    print(f"Final status: {result['final_status']}")
    print(f"PDF structure: {result['pdf_structure_status']}")
    print(f"Reading order: {result['reading_order_status']}")
    print("Artifacts:")
    for filename in result["artifact_filenames"]:
        print(f"- {filename}")
