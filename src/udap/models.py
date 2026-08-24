"""Core data structures for the accessibility transformation pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4


class ElementType(StrEnum):
    DOCUMENT = "document"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    LIST_ITEM = "list_item"
    TABLE = "table"
    IMAGE = "image"
    LINK = "link"
    FORM_FIELD = "form_field"


class IssueSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AutomationStatus(StrEnum):
    AUTO_FIXABLE = "auto_fixable"
    NEEDS_USER_CONFIRMATION = "needs_user_confirmation"
    CANNOT_AUTOMATE = "cannot_automate"


class IssueStatus(StrEnum):
    OPEN = "open"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FIXED = "fixed"
    UNRESOLVED = "unresolved"


class SuggestionAction(StrEnum):
    SET_DOCUMENT_TITLE = "set_document_title"
    SET_DOCUMENT_LANGUAGE = "set_document_language"
    REBUILD_PDF_TAGS = "rebuild_pdf_tags"
    REQUEST_OCR = "request_ocr"
    GENERATE_ALT_TEXT = "generate_alt_text"
    IMPROVE_LINK_TEXT = "improve_link_text"
    ADJUST_HEADING_LEVEL = "adjust_heading_level"
    CONFIRM_TABLE_HEADERS = "confirm_table_headers"
    CONFIRM_READING_ORDER = "confirm_reading_order"
    MANUAL_REVIEW = "manual_review"


class SuggestionSource(StrEnum):
    RULE = "rule"
    AI_ASSISTED = "ai_assisted"
    USER = "user"


class ReviewDecision(StrEnum):
    ACCEPT = "accept"
    EDIT = "edit"
    REJECT = "reject"


class AuditEventType(StrEnum):
    SUGGESTION_CREATED = "suggestion_created"
    USER_DECISION_RECORDED = "user_decision_recorded"


class JobStatus(StrEnum):
    AWAITING_REVIEW = "awaiting_review"
    REVIEWED = "reviewed"


@dataclass(frozen=True)
class SourceLocation:
    """Where an extracted item came from in the source document."""

    page_number: int | None = None
    element_id: str | None = None
    description: str | None = None
    bbox: tuple[float, float, float, float] | None = None


@dataclass
class DocumentElement:
    """A neutral representation of document content across PDF, DOCX, and later formats."""

    type: ElementType
    text: str = ""
    id: str = field(default_factory=lambda: str(uuid4()))
    source: SourceLocation = field(default_factory=SourceLocation)
    confidence: float = 1.0
    children: list[DocumentElement] = field(default_factory=list)

    # Accessibility and structure hints.
    heading_level: int | None = None
    language: str | None = None
    alt_text: str | None = None
    decorative: bool = False
    href: str | None = None
    table_headers: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PdfInspection:
    """PDF-specific accessibility signals extracted from the source file."""

    page_count: int = 0
    is_encrypted: bool = False
    has_struct_tree: bool | None = None
    mark_info_marked: bool | None = None
    language: str | None = None
    title: str | None = None
    image_count: int = 0
    link_count: int = 0
    text_block_count: int = 0
    heading_candidate_count: int = 0
    table_candidate_count: int = 0
    pages_with_multiple_columns: list[int] = field(default_factory=list)
    extraction_warnings: list[str] = field(default_factory=list)

    @property
    def is_tagged(self) -> bool | None:
        if self.has_struct_tree is None and self.mark_info_marked is None:
            return None
        return bool(self.has_struct_tree and self.mark_info_marked)


@dataclass
class DocumentModel:
    """A source-independent document model used for analysis, remediation, and rebuild."""

    original_filename: str
    source_format: Literal["pdf", "docx", "unknown"]
    title: str | None = None
    language: str | None = None
    elements: list[DocumentElement] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    pdf: PdfInspection | None = None

    def walk(self) -> list[DocumentElement]:
        flattened: list[DocumentElement] = []

        def visit(element: DocumentElement) -> None:
            flattened.append(element)
            for child in element.children:
                visit(child)

        for element in self.elements:
            visit(element)

        return flattened


@dataclass(frozen=True)
class AccessibilityRule:
    id: str
    standard: str
    criterion: str
    title: str
    level: Literal["A", "AA", "AAA"]
    requirement: str
    test_method: str
    remediation: str


@dataclass
class AccessibilityIssue:
    id: str
    rule_id: str
    issue_type: str
    severity: IssueSeverity
    source: SourceLocation
    explanation: str
    suggested_fix: str | None
    confidence: float
    automation_status: AutomationStatus
    final_status: IssueStatus = IssueStatus.OPEN


@dataclass
class RemediationSuggestion:
    id: str
    issue_id: str
    action: SuggestionAction
    source: SuggestionSource
    proposed_value: str | None
    explanation: str
    requires_user_confirmation: bool
    confidence: float


@dataclass
class UserDecision:
    suggestion_id: str
    issue_id: str
    decision: ReviewDecision
    final_value: str | None = None
    reviewer_note: str | None = None


@dataclass
class AuditEvent:
    type: AuditEventType
    issue_id: str
    suggestion_id: str | None
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisResult:
    document: DocumentModel
    standard: str
    issues: list[AccessibilityIssue]
    suggestions: list[RemediationSuggestion] = field(default_factory=list)
    audit_events: list[AuditEvent] = field(default_factory=list)

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    def counts_by_status(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for issue in self.issues:
            key = issue.automation_status.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    def counts_by_severity(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for issue in self.issues:
            key = issue.severity.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    def counts_by_issue_type(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for issue in self.issues:
            counts[issue.issue_type] = counts.get(issue.issue_type, 0) + 1
        return counts

    def suggestion_count(self) -> int:
        return len(self.suggestions)


@dataclass
class AnalysisJob:
    id: str
    result: AnalysisResult
    status: JobStatus
    created_at: str
    updated_at: str
