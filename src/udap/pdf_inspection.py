"""PDF inspection helpers for the PDF-first MVP path."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import PdfInspection


class PdfInspectionDependencyError(RuntimeError):
    pass


def inspect_pdf(path: str | Path) -> PdfInspection:
    """Extract PDF accessibility signals that are available without remediation.

    This is not a full PDF/UA validator. It records the signals the rest of the
    MVP pipeline needs: document metadata, tagging indicators, page count, links,
    images, and extraction warnings.
    """

    source = Path(path)
    inspection = _inspect_with_pypdf(source)
    _augment_with_pymupdf(source, inspection)
    return inspection


def _inspect_with_pypdf(path: Path) -> PdfInspection:
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except ImportError as exc:
        raise PdfInspectionDependencyError(
            "PDF inspection requires pypdf. Install project dependencies first."
        ) from exc

    reader = PdfReader(str(path))
    metadata = reader.metadata or {}
    inspection = PdfInspection(
        page_count=len(reader.pages),
        is_encrypted=bool(reader.is_encrypted),
        title=_clean_pdf_value(_metadata_get(metadata, "/Title")),
    )

    if reader.is_encrypted:
        inspection.extraction_warnings.append("PDF is encrypted; accessibility inspection is limited.")
        return inspection

    root = _resolve(reader.trailer.get("/Root"))
    if isinstance(root, dict):
        inspection.language = _clean_pdf_value(root.get("/Lang"))
        inspection.has_struct_tree = root.get("/StructTreeRoot") is not None

        mark_info = _resolve(root.get("/MarkInfo"))
        if isinstance(mark_info, dict):
            inspection.mark_info_marked = bool(mark_info.get("/Marked"))
        else:
            inspection.mark_info_marked = False

    return inspection


def _augment_with_pymupdf(path: Path, inspection: PdfInspection) -> None:
    try:
        import pymupdf as fitz  # type: ignore[import-not-found]
    except ImportError:
        try:
            import fitz  # type: ignore[import-not-found,no-redef]
        except ImportError:
            inspection.extraction_warnings.append(
                "PyMuPDF is not installed; text block, image, and link extraction is unavailable."
            )
            return

    try:
        pdf = fitz.open(path)
    except RuntimeError as exc:  # pragma: no cover - library-specific failure detail
        inspection.extraction_warnings.append(f"PyMuPDF could not open the PDF: {exc}")
        return

    if not inspection.title:
        metadata = pdf.metadata or {}
        inspection.title = _clean_pdf_value(metadata.get("title"))

    for page in pdf:
        try:
            blocks = page.get_text("blocks")
            inspection.text_block_count += len([block for block in blocks if _block_has_text(block)])
        except RuntimeError:
            inspection.extraction_warnings.append(
                f"Could not extract text blocks from page {page.number + 1}."
            )

        try:
            inspection.image_count += len(page.get_images(full=True))
        except RuntimeError:
            inspection.extraction_warnings.append(f"Could not extract images from page {page.number + 1}.")

        try:
            inspection.link_count += len(page.get_links())
        except RuntimeError:
            inspection.extraction_warnings.append(f"Could not extract links from page {page.number + 1}.")


def _resolve(value: Any) -> Any:
    if hasattr(value, "get_object"):
        return value.get_object()
    return value


def _metadata_get(metadata: Any, key: str) -> Any:
    if hasattr(metadata, "get"):
        return metadata.get(key)
    return None


def _clean_pdf_value(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _block_has_text(block: Any) -> bool:
    if not isinstance(block, (list, tuple)) or len(block) < 5:
        return False
    return bool(str(block[4]).strip())
