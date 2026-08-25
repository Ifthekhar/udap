"""PDF output generation for Milestone 5."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from textwrap import wrap
from uuid import uuid4

from .extractors import load_pdf
from .models import (
    AnalysisResult,
    DocumentElement,
    ElementType,
    OutputArtifact,
    OutputArtifactType,
    SuggestionAction,
)
from .pdf_tagging import PdfTaggingError, apply_minimal_structure_tree
from .pdf_validation import validate_pdf_ua, validation_to_dict
from .pipeline import analyse_document, build_validation_report


class PdfGenerationError(RuntimeError):
    pass


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

    rendered_mappings: list[dict[str, int | str | None]] = []
    role_counts: dict[str, int] = {}
    for element in _content_elements(result.document.walk()):
        page, cursor_y = _ensure_space(doc, page, cursor_y)
        page_index = page.number
        cursor_y, block_count = _write_element(page, element, cursor_y, pymupdf)
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
    validation = build_validation_report(analyse_document(generated_document))
    validation["pdf_ua"] = validation_to_dict(validate_pdf_ua(path))
    validation["structure_plan"] = structure_plan

    return OutputArtifact(
        id=str(uuid4()),
        type=OutputArtifactType.ACCESSIBLE_PDF,
        filename=filename,
        path=str(path),
        created_at=datetime.now(UTC).isoformat(),
        validation_report=validation,
    )


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
            ElementType.LINK,
        }
        and element.text.strip()
    ]


def _build_structure_plan(
    *,
    role_counts: dict[str, int],
    mappings: list[dict[str, int | str | None]],
    status: str = "planned",
) -> dict:
    return {
        "status": status,
        "details": (
            "Generated PDF text is rebuilt from the internal document model. "
            "A minimal logical structure tree is embedded for headings, paragraphs, "
            "links, lists, and table placeholders. Full PDF/UA tagging is not yet claimed."
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
    return "P"


def _ensure_space(doc, page, cursor_y: float):
    if cursor_y <= 760:
        return page, cursor_y
    page = doc.new_page(width=595, height=842)
    return page, 72.0


def _write_element(page, element: DocumentElement, cursor_y: float, pymupdf) -> tuple[float, int]:
    left = 72.0
    right = 523.0
    width_chars = 72
    font_size = 11
    line_height = 16

    if element.type == ElementType.HEADING:
        font_size = 18 if element.heading_level == 1 else 14
        line_height = 24 if element.heading_level == 1 else 20

    text = element.text.replace("\n", " ").strip()
    lines = wrap(text, width=width_chars) or [text]

    for line in lines:
        page.insert_text((left, cursor_y), line, fontsize=font_size)
        cursor_y += line_height

    if element.type == ElementType.LINK and element.href:
        rect = pymupdf.Rect(left, cursor_y - line_height, right, cursor_y)
        page.insert_link({"kind": pymupdf.LINK_URI, "from": rect, "uri": element.href})

    return cursor_y + 8, len(lines)


def _escape_pdf_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
