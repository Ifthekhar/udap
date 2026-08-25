"""PDF/UA validation integration.

The validator is optional because local development machines may not have
veraPDF installed. Missing tooling is reported explicitly in the artifact
validation result instead of being treated as success.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class PdfUaValidationResult:
    status: str
    tool: str
    passed: bool | None
    details: str
    raw: dict | None = None


def validate_pdf_ua(path: str | Path) -> PdfUaValidationResult:
    executable = shutil.which("verapdf")
    if executable is None:
        return PdfUaValidationResult(
            status="unavailable",
            tool="veraPDF",
            passed=None,
            details="veraPDF is not installed; PDF/UA validation was not run.",
        )

    command = [executable, "--format", "json", str(path)]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    raw = _parse_json(completed.stdout)

    if completed.returncode not in {0, 1}:
        return PdfUaValidationResult(
            status="error",
            tool="veraPDF",
            passed=False,
            details=completed.stderr.strip() or "veraPDF failed to run.",
            raw=raw,
        )

    passed = _extract_passed(raw)
    return PdfUaValidationResult(
        status="completed",
        tool="veraPDF",
        passed=passed,
        details="veraPDF validation completed.",
        raw=raw,
    )


def validation_to_dict(result: PdfUaValidationResult) -> dict:
    return asdict(result)


def validate_generated_pdf_structure(
    path: str | Path,
    structure_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run structural checks over the generated tagged PDF.

    These checks are intentionally narrower than PDF/UA. They verify the core
    relationships this MVP writes itself: marked content, parent-tree mappings,
    link annotation structure references, figure alt attributes, and simple
    table roles.
    """

    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
    except ImportError:
        return {
            "status": "unavailable",
            "passed": None,
            "details": "pypdf is not installed; generated PDF structure was not checked.",
            "summary": {"check_count": 0, "passed_count": 0, "failed_count": 0},
            "counts": {},
            "role_counts": {},
            "checks": [],
        }

    try:
        reader = PdfReader(str(path))
        actual = _inspect_structure(reader)
    except (OSError, KeyError, TypeError, ValueError, PdfReadError) as exc:
        return {
            "status": "error",
            "passed": False,
            "details": f"Generated PDF structure could not be inspected: {exc}",
            "summary": {"check_count": 1, "passed_count": 0, "failed_count": 1},
            "counts": {},
            "role_counts": {},
            "checks": [
                _check(
                    "structure.inspectable",
                    "Generated PDF can be inspected",
                    False,
                    str(exc),
                )
            ],
        }

    checks = [
        _check(
            "structure.root_present",
            "Structure tree is present",
            actual["has_struct_tree"],
            "Catalog includes /StructTreeRoot."
            if actual["has_struct_tree"]
            else "Catalog is missing /StructTreeRoot.",
        ),
        _check(
            "structure.mark_info_marked",
            "Document is marked",
            actual["mark_info_marked"],
            "Catalog /MarkInfo declares /Marked true."
            if actual["mark_info_marked"]
            else "Catalog /MarkInfo does not declare /Marked true.",
        ),
        _check(
            "structure.mcid_parent_tree",
            "MCIDs are mapped through the parent tree",
            actual["mcids_have_parent_tree_entries"],
            _mcid_parent_tree_details(actual),
        ),
        _check(
            "structure.figures_have_alt",
            "Figures have alternate text entries",
            actual["figures_missing_alt"] == 0,
            "Every /Figure structure element includes /Alt."
            if actual["figures_missing_alt"] == 0
            else f"{actual['figures_missing_alt']} /Figure element(s) are missing /Alt.",
        ),
        _check(
            "structure.links_reference_annotations",
            "Links reference annotations",
            actual["links_missing_annotation_refs"] == 0,
            "Every /Link structure element has an /OBJR annotation reference."
            if actual["links_missing_annotation_refs"] == 0
            else f"{actual['links_missing_annotation_refs']} /Link element(s) are missing valid /OBJR references.",
        ),
        _check(
            "structure.link_annotations_mapped",
            "Link annotations map back to structure elements",
            actual["link_annotations_missing_parent_tree"] == 0,
            "Every linked annotation /StructParent resolves through the parent tree."
            if actual["link_annotations_missing_parent_tree"] == 0
            else f"{actual['link_annotations_missing_parent_tree']} link annotation(s) are missing parent-tree mappings.",
        ),
        _check(
            "structure.tables_have_roles",
            "Tables include row and cell roles",
            actual["tables_missing_required_roles"] == 0,
            "Every /Table includes /TR rows with /TH and /TD cells."
            if actual["tables_missing_required_roles"] == 0
            else f"{actual['tables_missing_required_roles']} /Table element(s) are missing required row or cell roles.",
        ),
    ]
    if structure_plan:
        checks.append(_planned_mapping_check(actual, structure_plan))

    passed_count = len([item for item in checks if item["status"] == "passed"])
    failed_count = len([item for item in checks if item["status"] == "failed"])

    return {
        "status": "passed" if failed_count == 0 else "failed",
        "passed": failed_count == 0,
        "details": (
            "Generated PDF structural checks passed."
            if failed_count == 0
            else "Generated PDF structural checks found issues."
        ),
        "summary": {
            "check_count": len(checks),
            "passed_count": passed_count,
            "failed_count": failed_count,
        },
        "counts": {
            "page_count": len(reader.pages),
            "marked_content_count": actual["marked_content_count"],
            "parent_tree_entry_count": actual["parent_tree_entry_count"],
            "structure_element_count": actual["structure_element_count"],
            "top_level_structure_element_count": actual["top_level_structure_element_count"],
            "figure_count": actual["figure_count"],
            "link_count": actual["link_count"],
            "table_count": actual["table_count"],
        },
        "role_counts": actual["role_counts"],
        "checks": checks,
    }


def _parse_json(output: str) -> dict | None:
    output = output.strip()
    if not output:
        return None
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError:
        return {"unparsed_output": output}
    return parsed if isinstance(parsed, dict) else {"result": parsed}


def _extract_passed(raw: dict | None) -> bool | None:
    if raw is None:
        return None

    jobs = raw.get("jobs")
    if isinstance(jobs, list) and jobs:
        validation_result = jobs[0].get("validationResult", {})
        if isinstance(validation_result, dict) and "isCompliant" in validation_result:
            return bool(validation_result["isCompliant"])

    validation_result = raw.get("validationResult")
    if isinstance(validation_result, dict) and "isCompliant" in validation_result:
        return bool(validation_result["isCompliant"])

    return None


def _inspect_structure(reader: Any) -> dict[str, Any]:
    root = _resolve(reader.trailer.get("/Root"))
    mark_info = _resolve(root.get("/MarkInfo")) if isinstance(root, dict) else None
    struct_tree = _resolve(root.get("/StructTreeRoot")) if isinstance(root, dict) else None
    parent_tree = _resolve(struct_tree.get("/ParentTree")) if isinstance(struct_tree, dict) else None
    parent_tree_entries = _parent_tree_entries(parent_tree)
    page_marked_content_counts = _page_marked_content_counts(reader)
    elements = _structure_elements(struct_tree.get("/K") if isinstance(struct_tree, dict) else None)
    top_level_elements = [
        _resolve(item) for item in _as_list(struct_tree.get("/K") if isinstance(struct_tree, dict) else None)
    ]
    top_level_elements = [
        item for item in top_level_elements if isinstance(item, dict) and item.get("/Type") == "/StructElem"
    ]
    role_counts = _role_counts(elements)
    top_level_role_counts = _role_counts(top_level_elements)

    return {
        "has_struct_tree": isinstance(struct_tree, dict),
        "mark_info_marked": bool(mark_info.get("/Marked")) if isinstance(mark_info, dict) else False,
        "marked_content_count": sum(page_marked_content_counts.values()),
        "parent_tree_entry_count": _parent_tree_entry_count(parent_tree_entries),
        "structure_element_count": len(elements),
        "top_level_structure_element_count": len(top_level_elements),
        "figure_count": role_counts.get("Figure", 0),
        "link_count": role_counts.get("Link", 0),
        "table_count": role_counts.get("Table", 0),
        "role_counts": role_counts,
        "top_level_role_counts": top_level_role_counts,
        "mcids_have_parent_tree_entries": _mcids_have_parent_tree_entries(
            reader,
            page_marked_content_counts,
            parent_tree_entries,
        ),
        "figures_missing_alt": _figures_missing_alt(elements),
        "links_missing_annotation_refs": _links_missing_annotation_refs(elements),
        "link_annotations_missing_parent_tree": _link_annotations_missing_parent_tree(
            elements,
            parent_tree_entries,
        ),
        "tables_missing_required_roles": _tables_missing_required_roles(elements),
        "page_marked_content_counts": page_marked_content_counts,
    }


def _check(check_id: str, label: str, passed: bool, details: str) -> dict[str, str | bool]:
    return {
        "id": check_id,
        "label": label,
        "status": "passed" if passed else "failed",
        "passed": passed,
        "details": details,
    }


def _planned_mapping_check(actual: dict[str, Any], structure_plan: dict[str, Any]) -> dict[str, str | bool]:
    expected_mappings = structure_plan.get("mappings", [])
    expected_role_counts = structure_plan.get("role_counts", {})
    if not isinstance(expected_mappings, list):
        expected_mappings = []
    if not isinstance(expected_role_counts, dict):
        expected_role_counts = {}

    missing_roles = {
        str(role): count
        for role, count in expected_role_counts.items()
        if actual["top_level_role_counts"].get(str(role), 0) < int(count)
    }
    expected_count = len(expected_mappings)
    actual_count = actual["top_level_structure_element_count"]
    passed = actual_count >= expected_count and not missing_roles
    details = (
        f"Top-level structure has {actual_count} element(s) for {expected_count} planned mapping(s)."
    )
    if missing_roles:
        details += f" Missing planned role counts: {missing_roles}."

    return _check(
        "structure.matches_plan",
        "Structure tree matches the generated plan",
        passed,
        details,
    )


def _mcid_parent_tree_details(actual: dict[str, Any]) -> str:
    if actual["mcids_have_parent_tree_entries"]:
        return "Each page with marked content has a parent-tree array large enough for its MCIDs."
    return (
        "One or more pages with marked content are missing /StructParents or a large enough "
        "parent-tree array."
    )


def _resolve(value: Any) -> Any:
    if hasattr(value, "get_object"):
        return value.get_object()
    return value


def _as_list(value: Any) -> list[Any]:
    resolved = _resolve(value)
    if resolved is None:
        return []
    if isinstance(resolved, list):
        return list(resolved)
    return [resolved]


def _structure_elements(value: Any) -> list[Any]:
    resolved = _resolve(value)
    if resolved is None:
        return []
    if isinstance(resolved, list):
        elements: list[Any] = []
        for item in resolved:
            elements.extend(_structure_elements(item))
        return elements
    if not isinstance(resolved, dict):
        return []

    elements = [resolved] if resolved.get("/Type") == "/StructElem" else []
    elements.extend(_structure_elements(resolved.get("/K")))
    return elements


def _role_counts(elements: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for element in elements:
        role = _role_name(element.get("/S"))
        if not role:
            continue
        counts[role] = counts.get(role, 0) + 1
    return counts


def _role_name(value: Any) -> str:
    text = str(value or "").strip()
    return text.removeprefix("/")


def _parent_tree_entries(parent_tree: Any) -> dict[int, Any]:
    if not isinstance(parent_tree, dict):
        return {}
    nums = _resolve(parent_tree.get("/Nums"))
    if not isinstance(nums, list):
        return {}

    entries: dict[int, Any] = {}
    for index in range(0, len(nums) - 1, 2):
        try:
            key = int(nums[index])
        except (TypeError, ValueError):
            continue
        entries[key] = _resolve(nums[index + 1])
    return entries


def _parent_tree_entry_count(entries: dict[int, Any]) -> int:
    count = 0
    for value in entries.values():
        if isinstance(value, list):
            count += len(value)
        elif value is not None:
            count += 1
    return count


def _page_marked_content_counts(reader: Any) -> dict[int, int]:
    counts: dict[int, int] = {}
    for page_index, page in enumerate(reader.pages):
        try:
            content = page.get_contents()
            if content is None:
                continue
            data = content.get_data().decode("latin-1", errors="ignore")
        except (AttributeError, KeyError, TypeError, ValueError):
            continue
        counts[page_index] = data.count("/MCID")
    return counts


def _mcids_have_parent_tree_entries(
    reader: Any,
    page_marked_content_counts: dict[int, int],
    parent_tree_entries: dict[int, Any],
) -> bool:
    for page_index, mcid_count in page_marked_content_counts.items():
        if mcid_count <= 0:
            continue
        page = reader.pages[page_index]
        if "/StructParents" not in page:
            return False
        try:
            parent_key = int(page["/StructParents"])
        except (TypeError, ValueError):
            return False
        entry = parent_tree_entries.get(parent_key)
        if not isinstance(entry, list) or len(entry) < mcid_count:
            return False
    return True


def _figures_missing_alt(elements: list[Any]) -> int:
    return len([element for element in elements if element.get("/S") == "/Figure" and "/Alt" not in element])


def _links_missing_annotation_refs(elements: list[Any]) -> int:
    missing = 0
    for element in elements:
        if element.get("/S") != "/Link":
            continue
        if not _link_objr_refs(element):
            missing += 1
    return missing


def _link_annotations_missing_parent_tree(
    elements: list[Any],
    parent_tree_entries: dict[int, Any],
) -> int:
    missing = 0
    for element in elements:
        if element.get("/S") != "/Link":
            continue
        for annotation_ref in _link_objr_refs(element):
            annotation = _resolve(annotation_ref)
            if not isinstance(annotation, dict) or annotation.get("/Subtype") != "/Link":
                missing += 1
                continue
            if "/StructParent" not in annotation:
                missing += 1
                continue
            try:
                parent_key = int(annotation["/StructParent"])
            except (TypeError, ValueError):
                missing += 1
                continue
            if parent_key not in parent_tree_entries:
                missing += 1
    return missing


def _link_objr_refs(element: Any) -> list[Any]:
    refs: list[Any] = []
    for item in _as_list(element.get("/K")):
        resolved = _resolve(item)
        if isinstance(resolved, dict) and resolved.get("/Type") == "/OBJR" and "/Obj" in resolved:
            refs.append(resolved.raw_get("/Obj") if hasattr(resolved, "raw_get") else resolved["/Obj"])
    return refs


def _tables_missing_required_roles(elements: list[Any]) -> int:
    missing = 0
    for table in [element for element in elements if element.get("/S") == "/Table"]:
        rows = [
            _resolve(row)
            for row in _as_list(table.get("/K"))
            if isinstance(_resolve(row), dict) and _resolve(row).get("/S") == "/TR"
        ]
        if not rows:
            missing += 1
            continue
        cell_roles = []
        invalid_row = False
        for row in rows:
            cells = [
                _resolve(cell)
                for cell in _as_list(row.get("/K"))
                if isinstance(_resolve(cell), dict)
            ]
            row_roles = {_role_name(cell.get("/S")) for cell in cells}
            if not cells or not row_roles.issubset({"TH", "TD"}):
                invalid_row = True
            cell_roles.extend(row_roles)
        if invalid_row or "TH" not in cell_roles or "TD" not in cell_roles:
            missing += 1
    return missing
