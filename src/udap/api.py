"""FastAPI entry point for the accessibility remediation service."""

from __future__ import annotations

import os
from tempfile import NamedTemporaryFile
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .extractors import MissingExtractorDependencyError, UnsupportedDocumentError, load_document
from .job_store import JobNotFoundError, LocalJobStore
from .models import OutputArtifactType, ReviewDecision, UserDecision
from .pdf_output import PdfGenerationError, generate_remediated_pdf_outputs
from .pipeline import analyse_document, build_job_report
from .review import ReviewWorkflowError


class ReviewDecisionPayload(BaseModel):
    suggestion_id: str
    issue_id: str
    decision: ReviewDecision
    final_value: str | None = None
    reviewer_note: str | None = None


def create_app():
    app = FastAPI(
        title="Universal Digital Accessibility Platform",
        version="0.1.0",
        description="PDF-first accessibility remediation API.",
    )
    store = LocalJobStore(os.environ.get("UDAP_JOB_STORE_DIR", ".local/jobs"))

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
                document.original_filename = file.filename or document.original_filename
                result = analyse_document(document)
                job = store.create(result)
            except UnsupportedDocumentError as exc:
                raise HTTPException(status_code=415, detail=str(exc)) from exc
            except MissingExtractorDependencyError as exc:
                raise HTTPException(status_code=500, detail=str(exc)) from exc

        return build_job_report(job)

    @app.get("/jobs/{job_id}")
    async def get_job(job_id: str) -> dict:
        try:
            job = store.get(job_id)
        except JobNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Job not found.") from exc
        return build_job_report(job)

    @app.post("/jobs/{job_id}/review")
    async def apply_job_review_decisions(job_id: str, payload: list[ReviewDecisionPayload]) -> dict:
        """Apply accept/edit/reject decisions to a persisted analysis job."""

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

        if not decisions:
            try:
                return build_job_report(store.get(job_id))
            except JobNotFoundError as exc:
                raise HTTPException(status_code=404, detail="Job not found.") from exc

        try:
            job = store.apply_decisions(job_id, decisions)
        except JobNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Job not found.") from exc
        except ReviewWorkflowError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return build_job_report(job)

    @app.post("/jobs/{job_id}/outputs/pdf")
    async def generate_pdf_output(job_id: str) -> dict:
        try:
            job = store.get(job_id)
            artifacts = generate_remediated_pdf_outputs(job.result)
            updated = store.add_output_artifacts(job_id, artifacts)
        except JobNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Job not found.") from exc
        except PdfGenerationError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        return build_job_report(updated)

    @app.get("/jobs/{job_id}/outputs/{artifact_id}")
    async def download_output(job_id: str, artifact_id: str):
        try:
            job = store.get(job_id)
        except JobNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Job not found.") from exc

        artifact = next(
            (item for item in job.output_artifacts if item.id == artifact_id),
            None,
        )
        if artifact is None:
            raise HTTPException(status_code=404, detail="Output artifact not found.")

        return FileResponse(
            artifact.path,
            media_type=_artifact_media_type(artifact.type),
            filename=artifact.filename,
        )

    @app.post("/reviews/apply")
    async def apply_review_decisions(payload: list[ReviewDecisionPayload]) -> dict:
        """Compatibility endpoint for validating review payload shape."""

        return {"decision_count": len(payload), "status": "use_job_review_endpoint"}

    return app


def _safe_suffix(filename: str) -> str:
    lowered = filename.lower()
    if lowered.endswith(".pdf"):
        return ".pdf"
    if lowered.endswith(".docx"):
        return ".docx"
    return ""


def _artifact_media_type(artifact_type: OutputArtifactType) -> str:
    if artifact_type == OutputArtifactType.ACCESSIBILITY_REPORT:
        return "application/json"
    return "application/pdf"
