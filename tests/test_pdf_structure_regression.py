import tempfile
import unittest

from pypdf import PdfReader

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
                self.assertEqual(report_structure["role_counts"], case.expected_role_counts)
                self.assertEqual(
                    artifact.validation_report["structure_plan"]["role_counts"],
                    case.expected_top_level_roles,
                )
                self.assertEqual(
                    {check["id"] for check in report_structure["checks"]},
                    case.expected_checks,
                )

                reader = PdfReader(artifact.path)
                if case.expected_page_count is not None:
                    self.assertEqual(report_structure["counts"]["page_count"], case.expected_page_count)
                    self.assertEqual(len(reader.pages), case.expected_page_count)
                if case.expected_figure_alt is not None:
                    self.assertEqual(_first_structure_element(reader)["/Alt"], case.expected_figure_alt)
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


def _first_structure_element(reader: PdfReader):
    struct_tree = reader.trailer["/Root"]["/StructTreeRoot"].get_object()
    return struct_tree["/K"][0].get_object()


if __name__ == "__main__":
    unittest.main()
