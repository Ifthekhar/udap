"""Deterministic MVP accessibility checks over the neutral document model."""

from __future__ import annotations

from uuid import uuid4

from .models import (
    AccessibilityIssue,
    AutomationStatus,
    DocumentElement,
    DocumentModel,
    ElementType,
    IssueSeverity,
    SourceLocation,
)

GENERIC_LINK_TEXT = {
    "click here",
    "here",
    "link",
    "learn more",
    "more",
    "read more",
    "view",
    "download",
}


def evaluate_document(document: DocumentModel) -> list[AccessibilityIssue]:
    """Run the MVP rule subset against a document model."""

    issues: list[AccessibilityIssue] = []
    issues.extend(_check_pdf_inspection(document))
    issues.extend(_check_title(document))
    issues.extend(_check_language(document))
    issues.extend(_check_headings(document))

    for element in document.walk():
        if element.type == ElementType.IMAGE:
            issues.extend(_check_image_alt_text(element))
        elif element.type == ElementType.LINK:
            issues.extend(_check_link_text(element))
        elif element.type == ElementType.TABLE:
            issues.extend(_check_table_headers(element))

        issues.extend(_check_reading_order_confidence(element))

    return issues


def _issue(
    *,
    rule_id: str,
    issue_type: str,
    severity: IssueSeverity,
    source: SourceLocation,
    explanation: str,
    suggested_fix: str | None,
    confidence: float,
    automation_status: AutomationStatus,
) -> AccessibilityIssue:
    return AccessibilityIssue(
        id=str(uuid4()),
        rule_id=rule_id,
        issue_type=issue_type,
        severity=severity,
        source=source,
        explanation=explanation,
        suggested_fix=suggested_fix,
        confidence=confidence,
        automation_status=automation_status,
    )


def _check_title(document: DocumentModel) -> list[AccessibilityIssue]:
    if document.title and document.title.strip():
        return []

    fallback_title = _first_text(document.elements)
    suggested = fallback_title[:80] if fallback_title else None
    return [
        _issue(
            rule_id="wcag.document.title",
            issue_type="missing_document_title",
            severity=IssueSeverity.HIGH,
            source=SourceLocation(description="document metadata"),
            explanation="The document does not have a clear title in the extracted metadata.",
            suggested_fix=suggested,
            confidence=0.85 if suggested else 0.6,
            automation_status=AutomationStatus.AUTO_FIXABLE
            if suggested
            else AutomationStatus.NEEDS_USER_CONFIRMATION,
        )
    ]


def _check_pdf_inspection(document: DocumentModel) -> list[AccessibilityIssue]:
    if document.source_format != "pdf" or document.pdf is None:
        return []

    pdf = document.pdf
    issues: list[AccessibilityIssue] = []

    if pdf.is_encrypted:
        issues.append(
            _issue(
                rule_id="pdf.encryption",
                issue_type="encrypted_pdf",
                severity=IssueSeverity.CRITICAL,
                source=SourceLocation(description="PDF security settings"),
                explanation="The PDF is encrypted, so the platform cannot reliably inspect or remediate it.",
                suggested_fix="Upload an unlocked copy of the PDF or provide the password.",
                confidence=1.0,
                automation_status=AutomationStatus.CANNOT_AUTOMATE,
            )
        )
        return issues

    if pdf.is_tagged is False:
        issues.append(
            _issue(
                rule_id="pdf.tags.present",
                issue_type="untagged_pdf",
                severity=IssueSeverity.CRITICAL,
                source=SourceLocation(description="PDF structure tree"),
                explanation="The PDF does not appear to have a complete logical tag structure.",
                suggested_fix="Rebuild the PDF with headings, paragraphs, lists, tables, links, and images mapped into a logical tag tree.",
                confidence=0.95,
                automation_status=AutomationStatus.AUTO_FIXABLE,
            )
        )
    elif pdf.is_tagged is None:
        issues.append(
            _issue(
                rule_id="pdf.tags.present",
                issue_type="unknown_pdf_tagging",
                severity=IssueSeverity.HIGH,
                source=SourceLocation(description="PDF structure tree"),
                explanation="The platform could not determine whether this PDF has a logical tag structure.",
                suggested_fix="Run a PDF/UA validation pass and inspect the document structure tree.",
                confidence=0.5,
                automation_status=AutomationStatus.NEEDS_USER_CONFIRMATION,
            )
        )

    if pdf.page_count > 0 and pdf.text_block_count == 0:
        issues.append(
            _issue(
                rule_id="pdf.extractable_text",
                issue_type="no_extractable_pdf_text",
                severity=IssueSeverity.CRITICAL,
                source=SourceLocation(description="PDF text extraction"),
                explanation="No extractable text was found in the PDF, which usually means the document is scanned or image-only.",
                suggested_fix="Run OCR before remediation or request a source document with real text.",
                confidence=0.9,
                automation_status=AutomationStatus.NEEDS_USER_CONFIRMATION,
            )
        )

    if pdf.pages_with_multiple_columns:
        pages = ", ".join(str(page) for page in pdf.pages_with_multiple_columns)
        issues.append(
            _issue(
                rule_id="pdf.reading_order.multicolumn",
                issue_type="multi_column_reading_order_review",
                severity=IssueSeverity.HIGH,
                source=SourceLocation(description=f"PDF pages: {pages}"),
                explanation=(
                    "One or more pages appear to use multiple columns, so the extracted reading "
                    "order needs review before remediation."
                ),
                suggested_fix="Confirm or reconstruct the reading order for the listed pages.",
                confidence=0.75,
                automation_status=AutomationStatus.NEEDS_USER_CONFIRMATION,
            )
        )

    return issues


def _check_language(document: DocumentModel) -> list[AccessibilityIssue]:
    if document.language and document.language.strip():
        return []

    return [
        _issue(
            rule_id="wcag.document.language",
            issue_type="missing_document_language",
            severity=IssueSeverity.HIGH,
            source=SourceLocation(description="document metadata"),
            explanation="The default document language is not set.",
            suggested_fix="Set the document language, for example en-US or en-AU.",
            confidence=0.7,
            automation_status=AutomationStatus.NEEDS_USER_CONFIRMATION,
        )
    ]


def _check_headings(document: DocumentModel) -> list[AccessibilityIssue]:
    elements = document.walk()
    headings = [element for element in elements if element.type == ElementType.HEADING]
    paragraphs = [element for element in elements if element.type == ElementType.PARAGRAPH]
    issues: list[AccessibilityIssue] = []

    if not headings and len(paragraphs) >= 4:
        issues.append(
            _issue(
                rule_id="wcag.headings.present",
                issue_type="missing_heading_structure",
                severity=IssueSeverity.MEDIUM,
                source=SourceLocation(description="document structure"),
                explanation="The document has multiple text blocks but no detected heading structure.",
                suggested_fix="Infer headings from layout or ask the user to confirm section headings.",
                confidence=0.75,
                automation_status=AutomationStatus.NEEDS_USER_CONFIRMATION,
            )
        )

    previous_level: int | None = None
    for heading in headings:
        level = heading.heading_level
        if level is None:
            continue
        if previous_level is not None and level > previous_level + 1:
            issues.append(
                _issue(
                    rule_id="wcag.headings.order",
                    issue_type="skipped_heading_level",
                    severity=IssueSeverity.MEDIUM,
                    source=heading.source,
                    explanation=(
                        f"Heading level jumps from H{previous_level} to H{level}, "
                        "which can make the document structure unclear."
                    ),
                    suggested_fix=f"Review whether this should be H{previous_level + 1}.",
                    confidence=0.9,
                    automation_status=AutomationStatus.NEEDS_USER_CONFIRMATION,
                )
            )
        previous_level = level

    return issues


def _check_image_alt_text(element: DocumentElement) -> list[AccessibilityIssue]:
    if element.decorative or (element.alt_text and element.alt_text.strip()):
        return []

    return [
        _issue(
            rule_id="wcag.images.alt_text",
            issue_type="missing_image_alt_text",
            severity=IssueSeverity.HIGH,
            source=element.source,
            explanation="An image appears to be missing alternative text or decorative marking.",
            suggested_fix="Generate alt text from image content and ask the user to confirm it.",
            confidence=element.confidence,
            automation_status=AutomationStatus.NEEDS_USER_CONFIRMATION,
        )
    ]


def _check_link_text(element: DocumentElement) -> list[AccessibilityIssue]:
    text = element.text.strip()
    lower_text = text.lower()
    is_url_only = lower_text.startswith(("http://", "https://", "www."))

    if text and lower_text not in GENERIC_LINK_TEXT and not is_url_only:
        return []

    return [
        _issue(
            rule_id="wcag.links.meaningful_text",
            issue_type="weak_link_text",
            severity=IssueSeverity.MEDIUM,
            source=element.source,
            explanation="A link has empty, generic, or URL-only text.",
            suggested_fix="Replace the link text with a phrase that describes the destination.",
            confidence=0.9,
            automation_status=AutomationStatus.NEEDS_USER_CONFIRMATION,
        )
    ]


def _check_table_headers(element: DocumentElement) -> list[AccessibilityIssue]:
    if element.table_headers:
        return []

    return [
        _issue(
            rule_id="wcag.tables.headers",
            issue_type="missing_table_headers",
            severity=IssueSeverity.HIGH,
            source=element.source,
            explanation="A table does not have identifiable header cells.",
            suggested_fix="Infer simple headers from the first row or ask the user to confirm headers.",
            confidence=element.confidence,
            automation_status=AutomationStatus.NEEDS_USER_CONFIRMATION,
        )
    ]


def _check_reading_order_confidence(element: DocumentElement) -> list[AccessibilityIssue]:
    if element.confidence >= 0.6:
        return []

    return [
        _issue(
            rule_id="wcag.reading_order.confidence",
            issue_type="low_reading_order_confidence",
            severity=IssueSeverity.MEDIUM,
            source=element.source,
            explanation="The extracted reading order for this content is low confidence.",
            suggested_fix="Ask the user to review this section before generating the accessible PDF.",
            confidence=element.confidence,
            automation_status=AutomationStatus.NEEDS_USER_CONFIRMATION,
        )
    ]


def _first_text(elements: list[DocumentElement]) -> str | None:
    for element in elements:
        if element.text.strip():
            return element.text.strip()
        nested = _first_text(element.children)
        if nested:
            return nested
    return None
