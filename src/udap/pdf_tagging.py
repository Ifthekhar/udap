"""Minimal PDF logical structure tagging with MCID associations.

This module creates a first structure tree for generated PDFs. It is a stepping
stone toward PDF/UA, not a full compliance implementation.
"""

from __future__ import annotations

import re
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
    parent_tree_entries: dict[int, Any] = {}
    mcid_by_page: dict[int, int] = {}
    mappings = list(structure_plan.get("mappings", []))
    wrapping_plan_by_page: dict[int, list[dict[str, int]]] = {}
    link_annotations_by_page = _link_annotation_refs_by_page(writer)
    annotation_parent_key = len(writer.pages)
    mapping_index = 0
    while mapping_index < len(mappings):
        mapping = mappings[mapping_index]
        role = str(mapping.get("pdf_role") or "P")
        page_index = _mapping_page_index(mapping, page_count=len(writer.pages))
        page_ref = _page_reference(writer, page_index)
        if role == "LI":
            list_mappings: list[Any] = []
            while mapping_index < len(mappings):
                candidate = mappings[mapping_index]
                if str(candidate.get("pdf_role") or "P") != "LI":
                    break
                candidate_page_index = _mapping_page_index(candidate, page_count=len(writer.pages))
                if candidate_page_index != page_index:
                    break
                list_mappings.append(candidate)
                mapping_index += 1

            list_element = DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/StructElem"),
                    NameObject("/S"): NameObject("/L"),
                    NameObject("/P"): struct_tree_ref,
                    NameObject("/T"): TextStringObject("List"),
                    NameObject("/K"): ArrayObject(),
                }
            )
            if page_ref is not None:
                list_element[NameObject("/Pg")] = page_ref
            list_ref = writer._add_object(list_element)
            item_refs = ArrayObject()

            for list_mapping in list_mappings:
                mcid = mcid_by_page.get(page_index, 0)
                mcid_by_page[page_index] = mcid + 1
                mcr = DictionaryObject(
                    {
                        NameObject("/Type"): NameObject("/MCR"),
                        NameObject("/MCID"): NumberObject(mcid),
                    }
                )
                if page_ref is not None:
                    mcr[NameObject("/Pg")] = page_ref

                item_element = DictionaryObject(
                    {
                        NameObject("/Type"): NameObject("/StructElem"),
                        NameObject("/S"): NameObject("/LI"),
                        NameObject("/P"): list_ref,
                        NameObject("/T"): TextStringObject(
                            str(list_mapping.get("text_preview") or "List item")
                        ),
                        NameObject("/K"): ArrayObject(),
                    }
                )
                if page_ref is not None:
                    item_element[NameObject("/Pg")] = page_ref
                item_ref = writer._add_object(item_element)

                label_element = DictionaryObject(
                    {
                        NameObject("/Type"): NameObject("/StructElem"),
                        NameObject("/S"): NameObject("/Lbl"),
                        NameObject("/P"): item_ref,
                        NameObject("/T"): TextStringObject(
                            str(list_mapping.get("list_label") or "-")
                        ),
                    }
                )
                if page_ref is not None:
                    label_element[NameObject("/Pg")] = page_ref
                label_ref = writer._add_object(label_element)

                body_element = DictionaryObject(
                    {
                        NameObject("/Type"): NameObject("/StructElem"),
                        NameObject("/S"): NameObject("/LBody"),
                        NameObject("/P"): item_ref,
                        NameObject("/T"): TextStringObject(
                            str(list_mapping.get("text_preview") or "List item")
                        ),
                        NameObject("/K"): mcr,
                    }
                )
                if page_ref is not None:
                    body_element[NameObject("/Pg")] = page_ref
                body_ref = writer._add_object(body_element)

                item_element[NameObject("/K")] = ArrayObject([label_ref, body_ref])
                item_refs.append(item_ref)
                parent_tree_entries.setdefault(page_index, ArrayObject()).append(body_ref)
                wrapping_plan_by_page.setdefault(page_index, []).append(
                    {
                        "mcid": mcid,
                        "content_block_count": _mapping_content_block_count(list_mapping),
                    }
                )

            list_element[NameObject("/K")] = item_refs
            children.append(list_ref)
            continue

        table_rows = _mapping_table_rows(mapping)
        if role == "Table" and table_rows:
            table_element = DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/StructElem"),
                    NameObject("/S"): NameObject("/Table"),
                    NameObject("/P"): struct_tree_ref,
                    NameObject("/T"): TextStringObject(str(mapping.get("text_preview") or "Table")),
                    NameObject("/K"): ArrayObject(),
                }
            )
            if page_ref is not None:
                table_element[NameObject("/Pg")] = page_ref
            table_ref = writer._add_object(table_element)
            row_refs = ArrayObject()
            header_count = _mapping_table_header_count(mapping)

            for row_index, row in enumerate(table_rows):
                row_element = DictionaryObject(
                    {
                        NameObject("/Type"): NameObject("/StructElem"),
                        NameObject("/S"): NameObject("/TR"),
                        NameObject("/P"): table_ref,
                        NameObject("/K"): ArrayObject(),
                    }
                )
                if page_ref is not None:
                    row_element[NameObject("/Pg")] = page_ref
                row_ref = writer._add_object(row_element)
                cell_refs = ArrayObject()

                for cell_text in row:
                    cell_role = "TH" if row_index == 0 and header_count else "TD"
                    mcid = mcid_by_page.get(page_index, 0)
                    mcid_by_page[page_index] = mcid + 1
                    mcr = DictionaryObject(
                        {
                            NameObject("/Type"): NameObject("/MCR"),
                            NameObject("/MCID"): NumberObject(mcid),
                        }
                    )
                    if page_ref is not None:
                        mcr[NameObject("/Pg")] = page_ref
                    cell_element = DictionaryObject(
                        {
                            NameObject("/Type"): NameObject("/StructElem"),
                            NameObject("/S"): NameObject(f"/{cell_role}"),
                            NameObject("/P"): row_ref,
                            NameObject("/T"): TextStringObject(str(cell_text)),
                            NameObject("/K"): mcr,
                        }
                    )
                    if page_ref is not None:
                        cell_element[NameObject("/Pg")] = page_ref
                    if cell_role == "TH":
                        cell_element[NameObject("/Scope")] = NameObject("/Column")
                    cell_ref = writer._add_object(cell_element)
                    cell_refs.append(cell_ref)
                    parent_tree_entries.setdefault(page_index, ArrayObject()).append(cell_ref)
                    wrapping_plan_by_page.setdefault(page_index, []).append(
                        {
                            "mcid": mcid,
                            "content_block_count": 1,
                        }
                    )

                row_element[NameObject("/K")] = cell_refs
                row_refs.append(row_ref)

            table_element[NameObject("/K")] = row_refs
            children.append(table_ref)
            mapping_index += 1
            continue

        mcid = mcid_by_page.get(page_index, 0)
        mcid_by_page[page_index] = mcid + 1
        link_annotation_ref = (
            _pop_first(link_annotations_by_page.get(page_index, [])) if role == "Link" else None
        )

        mcr = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/MCR"),
                NameObject("/MCID"): NumberObject(mcid),
            }
        )
        if page_ref is not None:
            mcr[NameObject("/Pg")] = page_ref

        element_k: Any = mcr
        if link_annotation_ref is not None:
            objr = DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/OBJR"),
                    NameObject("/Obj"): link_annotation_ref,
                }
            )
            if page_ref is not None:
                objr[NameObject("/Pg")] = page_ref
            element_k = ArrayObject([mcr, objr])

        element = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/StructElem"),
                NameObject("/S"): NameObject(f"/{role}"),
                NameObject("/P"): struct_tree_ref,
                NameObject("/T"): TextStringObject(str(mapping.get("text_preview") or role)),
                NameObject("/K"): element_k,
            }
        )
        if page_ref is not None:
            element[NameObject("/Pg")] = page_ref
        alt_text = _mapping_alt_text(mapping)
        if role == "Figure" and alt_text is not None:
            element[NameObject("/Alt")] = TextStringObject(alt_text)
        element_ref = writer._add_object(element)
        children.append(element_ref)
        parent_tree_entries.setdefault(page_index, ArrayObject()).append(element_ref)
        if link_annotation_ref is not None:
            annotation = link_annotation_ref.get_object()
            annotation[NameObject("/StructParent")] = NumberObject(annotation_parent_key)
            parent_tree_entries[annotation_parent_key] = element_ref
            annotation_parent_key += 1
        wrapping_plan_by_page.setdefault(page_index, []).append(
            {
                "mcid": mcid,
                "content_block_count": _mapping_content_block_count(mapping),
            }
        )
        mapping_index += 1

    struct_tree[NameObject("/K")] = children
    parent_tree[NameObject("/Nums")] = _build_parent_tree_nums(parent_tree_entries)
    root[NameObject("/StructTreeRoot")] = struct_tree_ref

    for page_index, wrapping_plan in wrapping_plan_by_page.items():
        page = writer.pages[page_index]
        page[NameObject("/StructParents")] = NumberObject(page_index)
        _replace_page_contents_with_marked_content(
            writer=writer,
            page=page,
            wrapping_plan=wrapping_plan,
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


def _page_reference(writer, page_index: int) -> object | None:
    if not writer.pages or page_index >= len(writer.pages):
        return None
    page = writer.pages[page_index]
    return getattr(page, "indirect_reference", None)


def _link_annotation_refs_by_page(writer) -> dict[int, list[Any]]:
    annotations_by_page: dict[int, list[Any]] = {}
    for page_index, page in enumerate(writer.pages):
        annotations = page.get("/Annots", [])
        for annotation_ref in annotations:
            annotation = annotation_ref.get_object()
            if annotation.get("/Subtype") == "/Link":
                annotations_by_page.setdefault(page_index, []).append(annotation_ref)
    return annotations_by_page


def _pop_first(items: list[Any]) -> Any | None:
    if not items:
        return None
    return items.pop(0)


def _replace_page_contents_with_marked_content(
    *,
    writer,
    page,
    wrapping_plan: list[dict[str, int]],
    stream_cls,
    name_cls,
) -> None:
    content = page.get_contents()
    if content is None:
        return

    original = content.get_data()
    wrapped = _wrap_content_blocks_with_mcids(original, wrapping_plan)
    stream = stream_cls()
    stream.set_data(wrapped)
    page[name_cls("/Contents")] = writer._add_object(stream)


def _wrap_content_blocks_with_mcids(original: bytes, wrapping_plan: list[dict[str, int]]) -> bytes:
    if not wrapping_plan:
        return original

    blocks = list(re.finditer(rb"q\s+BT\s+.*?ET\s+Q", original, re.DOTALL))
    required_blocks = sum(item["content_block_count"] for item in wrapping_plan)
    if len(blocks) < required_blocks:
        return _wrap_entire_content_with_mcids(original, [item["mcid"] for item in wrapping_plan])

    output = bytearray()
    source_cursor = 0
    block_cursor = 0
    for item in wrapping_plan:
        block_count = item["content_block_count"]
        if block_count <= 0:
            continue

        first_block = blocks[block_cursor]
        last_block = blocks[block_cursor + block_count - 1]
        output.extend(original[source_cursor : first_block.start()])
        output.extend(f"/P <</MCID {item['mcid']}>> BDC\n".encode("ascii"))
        output.extend(original[first_block.start() : last_block.end()])
        output.extend(b"\nEMC")
        source_cursor = last_block.end()
        block_cursor += block_count

    output.extend(original[source_cursor:])
    return bytes(output)


def _wrap_entire_content_with_mcids(original: bytes, mcids: list[int]) -> bytes:
    prefix = "".join(f"/P <</MCID {mcid}>> BDC\n" for mcid in mcids)
    suffix = "".join("EMC\n" for _ in mcids)
    return prefix.encode("ascii") + original + b"\n" + suffix.encode("ascii")


def _build_parent_tree_nums(parent_entries_by_page: dict[int, Any]):
    from pypdf.generic import ArrayObject, NumberObject

    nums = ArrayObject()
    for page_index in sorted(parent_entries_by_page):
        nums.append(NumberObject(page_index))
        nums.append(parent_entries_by_page[page_index])
    return nums


def _mapping_page_index(mapping: Any, page_count: int) -> int:
    try:
        page_index = int(mapping.get("page_index", 0))
    except (AttributeError, TypeError, ValueError):
        return 0
    if page_count <= 0:
        return 0
    return max(0, min(page_index, page_count - 1))


def _mapping_content_block_count(mapping: Any) -> int:
    try:
        block_count = int(mapping.get("content_block_count", 1))
    except (AttributeError, TypeError, ValueError):
        return 1
    return max(1, block_count)


def _mapping_alt_text(mapping: Any) -> str | None:
    try:
        value = mapping.get("alt_text")
    except AttributeError:
        return None
    if value is None:
        return None
    return str(value).strip()


def _mapping_table_rows(mapping: Any) -> list[list[str]]:
    try:
        value = mapping.get("table_rows")
    except AttributeError:
        return []
    if not isinstance(value, list):
        return []

    rows: list[list[str]] = []
    for row in value:
        if not isinstance(row, list):
            continue
        cells = [str(cell).strip() for cell in row if str(cell).strip()]
        if cells:
            rows.append(cells)
    return rows


def _mapping_table_header_count(mapping: Any) -> int:
    try:
        value = mapping.get("table_header_count", 0)
    except AttributeError:
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0
