"""Application-level orchestration for analysis and reporting."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from .models import AnalysisJob, AnalysisResult, AuditEvent, AuditEventType, DocumentModel
from .rules import evaluate_document
from .standards import WCAG_2_2_AA
from .suggestions import generate_remediation_suggestions


def analyse_document(document: DocumentModel, standard: str = WCAG_2_2_AA) -> AnalysisResult:
    """Analyse a document model against the MVP rule set."""

    issues = evaluate_document(document)
    suggestions = generate_remediation_suggestions(document, issues)
    audit_events = [
        AuditEvent(
            type=AuditEventType.SUGGESTION_CREATED,
            issue_id=suggestion.issue_id,
            suggestion_id=suggestion.id,
            message="Remediation suggestion created.",
            metadata={
                "action": suggestion.action.value,
                "source": suggestion.source.value,
                "requires_user_confirmation": suggestion.requires_user_confirmation,
            },
        )
        for suggestion in suggestions
    ]

    return AnalysisResult(
        document=document,
        standard=standard,
        issues=issues,
        suggestions=suggestions,
        audit_events=audit_events,
    )


def build_validation_report(result: AnalysisResult) -> dict[str, Any]:
    """Create the first machine-readable report shape.

    This report intentionally avoids legal compliance guarantees. It describes
    automated checks and review needs only.
    """

    return {
        "file": result.document.original_filename,
        "target": result.standard,
        "generated_at": datetime.now(UTC).isoformat(),
        "source": {
            "format": result.document.source_format,
            "pdf": asdict(result.document.pdf) if result.document.pdf else None,
        },
        "summary": {
            "initial_issue_count": result.issue_count,
            "suggestion_count": result.suggestion_count(),
            "automation_status_counts": result.counts_by_status(),
            "severity_counts": result.counts_by_severity(),
            "issue_type_counts": result.counts_by_issue_type(),
            "validation_statement": "Automated analysis completed; legal compliance is not guaranteed.",
        },
        "issues": [asdict(issue) for issue in result.issues],
        "suggestions": [asdict(suggestion) for suggestion in result.suggestions],
        "audit_events": [asdict(event) for event in result.audit_events],
    }


def build_job_report(job: AnalysisJob) -> dict[str, Any]:
    report = build_validation_report(job.result)
    report["job"] = {
        "id": job.id,
        "status": job.status.value,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }
    return report
