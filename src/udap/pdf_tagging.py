"""Minimal PDF logical structure tagging with MCID associations.

This module creates a first structure tree for generated PDFs. It is a stepping
stone toward PDF/UA, not a full compliance implementation.
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
            DecodedStreamObject,
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
    parent_entries = ArrayObject()
    page = writer.pages[0] if writer.pages else None
    mappings = list(structure_plan.get("mappings", []))
    for mcid, mapping in enumerate(mappings):
        role = str(mapping.get("pdf_role") or "P")
        mcr = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/MCR"),
                NameObject("/MCID"): NumberObject(mcid),
            }
        )
        if page_ref is not None:
            mcr[NameObject("/Pg")] = page_ref

        element = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/StructElem"),
                NameObject("/S"): NameObject(f"/{role}"),
                NameObject("/P"): struct_tree_ref,
                NameObject("/T"): TextStringObject(str(mapping.get("text_preview") or role)),
                NameObject("/K"): mcr,
            }
        )
        if page_ref is not None:
            element[NameObject("/Pg")] = page_ref
        element_ref = writer._add_object(element)
        children.append(element_ref)
        parent_entries.append(element_ref)

    struct_tree[NameObject("/K")] = children
    parent_tree[NameObject("/Nums")] = ArrayObject([NumberObject(0), parent_entries])
    root[NameObject("/StructTreeRoot")] = struct_tree_ref

    if page is not None:
        page[NameObject("/StructParents")] = NumberObject(0)
        _replace_page_contents_with_marked_content(
            writer=writer,
            page=page,
            mcid_count=len(mappings),
            stream_cls=DecodedStreamObject,
            name_cls=NameObject,
        )

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


def _replace_page_contents_with_marked_content(
    *,
    writer,
    page,
    mcid_count: int,
    stream_cls,
    name_cls,
) -> None:
    content = page.get_contents()
    if content is None:
        return

    original = content.get_data()
    wrapped = _wrap_content_with_mcids(original, mcid_count)
    stream = stream_cls()
    stream.set_data(wrapped)
    page[name_cls("/Contents")] = writer._add_object(stream)


def _wrap_content_with_mcids(original: bytes, mcid_count: int) -> bytes:
    if mcid_count <= 0:
        return original

    # This first implementation associates the full page content with every
    # planned structure element. Later hardening will split content streams per
    # element so each MCID maps to only its own drawing operations.
    prefix = "".join(f"/P <</MCID {mcid}>> BDC\n" for mcid in range(mcid_count))
    suffix = "".join("EMC\n" for _ in range(mcid_count))
    return prefix.encode("ascii") + original + b"\n" + suffix.encode("ascii")
