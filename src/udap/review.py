"""User review workflow for remediation suggestions."""

from __future__ import annotations

from dataclasses import replace

from .models import (
    AnalysisResult,
    AuditEvent,
    AuditEventType,
    IssueStatus,
    ReviewDecision,
    UserDecision,
)


class ReviewWorkflowError(ValueError):
    pass


def record_user_decisions(
    result: AnalysisResult,
    decisions: list[UserDecision],
) -> AnalysisResult:
    """Apply accept/edit/reject decisions to a copy of an analysis result."""

    suggestions_by_id = {suggestion.id: suggestion for suggestion in result.suggestions}
    issues_by_id = {issue.id: issue for issue in result.issues}
    updated_issues = list(result.issues)
    audit_events = list(result.audit_events)

    issue_index = {issue.id: index for index, issue in enumerate(updated_issues)}

    for decision in decisions:
        suggestion = suggestions_by_id.get(decision.suggestion_id)
        if suggestion is None:
            raise ReviewWorkflowError(f"Unknown suggestion id: {decision.suggestion_id}")
        if suggestion.issue_id != decision.issue_id:
            raise ReviewWorkflowError("Decision issue_id does not match the suggestion issue_id.")
        issue = issues_by_id.get(decision.issue_id)
        if issue is None:
            raise ReviewWorkflowError(f"Unknown issue id: {decision.issue_id}")

        final_status = _status_for_decision(decision.decision)
        updated_issues[issue_index[issue.id]] = replace(issue, final_status=final_status)
        audit_events.append(
            AuditEvent(
                type=AuditEventType.USER_DECISION_RECORDED,
                issue_id=issue.id,
                suggestion_id=suggestion.id,
                message=_decision_message(decision),
                metadata={
                    "decision": decision.decision.value,
                    "final_value": decision.final_value,
                    "reviewer_note": decision.reviewer_note,
                },
            )
        )

    return replace(result, issues=updated_issues, audit_events=audit_events)


def _status_for_decision(decision: ReviewDecision) -> IssueStatus:
    if decision == ReviewDecision.ACCEPT:
        return IssueStatus.ACCEPTED
    if decision == ReviewDecision.EDIT:
        return IssueStatus.ACCEPTED
    return IssueStatus.REJECTED


def _decision_message(decision: UserDecision) -> str:
    if decision.decision == ReviewDecision.EDIT:
        return "User edited and accepted the remediation suggestion."
    if decision.decision == ReviewDecision.ACCEPT:
        return "User accepted the remediation suggestion."
    return "User rejected the remediation suggestion."
