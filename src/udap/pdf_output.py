"""PDF output generation for Milestone 5."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from textwrap import wrap
from uuid import uuid4

from .extractors import load_pdf
from .models import (
    AccessibilityIssue,
    AnalysisResult,
    AutomationStatus,
    DocumentElement,
    ElementType,
    IssueStatus,
    OutputArtifact,
    OutputArtifactType,
    RemediationSuggestion,
    SuggestionAction,
)
from .pdf_tagging import PdfTaggingError, apply_minimal_structure_tree
from .pdf_validation import validate_generated_pdf_structure, validate_pdf_ua, validation_to_dict
from .pipeline import analyse_document, build_validation_report


class PdfGenerationError(RuntimeError):
    pass


def generate_remediated_pdf_outputs(
    result: AnalysisResult,
    output_dir: str | Path = ".local/outputs",
) -> list[OutputArtifact]:
    pdf_artifact = generate_remediated_pdf(result, output_dir=output_dir)
    report_artifact = generate_accessibility_report_artifact(pdf_artifact)
    return [pdf_artifact, report_artifact]


def generate_remediated_pdf(
    result: AnalysisResult,
    output_dir: str | Path = ".local/outputs",
) -> OutputArtifact:
    """Generate a first-pass remediated PDF from a reviewed analysis result.

    This is intentionally conservative: it rebuilds readable text content,
    writes title/language metadata, preserves simple links, and validates the
    generated PDF through the existing analysis pipeline. It does not yet claim
    full PDF/UA tagging.
    """

    try:
        import pymupdf
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise PdfGenerationError("PDF output generation requires PyMuPDF.") from exc

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    title = _resolved_value(result, SuggestionAction.SET_DOCUMENT_TITLE) or result.document.title
    title = title or _fallback_title(result)
    language = _resolved_value(result, SuggestionAction.SET_DOCUMENT_LANGUAGE) or result.document.language
    language = language or "en-AU"

    filename = _output_filename(result.document.original_filename)
    path = output_root / filename

    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    cursor_y = 72.0

    rendered_mappings: list[dict[str, bool | int | str | None]] = []
    role_counts: dict[str, int] = {}
    for element in _content_elements(result.document.walk()):
        page, cursor_y = _ensure_space(doc, page, cursor_y)
        page_index = page.number
        alt_text = _resolved_image_alt_text(result, element)
        table_rows = _table_rows_for_element(element)
        cursor_y, block_count = _write_element(
            page,
            element,
            cursor_y,
            pymupdf,
            alt_text=alt_text,
            table_rows=table_rows,
        )
        role = _pdf_role_for_element(element)
        role_counts[role] = role_counts.get(role, 0) + 1
        rendered_mappings.append(
            {
                "element_id": element.id,
                "element_type": element.type.value,
                "pdf_role": role,
                "text_preview": element.text[:80],
                "page_index": page_index,
                "content_block_count": block_count,
                "alt_text": alt_text,
                "decorative": element.decorative,
                "table_rows": table_rows,
                "table_header_count": len(element.table_headers),
            }
        )

    doc.set_metadata({"title": title})
    doc.xref_set_key(doc.pdf_catalog(), "Lang", f"({_escape_pdf_string(language)})")
    structure_plan = _build_structure_plan(
        role_counts=role_counts,
        mappings=rendered_mappings,
        status="embedded_minimal",
    )
    doc.save(path)
    doc.close()

    try:
        apply_minimal_structure_tree(path, structure_plan)
    except PdfTaggingError as exc:
        structure_plan = _mark_structure_plan_failed(structure_plan, str(exc))

    generated_document = load_pdf(path)
    generated_analysis = analyse_document(generated_document)
    validation = build_validation_report(generated_analysis)
    validation["remediation_summary"] = _build_remediation_summary(result, generated_analysis)
    validation["pdf_ua"] = validation_to_dict(validate_pdf_ua(path))
    validation["structure_plan"] = structure_plan
    validation["pdf_structure"] = validate_generated_pdf_structure(path, structure_plan)

    return OutputArtifact(
        id=str(uuid4()),
        type=OutputArtifactType.ACCESSIBLE_PDF,
        filename=filename,
        path=str(path),
        created_at=datetime.now(UTC).isoformat(),
        validation_report=validation,
    )


def generate_accessibility_report_artifact(pdf_artifact: OutputArtifact) -> OutputArtifact:
    report_path = _report_path_for_pdf(pdf_artifact.path)
    report_payload = {
        "artifact_type": OutputArtifactType.ACCESSIBILITY_REPORT.value,
        "generated_at": datetime.now(UTC).isoformat(),
        "source_artifact": {
            "id": pdf_artifact.id,
            "type": pdf_artifact.type.value,
            "filename": pdf_artifact.filename,
            "path": pdf_artifact.path,
            "created_at": pdf_artifact.created_at,
        },
        "validation_report": pdf_artifact.validation_report,
    }
    report_path.write_text(
        json.dumps(report_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return OutputArtifact(
        id=str(uuid4()),
        type=OutputArtifactType.ACCESSIBILITY_REPORT,
        filename=report_path.name,
        path=str(report_path),
        created_at=report_payload["generated_at"],
        validation_report=report_payload,
    )


def _report_path_for_pdf(path: str | Path) -> Path:
    source = Path(path)
    stem = source.stem.removesuffix("_accessible")
    return source.with_name(f"{stem}_accessibility_report.json")


def _resolved_value(result: AnalysisResult, action: SuggestionAction) -> str | None:
    suggestion_by_id = {suggestion.id: suggestion for suggestion in result.suggestions}
    for event in reversed(result.audit_events):
        if not event.suggestion_id:
            continue
        suggestion = suggestion_by_id.get(event.suggestion_id)
        if not suggestion or suggestion.action != action:
            continue
        if event.metadata.get("decision") not in {"accept", "edit"}:
            continue
        final_value = event.metadata.get("final_value")
        if isinstance(final_value, str) and final_value.strip():
            return final_value.strip()
        if suggestion.proposed_value:
            return suggestion.proposed_value.strip()
    return None


def _build_remediation_summary(
    source_result: AnalysisResult,
    generated_result: AnalysisResult,
) -> dict:
    generated_issue_types = {issue.issue_type for issue in generated_result.issues}
    rejected_issues = [
        issue for issue in source_result.issues if issue.final_status == IssueStatus.REJECTED
    ]
    fixed_issues = [
        issue
        for issue in source_result.issues
        if issue.final_status != IssueStatus.REJECTED and issue.issue_type not in generated_issue_types
    ]
    remaining_issues = list(generated_result.issues)
    manual_review_items = [
        issue
        for issue in remaining_issues
        if issue.automation_status
        in {
            AutomationStatus.NEEDS_USER_CONFIRMATION,
            AutomationStatus.CANNOT_AUTOMATE,
        }
    ]

    return {
        "statement": (
            "Generated output was analysed after remediation; legal compliance is not guaranteed."
        ),
        "fixed_issue_count": len(fixed_issues),
        "remaining_issue_count": len(remaining_issues),
        "manual_review_count": len(manual_review_items),
        "rejected_issue_count": len(rejected_issues),
        "fixed_issue_type_counts": _issue_type_counts(fixed_issues),
        "remaining_issue_type_counts": _issue_type_counts(remaining_issues),
        "manual_review_type_counts": _issue_type_counts(manual_review_items),
        "rejected_issue_type_counts": _issue_type_counts(rejected_issues),
        "fixed_issues": [_issue_report_item(issue) for issue in fixed_issues],
        "remaining_issues": [_issue_report_item(issue) for issue in remaining_issues],
        "manual_review_items": [_issue_report_item(issue) for issue in manual_review_items],
        "rejected_issues": [_issue_report_item(issue) for issue in rejected_issues],
    }


def _issue_type_counts(issues: list[AccessibilityIssue]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for issue in issues:
        counts[issue.issue_type] = counts.get(issue.issue_type, 0) + 1
    return counts


def _issue_report_item(issue: AccessibilityIssue) -> dict[str, str | float | None]:
    return {
        "id": issue.id,
        "issue_type": issue.issue_type,
        "severity": issue.severity.value,
        "automation_status": issue.automation_status.value,
        "final_status": issue.final_status.value,
        "explanation": issue.explanation,
        "suggested_fix": issue.suggested_fix,
        "confidence": issue.confidence,
    }


def _resolved_image_alt_text(result: AnalysisResult, element: DocumentElement) -> str | None:
    if element.type != ElementType.IMAGE:
        return None
    if element.decorative:
        return ""

    suggestion_by_id = {suggestion.id: suggestion for suggestion in result.suggestions}
    issue_by_id = {issue.id: issue for issue in result.issues}
    for event in reversed(result.audit_events):
        if not event.suggestion_id:
            continue
        suggestion = suggestion_by_id.get(event.suggestion_id)
        if not _is_alt_text_suggestion_for_element(suggestion, issue_by_id, element):
            continue
        if event.metadata.get("decision") not in {"accept", "edit"}:
            continue
        final_value = event.metadata.get("final_value")
        if isinstance(final_value, str) and final_value.strip():
            return final_value.strip()
        if suggestion and suggestion.proposed_value and suggestion.proposed_value.strip():
            return suggestion.proposed_value.strip()

    if element.alt_text and element.alt_text.strip():
        return element.alt_text.strip()
    return None


def _is_alt_text_suggestion_for_element(
    suggestion: RemediationSuggestion | None,
    issue_by_id: dict[str, AccessibilityIssue],
    element: DocumentElement,
) -> bool:
    if suggestion is None or suggestion.action != SuggestionAction.GENERATE_ALT_TEXT:
        return False
    issue = issue_by_id.get(suggestion.issue_id)
    if issue is None:
        return False
    source = getattr(issue, "source", None)
    if source is None:
        return False
    if source.element_id and source.element_id == element.source.element_id:
        return True
    if source.page_number and source.page_number == element.source.page_number:
        return source.bbox is None or source.bbox == element.source.bbox
    return source == element.source


def _fallback_title(result: AnalysisResult) -> str:
    for element in result.document.walk():
        text = element.text.strip()
        if text:
            return text[:80]
    return "Accessible Document"


def _output_filename(original_filename: str) -> str:
    stem = Path(original_filename).stem or "document"
    safe = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in stem)
    return f"{safe}_accessible.pdf"


def _content_elements(elements: list[DocumentElement]) -> list[DocumentElement]:
    return [
        element
        for element in elements
        if element.type
        in {
            ElementType.HEADING,
            ElementType.PARAGRAPH,
            ElementType.LIST_ITEM,
            ElementType.TABLE,
            ElementType.IMAGE,
            ElementType.LINK,
        }
        and _has_renderable_content(element)
    ]


def _has_renderable_content(element: DocumentElement) -> bool:
    if element.type == ElementType.IMAGE:
        return True
    if element.type == ElementType.TABLE:
        return bool(_table_rows_for_element(element))
    return bool(element.text.strip())


def _build_structure_plan(
    *,
    role_counts: dict[str, int],
    mappings: list[dict[str, bool | int | str | None]],
    status: str = "planned",
) -> dict:
    return {
        "status": status,
        "details": (
            "Generated PDF text is rebuilt from the internal document model. "
            "A minimal logical structure tree is embedded for headings, paragraphs, "
            "links, lists, figures, and simple tables. Full PDF/UA tagging is not yet claimed."
        ),
        "role_counts": role_counts,
        "mappings": mappings,
    }


def _mark_structure_plan_failed(structure_plan: dict, reason: str) -> dict:
    failed = dict(structure_plan)
    failed["status"] = "failed"
    failed["details"] = f"Minimal structure tagging failed: {reason}"
    return failed


def _pdf_role_for_element(element: DocumentElement) -> str:
    if element.type == ElementType.HEADING:
        level = element.heading_level or 1
        return f"H{max(1, min(level, 6))}"
    if element.type == ElementType.LINK:
        return "Link"
    if element.type == ElementType.LIST_ITEM:
        return "LI"
    if element.type == ElementType.TABLE:
        return "Table"
    if element.type == ElementType.IMAGE:
        return "Figure"
    return "P"


def _ensure_space(doc, page, cursor_y: float):
    if cursor_y <= 760:
        return page, cursor_y
    page = doc.new_page(width=595, height=842)
    return page, 72.0


def _write_element(
    page,
    element: DocumentElement,
    cursor_y: float,
    pymupdf,
    *,
    alt_text: str | None = None,
    table_rows: list[list[str]] | None = None,
) -> tuple[float, int]:
    left = 72.0
    right = 523.0
    width_chars = 72
    font_size = 11
    line_height = 16

    if element.type == ElementType.HEADING:
        font_size = 18 if element.heading_level == 1 else 14
        line_height = 24 if element.heading_level == 1 else 20

    if element.type == ElementType.IMAGE:
        return _write_image_placeholder(page, element, cursor_y, pymupdf, alt_text=alt_text)
    if element.type == ElementType.TABLE:
        return _write_table(page, cursor_y, pymupdf, rows=table_rows or [])

    text = element.text.replace("\n", " ").strip()
    lines = wrap(text, width=width_chars) or [text]

    for line in lines:
        page.insert_text((left, cursor_y), line, fontsize=font_size)
        cursor_y += line_height

    if element.type == ElementType.LINK and element.href:
        rect = pymupdf.Rect(left, cursor_y - line_height, right, cursor_y)
        page.insert_link({"kind": pymupdf.LINK_URI, "from": rect, "uri": element.href})

    return cursor_y + 8, len(lines)


def _write_image_placeholder(
    page,
    element: DocumentElement,
    cursor_y: float,
    pymupdf,
    *,
    alt_text: str | None,
) -> tuple[float, int]:
    left = 72.0
    width = 451.0
    height = 64.0
    rect = pymupdf.Rect(left, cursor_y, left + width, cursor_y + height)
    page.draw_rect(rect, color=(0.35, 0.35, 0.35), width=0.75)

    if element.decorative:
        label = "Decorative image"
    elif alt_text:
        label = f"Figure: {alt_text}"
    else:
        label = "Figure: alt text requires review"

    lines = wrap(label.replace("\n", " ").strip(), width=68) or [label]
    text_y = cursor_y + 20
    for line in lines[:3]:
        page.insert_text((left + 10, text_y), line, fontsize=10)
        text_y += 14

    return cursor_y + height + 12, min(len(lines), 3)


def _write_table(page, cursor_y: float, pymupdf, *, rows: list[list[str]]) -> tuple[float, int]:
    if not rows:
        return cursor_y, 0

    left = 72.0
    width = 451.0
    row_height = 24.0
    column_count = max(len(row) for row in rows)
    column_width = width / max(column_count, 1)
    font_size = 9
    content_blocks = 0

    for row_index, row in enumerate(rows):
        y = cursor_y + row_index * row_height
        for column_index in range(column_count):
            x = left + column_index * column_width
            rect = pymupdf.Rect(x, y, x + column_width, y + row_height)
            page.draw_rect(rect, color=(0.35, 0.35, 0.35), width=0.5)
            cell_text = row[column_index] if column_index < len(row) else ""
            if cell_text:
                page.insert_text((x + 4, y + 15), _fit_cell_text(cell_text), fontsize=font_size)
                content_blocks += 1

    return cursor_y + len(rows) * row_height + 12, content_blocks


def _table_rows_for_element(element: DocumentElement) -> list[list[str]]:
    if element.type != ElementType.TABLE:
        return []

    parsed_rows = _parse_table_rows(element.text)
    headers = [header.strip() for header in element.table_headers if header.strip()]
    if not headers:
        return parsed_rows

    if parsed_rows and _normalise_row(parsed_rows[0]) == _normalise_row(headers):
        return parsed_rows
    return [headers, *parsed_rows]


def _parse_table_rows(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if "\t" in stripped:
            cells = stripped.split("\t")
        elif "|" in stripped:
            cells = stripped.strip("|").split("|")
        elif "," in stripped:
            cells = stripped.split(",")
        else:
            cells = _split_on_repeated_spaces(stripped)
        row = [cell.strip() for cell in cells if cell.strip()]
        if row:
            rows.append(row)
    return rows


def _split_on_repeated_spaces(value: str) -> list[str]:
    return re.split(r"\s{2,}", value)


def _normalise_row(row: list[str]) -> list[str]:
    return [cell.strip().casefold() for cell in row]


def _fit_cell_text(value: str) -> str:
    text = value.replace("\n", " ").strip()
    return text if len(text) <= 28 else f"{text[:25]}..."


def _escape_pdf_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
