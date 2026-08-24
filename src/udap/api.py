"""FastAPI entry point for the accessibility remediation service."""

from __future__ import annotations

from tempfile import NamedTemporaryFile
from typing import Annotated

from .extractors import MissingExtractorDependencyError, UnsupportedDocumentError, load_document
from .pipeline import analyse_document, build_validation_report


def create_app():
    from fastapi import FastAPI, File, HTTPException, UploadFile
    from pydantic import BaseModel

    from .models import ReviewDecision, UserDecision

    class ReviewDecisionPayload(BaseModel):
        suggestion_id: str
        issue_id: str
        decision: ReviewDecision
        final_value: str | None = None
        reviewer_note: str | None = None

    app = FastAPI(
        title="Universal Digital Accessibility Platform",
        version="0.1.0",
        description="PDF-first accessibility remediation API.",
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/documents/analyse")
    @app.post("/documents/analyze")
    async def analyse_upload(file: Annotated[UploadFile, File(...)]) -> dict:
        suffix = _safe_suffix(file.filename or "")
        with NamedTemporaryFile(delete=True, suffix=suffix) as tmp:
            while chunk := await file.read(1024 * 1024):
                tmp.write(chunk)
            tmp.flush()

            try:
                document = load_document(tmp.name)
                result = analyse_document(document)
            except UnsupportedDocumentError as exc:
                raise HTTPException(status_code=415, detail=str(exc)) from exc
            except MissingExtractorDependencyError as exc:
                raise HTTPException(status_code=500, detail=str(exc)) from exc

        return build_validation_report(result)

    @app.post("/reviews/apply")
    async def apply_review_decisions(payload: list[ReviewDecisionPayload]) -> dict:
        """Validate review payload shape for the future persisted workflow.

        This endpoint intentionally does not persist yet. It proves the API
        contract that the UI will use once analysis jobs are stored.
        """

        decisions = [
            UserDecision(
                suggestion_id=item.suggestion_id,
                issue_id=item.issue_id,
                decision=item.decision,
                final_value=item.final_value,
                reviewer_note=item.reviewer_note,
            )
            for item in payload
        ]

        # Persistence arrives with the job/database milestone. For now this
        # endpoint validates decision payloads and reports their count.
        if not decisions:
            return {"decision_count": 0, "status": "no_decisions"}

        return {"decision_count": len(decisions), "status": "accepted_for_future_job_store"}

    return app


def _safe_suffix(filename: str) -> str:
    lowered = filename.lower()
    if lowered.endswith(".pdf"):
        return ".pdf"
    if lowered.endswith(".docx"):
        return ".docx"
    return ""
