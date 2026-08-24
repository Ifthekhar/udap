"""Milestone 4 remediation suggestion generation."""

from __future__ import annotations

from urllib.parse import urlparse
from uuid import uuid4

from .models import (
    AccessibilityIssue,
    AutomationStatus,
    DocumentElement,
    DocumentModel,
    RemediationSuggestion,
    SuggestionAction,
    SuggestionSource,
)


def generate_remediation_suggestions(
    document: DocumentModel,
    issues: list[AccessibilityIssue],
) -> list[RemediationSuggestion]:
    """Generate reviewable remediation suggestions for detected issues.

    These are deterministic suggestions for the first implementation. The
    function is intentionally shaped like an AI provider boundary: each issue
    receives an action, proposed value, explanation, confidence, and review flag.
    """

    return [_build_suggestion(document, issue) for issue in issues]


def _build_suggestion(
    document: DocumentModel,
    issue: AccessibilityIssue,
) -> RemediationSuggestion:
    element = _find_element(document, issue)
    proposed_value = _proposed_value(document, issue, element)
    action = _action_for_issue(issue.issue_type)
    source = _source_for_issue(issue.issue_type)

    return RemediationSuggestion(
        id=str(uuid4()),
        issue_id=issue.id,
        action=action,
        source=source,
        proposed_value=proposed_value,
        explanation=_suggestion_explanation(issue, action, proposed_value),
        requires_user_confirmation=issue.automation_status != AutomationStatus.AUTO_FIXABLE,
        confidence=_suggestion_confidence(issue, proposed_value),
    )


def _action_for_issue(issue_type: str) -> SuggestionAction:
    return {
        "missing_document_title": SuggestionAction.SET_DOCUMENT_TITLE,
        "missing_document_language": SuggestionAction.SET_DOCUMENT_LANGUAGE,
        "untagged_pdf": SuggestionAction.REBUILD_PDF_TAGS,
        "unknown_pdf_tagging": SuggestionAction.MANUAL_REVIEW,
        "encrypted_pdf": SuggestionAction.MANUAL_REVIEW,
        "no_extractable_pdf_text": SuggestionAction.REQUEST_OCR,
        "missing_image_alt_text": SuggestionAction.GENERATE_ALT_TEXT,
        "weak_link_text": SuggestionAction.IMPROVE_LINK_TEXT,
        "skipped_heading_level": SuggestionAction.ADJUST_HEADING_LEVEL,
        "missing_heading_structure": SuggestionAction.CONFIRM_READING_ORDER,
        "missing_table_headers": SuggestionAction.CONFIRM_TABLE_HEADERS,
        "multi_column_reading_order_review": SuggestionAction.CONFIRM_READING_ORDER,
        "low_reading_order_confidence": SuggestionAction.CONFIRM_READING_ORDER,
    }.get(issue_type, SuggestionAction.MANUAL_REVIEW)


def _source_for_issue(issue_type: str) -> SuggestionSource:
    if issue_type in {"missing_image_alt_text", "weak_link_text", "missing_heading_structure"}:
        return SuggestionSource.AI_ASSISTED
    return SuggestionSource.RULE


def _proposed_value(
    document: DocumentModel,
    issue: AccessibilityIssue,
    element: DocumentElement | None,
) -> str | None:
    if issue.issue_type == "missing_document_title":
        return issue.suggested_fix or _first_meaningful_text(document)

    if issue.issue_type == "missing_document_language":
        return document.metadata.get("language") or "en-AU"

    if issue.issue_type == "untagged_pdf":
        return "Rebuild PDF logical structure tree from the internal document model."

    if issue.issue_type == "no_extractable_pdf_text":
        return "Run OCR before remediation."

    if issue.issue_type == "missing_image_alt_text":
        nearby = _element_nearby_text(element)
        if nearby:
            return f"Image related to: {nearby}"
        return "Describe the meaningful content or purpose of this image."

    if issue.issue_type == "weak_link_text":
        if element and element.href:
            parsed = urlparse(element.href)
            host = parsed.netloc or element.href
            nearby = str(element.metadata.get("nearby_text") or "").strip()
            if nearby:
                return nearby[:80]
            return f"Open {host}"
        return "Replace with descriptive link text."

    if issue.issue_type == "skipped_heading_level":
        return issue.suggested_fix

    if issue.issue_type == "missing_table_headers":
        return "Confirm the first row or column that should be treated as table headers."

    if issue.issue_type in {
        "missing_heading_structure",
        "multi_column_reading_order_review",
        "low_reading_order_confidence",
    }:
        return "Confirm the correct reading order and section structure before PDF rebuild."

    return issue.suggested_fix


def _suggestion_explanation(
    issue: AccessibilityIssue,
    action: SuggestionAction,
    proposed_value: str | None,
) -> str:
    if proposed_value:
        return f"{issue.explanation} Proposed action: {action.value}."
    return f"{issue.explanation} This issue needs manual review before remediation."


def _suggestion_confidence(issue: AccessibilityIssue, proposed_value: str | None) -> float:
    if not proposed_value:
        return min(issue.confidence, 0.4)
    if issue.automation_status == AutomationStatus.AUTO_FIXABLE:
        return max(issue.confidence, 0.85)
    return issue.confidence


def _find_element(document: DocumentModel, issue: AccessibilityIssue) -> DocumentElement | None:
    source = issue.source
    element_scoped_issue = issue.issue_type in {
        "missing_image_alt_text",
        "weak_link_text",
        "missing_table_headers",
        "low_reading_order_confidence",
        "skipped_heading_level",
    }
    for element in document.walk():
        if source.element_id and element.source.element_id == source.element_id:
            return element
        if source.page_number and element.source.page_number == source.page_number and source.bbox and element.source.bbox == source.bbox:
            return element
        if element_scoped_issue and element.source == source:
            return element
    return None


def _first_meaningful_text(document: DocumentModel) -> str | None:
    for element in document.walk():
        text = element.text.strip()
        if text:
            return text[:80]
    return None


def _element_nearby_text(element: DocumentElement | None) -> str:
    if not element:
        return ""
    nearby = str(element.metadata.get("nearby_text") or "").strip()
    if nearby:
        return nearby[:160]
    return element.text.strip()[:160]
