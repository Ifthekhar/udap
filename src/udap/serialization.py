"""JSON-safe serialisation for persisted analysis jobs."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .models import (
    AccessibilityIssue,
    AnalysisJob,
    AnalysisResult,
    AuditEvent,
    AuditEventType,
    AutomationStatus,
    DocumentElement,
    DocumentModel,
    ElementType,
    IssueSeverity,
    IssueStatus,
    JobStatus,
    OutputArtifact,
    OutputArtifactType,
    PdfInspection,
    RemediationSuggestion,
    SourceLocation,
    SuggestionAction,
    SuggestionSource,
)


def job_to_dict(job: AnalysisJob) -> dict[str, Any]:
    return asdict(job)


def job_from_dict(data: dict[str, Any]) -> AnalysisJob:
    return AnalysisJob(
        id=str(data["id"]),
        result=result_from_dict(data["result"]),
        status=JobStatus(data["status"]),
        created_at=str(data["created_at"]),
        updated_at=str(data["updated_at"]),
        output_artifacts=[
            output_artifact_from_dict(item) for item in data.get("output_artifacts", [])
        ],
    )


def result_from_dict(data: dict[str, Any]) -> AnalysisResult:
    return AnalysisResult(
        document=document_from_dict(data["document"]),
        standard=str(data["standard"]),
        issues=[issue_from_dict(item) for item in data.get("issues", [])],
        suggestions=[suggestion_from_dict(item) for item in data.get("suggestions", [])],
        audit_events=[audit_event_from_dict(item) for item in data.get("audit_events", [])],
    )


def document_from_dict(data: dict[str, Any]) -> DocumentModel:
    return DocumentModel(
        original_filename=str(data["original_filename"]),
        source_format=data["source_format"],
        title=data.get("title"),
        language=data.get("language"),
        elements=[element_from_dict(item) for item in data.get("elements", [])],
        metadata=dict(data.get("metadata", {})),
        pdf=pdf_from_dict(data["pdf"]) if data.get("pdf") else None,
    )


def element_from_dict(data: dict[str, Any]) -> DocumentElement:
    return DocumentElement(
        type=ElementType(data["type"]),
        text=str(data.get("text", "")),
        id=str(data["id"]),
        source=source_from_dict(data.get("source", {})),
        confidence=float(data.get("confidence", 1.0)),
        children=[element_from_dict(item) for item in data.get("children", [])],
        heading_level=data.get("heading_level"),
        language=data.get("language"),
        alt_text=data.get("alt_text"),
        decorative=bool(data.get("decorative", False)),
        href=data.get("href"),
        table_headers=list(data.get("table_headers", [])),
        metadata=dict(data.get("metadata", {})),
    )


def source_from_dict(data: dict[str, Any]) -> SourceLocation:
    bbox = data.get("bbox")
    return SourceLocation(
        page_number=data.get("page_number"),
        element_id=data.get("element_id"),
        description=data.get("description"),
        bbox=tuple(bbox) if bbox else None,
    )


def pdf_from_dict(data: dict[str, Any]) -> PdfInspection:
    return PdfInspection(
        page_count=int(data.get("page_count", 0)),
        is_encrypted=bool(data.get("is_encrypted", False)),
        has_struct_tree=data.get("has_struct_tree"),
        mark_info_marked=data.get("mark_info_marked"),
        language=data.get("language"),
        title=data.get("title"),
        image_count=int(data.get("image_count", 0)),
        link_count=int(data.get("link_count", 0)),
        text_block_count=int(data.get("text_block_count", 0)),
        heading_candidate_count=int(data.get("heading_candidate_count", 0)),
        table_candidate_count=int(data.get("table_candidate_count", 0)),
        pages_with_multiple_columns=list(data.get("pages_with_multiple_columns", [])),
        marked_content_count=int(data.get("marked_content_count", 0)),
        parent_tree_entry_count=int(data.get("parent_tree_entry_count", 0)),
        structure_element_count=int(data.get("structure_element_count", 0)),
        extraction_warnings=list(data.get("extraction_warnings", [])),
    )


def issue_from_dict(data: dict[str, Any]) -> AccessibilityIssue:
    return AccessibilityIssue(
        id=str(data["id"]),
        rule_id=str(data["rule_id"]),
        issue_type=str(data["issue_type"]),
        severity=IssueSeverity(data["severity"]),
        source=source_from_dict(data.get("source", {})),
        explanation=str(data["explanation"]),
        suggested_fix=data.get("suggested_fix"),
        confidence=float(data.get("confidence", 0.0)),
        automation_status=AutomationStatus(data["automation_status"]),
        final_status=IssueStatus(data.get("final_status", IssueStatus.OPEN)),
    )


def suggestion_from_dict(data: dict[str, Any]) -> RemediationSuggestion:
    return RemediationSuggestion(
        id=str(data["id"]),
        issue_id=str(data["issue_id"]),
        action=SuggestionAction(data["action"]),
        source=SuggestionSource(data["source"]),
        proposed_value=data.get("proposed_value"),
        explanation=str(data["explanation"]),
        requires_user_confirmation=bool(data.get("requires_user_confirmation", False)),
        confidence=float(data.get("confidence", 0.0)),
    )


def audit_event_from_dict(data: dict[str, Any]) -> AuditEvent:
    return AuditEvent(
        type=AuditEventType(data["type"]),
        issue_id=str(data["issue_id"]),
        suggestion_id=data.get("suggestion_id"),
        message=str(data["message"]),
        metadata=dict(data.get("metadata", {})),
    )


def output_artifact_from_dict(data: dict[str, Any]) -> OutputArtifact:
    return OutputArtifact(
        id=str(data["id"]),
        type=OutputArtifactType(data["type"]),
        filename=str(data["filename"]),
        path=str(data["path"]),
        created_at=str(data["created_at"]),
        validation_report=dict(data.get("validation_report", {})),
    )
