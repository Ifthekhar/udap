import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, NameObject

from tests.pdf_regression_cases import generated_pdf_regression_cases
from udap.pdf_output import generate_remediated_pdf
from udap.pdf_validation import validate_generated_pdf_structure
from udap.pipeline import analyse_document


class PdfStructureRegressionTest(unittest.TestCase):
    def test_generated_pdf_regression_cases_pass_structural_checks(self):
        for case in generated_pdf_regression_cases():
            with self.subTest(case=case.name), tempfile.TemporaryDirectory() as tmp:
                artifact = generate_remediated_pdf(analyse_document(case.document), output_dir=tmp)
                report_structure = artifact.validation_report["pdf_structure"]
                direct_structure = validate_generated_pdf_structure(
                    artifact.path,
                    artifact.validation_report["structure_plan"],
                )

                self.assertEqual(report_structure["status"], "passed")
                self.assertEqual(report_structure["summary"]["failed_count"], 0)
                self.assertEqual(report_structure, direct_structure)
                self.assertEqual(
                    report_structure["counts"]["marked_content_count"],
                    case.expected_marked_content_count,
                )
                self.assertEqual(
                    report_structure["counts"]["parent_tree_entry_count"],
                    case.expected_parent_tree_entry_count,
                )
                self.assertEqual(
                    report_structure["counts"]["structure_element_count"],
                    case.expected_structure_element_count,
                )
                self.assertEqual(
                    report_structure["counts"]["link_count"],
                    case.expected_link_count,
                )
                self.assertEqual(
                    report_structure["counts"]["table_count"],
                    case.expected_table_count,
                )
                self.assertEqual(
                    report_structure["counts"]["list_count"],
                    case.expected_list_count,
                )
                self.assertEqual(report_structure["role_counts"], case.expected_role_counts)
                self.assertEqual(
                    artifact.validation_report["structure_plan"]["role_counts"],
                    case.expected_top_level_roles,
                )
                self.assertEqual(
                    {check["id"] for check in report_structure["checks"]},
                    case.expected_checks,
                )
                self.assertEqual(report_structure["reading_order"]["status"], "passed")
                self.assertTrue(report_structure["reading_order"]["top_level_order_matches_plan"])
                self.assertTrue(report_structure["reading_order"]["content_sequence_matches_plan"])
                self.assertTrue(report_structure["reading_order"]["mcids_increase_by_page"])
                self.assertTrue(report_structure["reading_order"]["parent_tree_keys_match_pages"])

                reader = PdfReader(artifact.path)
                if case.expected_page_count is not None:
                    self.assertEqual(report_structure["counts"]["page_count"], case.expected_page_count)
                    self.assertEqual(len(reader.pages), case.expected_page_count)
                if case.expected_figure_alt is not None:
                    self.assertEqual(_first_structure_element(reader)["/Alt"], case.expected_figure_alt)
                if case.expected_list_count:
                    self.assertEqual(_first_structure_element(reader)["/S"], "/L")
                    self.assertEqual(
                        _list_item_child_roles(_first_structure_element(reader)),
                        [["Lbl", "LBody"], ["Lbl", "LBody"]],
                    )
                if case.expected_wrapped_mcid_count is not None:
                    content = reader.pages[0].get_contents().get_data().decode("latin-1")
                    self.assertEqual(content.count("/MCID"), case.expected_wrapped_mcid_count)
                    self.assertGreaterEqual(
                        content.count("\nq\nBT\n"),
                        case.minimum_text_block_count or 0,
                    )

    def test_multi_page_fixture_has_parent_tree_entries_for_each_content_page(self):
        case = next(
            item for item in generated_pdf_regression_cases() if item.name == "multi_page_parent_tree"
        )

        with tempfile.TemporaryDirectory() as tmp:
            artifact = generate_remediated_pdf(analyse_document(case.document), output_dir=tmp)
            reader = PdfReader(artifact.path)
            struct_tree = reader.trailer["/Root"]["/StructTreeRoot"].get_object()
            parent_tree_nums = struct_tree["/ParentTree"].get_object()["/Nums"]

        parent_tree_keys = [int(parent_tree_nums[index]) for index in range(0, len(parent_tree_nums), 2)]
        content_page_keys = [
            int(page["/StructParents"])
            for page in reader.pages
            if page.get_contents().get_data().count(b"/MCID")
        ]

        self.assertEqual(content_page_keys, [0, 1])
        self.assertEqual(parent_tree_keys, [0, 1])

    def test_multi_page_fixture_reports_reading_order_by_page(self):
        case = next(
            item for item in generated_pdf_regression_cases() if item.name == "multi_page_parent_tree"
        )

        with tempfile.TemporaryDirectory() as tmp:
            artifact = generate_remediated_pdf(analyse_document(case.document), output_dir=tmp)

        reading_order = artifact.validation_report["pdf_structure"]["reading_order"]

        self.assertEqual(reading_order["status"], "passed")
        self.assertEqual(reading_order["page_marked_content_counts"], {"0": 29, "1": 11})
        self.assertEqual(reading_order["actual_content_sequence"][0], {"role": "P", "page_index": 0})
        self.assertEqual(reading_order["actual_content_sequence"][28], {"role": "P", "page_index": 0})
        self.assertEqual(reading_order["actual_content_sequence"][29], {"role": "P", "page_index": 1})
        self.assertEqual(reading_order["actual_content_sequence"][-1], {"role": "P", "page_index": 1})

    def test_validator_flags_pdf_missing_structure_tree(self):
        case = next(item for item in generated_pdf_regression_cases() if item.name == "heading_paragraph")

        with tempfile.TemporaryDirectory() as tmp:
            artifact = generate_remediated_pdf(analyse_document(case.document), output_dir=tmp)
            damaged_path = Path(tmp) / "missing-structure-tree.pdf"
            _write_modified_pdf(
                artifact.path,
                damaged_path,
                lambda writer: writer.root_object.pop(NameObject("/StructTreeRoot"), None),
            )
            structure = validate_generated_pdf_structure(
                damaged_path,
                artifact.validation_report["structure_plan"],
            )

        failed_checks = _failed_checks(structure)

        self.assertEqual(structure["status"], "failed")
        self.assertIn("structure.root_present", failed_checks)
        self.assertIn("structure.reading_order_matches_plan", failed_checks)

    def test_validator_flags_removed_figure_alt_text(self):
        case = next(item for item in generated_pdf_regression_cases() if item.name == "figure_alt")

        with tempfile.TemporaryDirectory() as tmp:
            artifact = generate_remediated_pdf(analyse_document(case.document), output_dir=tmp)
            damaged_path = Path(tmp) / "figure-without-alt.pdf"
            _write_modified_pdf(artifact.path, damaged_path, _remove_first_figure_alt)
            structure = validate_generated_pdf_structure(
                damaged_path,
                artifact.validation_report["structure_plan"],
            )

        failed_checks = _failed_checks(structure)

        self.assertEqual(structure["status"], "failed")
        self.assertIn("structure.figures_have_alt", failed_checks)

    def test_validator_flags_broken_list_hierarchy(self):
        case = next(item for item in generated_pdf_regression_cases() if item.name == "simple_list")

        with tempfile.TemporaryDirectory() as tmp:
            artifact = generate_remediated_pdf(analyse_document(case.document), output_dir=tmp)
            damaged_path = Path(tmp) / "list-without-body.pdf"
            _write_modified_pdf(artifact.path, damaged_path, _remove_first_list_body)
            structure = validate_generated_pdf_structure(
                damaged_path,
                artifact.validation_report["structure_plan"],
            )

        failed_checks = _failed_checks(structure)

        self.assertEqual(structure["status"], "failed")
        self.assertIn("structure.lists_have_roles", failed_checks)

    def test_validator_flags_reversed_reading_order(self):
        case = next(item for item in generated_pdf_regression_cases() if item.name == "heading_paragraph")

        with tempfile.TemporaryDirectory() as tmp:
            artifact = generate_remediated_pdf(analyse_document(case.document), output_dir=tmp)
            damaged_path = Path(tmp) / "reversed-reading-order.pdf"
            _write_modified_pdf(artifact.path, damaged_path, _reverse_top_level_structure_order)
            structure = validate_generated_pdf_structure(
                damaged_path,
                artifact.validation_report["structure_plan"],
            )

        failed_checks = _failed_checks(structure)
        reading_order = structure["reading_order"]

        self.assertEqual(structure["status"], "failed")
        self.assertIn("structure.reading_order_matches_plan", failed_checks)
        self.assertFalse(reading_order["top_level_order_matches_plan"])
        self.assertFalse(reading_order["content_sequence_matches_plan"])
        self.assertFalse(reading_order["mcids_increase_by_page"])


def _first_structure_element(reader: PdfReader):
    struct_tree = reader.trailer["/Root"]["/StructTreeRoot"].get_object()
    return struct_tree["/K"][0].get_object()


def _list_item_child_roles(list_element) -> list[list[str]]:
    return [
        [str(child.get_object()["/S"]).removeprefix("/") for child in item_ref.get_object()["/K"]]
        for item_ref in list_element["/K"]
    ]


def _write_modified_pdf(source_path: str, output_path: Path, modifier) -> None:
    reader = PdfReader(source_path)
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    modifier(writer)
    with output_path.open("wb") as handle:
        writer.write(handle)


def _remove_first_figure_alt(writer: PdfWriter) -> None:
    for element in _structure_elements(writer):
        if element.get("/S") == "/Figure":
            element.pop(NameObject("/Alt"), None)
            return
    raise AssertionError("No /Figure structure element found.")


def _remove_first_list_body(writer: PdfWriter) -> None:
    for element in _structure_elements(writer):
        if element.get("/S") != "/LI":
            continue
        children = [child for child in element["/K"] if child.get_object().get("/S") != "/LBody"]
        element[NameObject("/K")] = ArrayObject(children)
        return
    raise AssertionError("No /LI structure element found.")


def _reverse_top_level_structure_order(writer: PdfWriter) -> None:
    struct_tree = writer.root_object["/StructTreeRoot"].get_object()
    struct_tree[NameObject("/K")] = ArrayObject(reversed(struct_tree["/K"]))


def _structure_elements(writer: PdfWriter):
    struct_tree = writer.root_object["/StructTreeRoot"].get_object()
    return _walk_structure(struct_tree["/K"])


def _walk_structure(value) -> list:
    if isinstance(value, list):
        elements = []
        for item in value:
            elements.extend(_walk_structure(item))
        return elements

    resolved = value.get_object() if hasattr(value, "get_object") else value
    if not hasattr(resolved, "get"):
        return []

    elements = [resolved] if resolved.get("/Type") == "/StructElem" else []
    elements.extend(_walk_structure(resolved.get("/K", [])))
    return elements


def _failed_checks(structure: dict) -> set[str]:
    return {check["id"] for check in structure["checks"] if check["status"] == "failed"}


if __name__ == "__main__":
    unittest.main()
