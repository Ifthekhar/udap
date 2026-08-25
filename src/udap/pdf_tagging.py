"""Minimal PDF logical structure tagging.

This module creates a first structure tree for generated PDFs. It is a stepping
stone toward PDF/UA, not a full compliance implementation: content streams are
not yet marked with MCIDs and the parent tree is intentionally minimal.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


class PdfTaggingError(RuntimeError):
    pass


def apply_minimal_structure_tree(path: str | Path, structure_plan: dict[str, Any]) -> None:
    try:
        from pypdf import PdfReader, PdfWriter
        from pypdf.generic import (
            ArrayObject,
            BooleanObject,
            DictionaryObject,
            NameObject,
            NumberObject,
            TextStringObject,
        )
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise PdfTaggingError("PDF tagging requires pypdf.") from exc

    source = Path(path)
    reader = PdfReader(str(source))
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)

    root = writer.root_object
    root[NameObject("/MarkInfo")] = DictionaryObject({NameObject("/Marked"): BooleanObject(True)})

    parent_tree = DictionaryObject({NameObject("/Nums"): ArrayObject()})
    parent_tree_ref = writer._add_object(parent_tree)

    struct_tree = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/StructTreeRoot"),
            NameObject("/K"): ArrayObject(),
            NameObject("/ParentTree"): parent_tree_ref,
        }
    )
    struct_tree_ref = writer._add_object(struct_tree)

    children = ArrayObject()
    page_ref = _first_page_reference(writer)
    for mapping in structure_plan.get("mappings", []):
        role = str(mapping.get("pdf_role") or "P")
        element = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/StructElem"),
                NameObject("/S"): NameObject(f"/{role}"),
                NameObject("/P"): struct_tree_ref,
                NameObject("/T"): TextStringObject(str(mapping.get("text_preview") or role)),
            }
        )
        if page_ref is not None:
            element[NameObject("/Pg")] = page_ref
        children.append(writer._add_object(element))

    struct_tree[NameObject("/K")] = children
    root[NameObject("/StructTreeRoot")] = struct_tree_ref

    if writer.pages:
        for index, page in enumerate(writer.pages):
            page[NameObject("/StructParents")] = NumberObject(index)

    with NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        temp_path = Path(tmp.name)
    try:
        with temp_path.open("wb") as handle:
            writer.write(handle)
        temp_path.replace(source)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _first_page_reference(writer) -> object | None:
    if not writer.pages:
        return None
    page = writer.pages[0]
    return getattr(page, "indirect_reference", None)
