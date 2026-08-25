import json
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from udap.extractors import load_pdf
from udap.job_store import LocalJobStore
from udap.models import (
    DocumentElement,
    DocumentModel,
    ElementType,
    JobStatus,
    ReviewDecision,
    SourceLocation,
    UserDecision,
)
from udap.pdf_output import (
    generate_accessibility_report_artifact,
    generate_remediated_pdf,
    generate_remediated_pdf_outputs,
)
from udap.pipeline import analyse_document
from udap.review import record_user_decisions


class PdfOutputTest(unittest.TestCase):
    def test_generate_remediated_pdf_writes_metadata_and_text(self):
        result = analyse_document(
            DocumentModel(
                original_filename="source.pdf",
                source_format="pdf",
                title="Accessible Annual Report",
                language="en-AU",
                elements=[
                    DocumentElement(
                        type=ElementType.HEADING,
                        text="Annual Report 2026",
                        heading_level=1,
                    ),
                    DocumentElement(
                        type=ElementType.PARAGRAPH,
                        text="This report has been reconstructed into a readable PDF.",
                    ),
                ],
            )
        )

        with tempfile.TemporaryDirectory() as tmp:
            artifact = generate_remediated_pdf(result, output_dir=tmp)
            generated = load_pdf(Path(artifact.path))
            content = PdfReader(artifact.path).pages[0].get_contents().get_data().decode("latin-1")

        self.assertEqual(artifact.filename, "source_accessible.pdf")
        self.assertEqual(generated.title, "Accessible Annual Report")
        self.assertEqual(generated.language, "en-AU")
        self.assertTrue(generated.pdf.is_tagged)
        self.assertEqual(generated.pdf.marked_content_count, 2)
        self.assertEqual(generated.pdf.parent_tree_entry_count, 2)
        self.assertEqual(generated.pdf.structure_element_count, 2)
        self.assertIn("EMC\n\n/P <</MCID 1>> BDC", content)
        self.assertTrue(any("Annual Report 2026" in element.text for element in generated.elements))
        self.assertIn("validation_report", artifact.__dict__)
        self.assertEqual(artifact.validation_report["pdf_ua"]["status"], "unavailable")
        self.assertEqual(artifact.validation_report["structure_plan"]["status"], "embedded_minimal")
        self.assertEqual(artifact.validation_report["structure_plan"]["role_counts"]["H1"], 1)
        self.assertEqual(artifact.validation_report["structure_plan"]["role_counts"]["P"], 1)
        self.assertEqual(artifact.validation_report["pdf_structure"]["status"], "passed")
        self.assertEqual(artifact.validation_report["pdf_structure"]["summary"]["failed_count"], 0)
        self.assertEqual(
            artifact.validation_report["pdf_structure"]["reading_order"]["status"],
            "passed",
        )
        self.assertEqual(
            artifact.validation_report["pdf_structure"]["role_counts"],
            {"H1": 1, "P": 1},
        )
        self.assertNotIn(
            "untagged_pdf",
            artifact.validation_report["summary"]["issue_type_counts"],
        )
        self.assertEqual(artifact.validation_report["remediation_summary"]["remaining_issue_count"], 0)

    def test_generate_remediated_pdf_outputs_writes_report_artifact(self):
        result = analyse_document(
            DocumentModel(
                original_filename="report.pdf",
                source_format="pdf",
                title="Report",
                language="en-AU",
                elements=[DocumentElement(type=ElementType.PARAGRAPH, text="Body text")],
            )
        )

        with tempfile.TemporaryDirectory() as tmp:
            pdf_artifact, report_artifact = generate_remediated_pdf_outputs(result, output_dir=tmp)
            payload = json.loads(Path(report_artifact.path).read_text(encoding="utf-8"))

        self.assertEqual(pdf_artifact.filename, "report_accessible.pdf")
        self.assertEqual(report_artifact.filename, "report_accessibility_report.json")
        self.assertEqual(report_artifact.type.value, "accessibility_report")
        self.assertEqual(payload["artifact_type"], "accessibility_report")
        self.assertEqual(payload["source_artifact"]["id"], pdf_artifact.id)
        self.assertIn("remediation_summary", payload["validation_report"])
        self.assertIn("pdf_structure", payload["validation_report"])
        self.assertEqual(report_artifact.validation_report, payload)

    def test_report_artifact_uses_pdf_validation_payload(self):
        result = analyse_document(
            DocumentModel(
                original_filename="standalone-report.pdf",
                source_format="pdf",
                title="Standalone Report",
                language="en-AU",
                elements=[DocumentElement(type=ElementType.PARAGRAPH, text="Body text")],
            )
        )

        with tempfile.TemporaryDirectory() as tmp:
            pdf_artifact = generate_remediated_pdf(result, output_dir=tmp)
            report_artifact = generate_accessibility_report_artifact(pdf_artifact)
            payload = json.loads(Path(report_artifact.path).read_text(encoding="utf-8"))

        self.assertEqual(payload["validation_report"], pdf_artifact.validation_report)

    def test_generate_remediated_pdf_uses_reviewed_title_and_language(self):
        result = analyse_document(
            DocumentModel(
                original_filename="untitled.pdf",
                source_format="pdf",
                elements=[DocumentElement(type=ElementType.PARAGRAPH, text="Draft report")],
            )
        )
        title_suggestion = next(
            suggestion for suggestion in result.suggestions if suggestion.action.value == "set_document_title"
        )
        language_suggestion = next(
            suggestion
            for suggestion in result.suggestions
            if suggestion.action.value == "set_document_language"
        )
        reviewed = record_user_decisions(
            result,
            [
                UserDecision(
                    suggestion_id=title_suggestion.id,
                    issue_id=title_suggestion.issue_id,
                    decision=ReviewDecision.EDIT,
                    final_value="Reviewed Title",
                ),
                UserDecision(
                    suggestion_id=language_suggestion.id,
                    issue_id=language_suggestion.issue_id,
                    decision=ReviewDecision.EDIT,
                    final_value="en-US",
                ),
            ],
        )

        with tempfile.TemporaryDirectory() as tmp:
            artifact = generate_remediated_pdf(reviewed, output_dir=tmp)
            generated = load_pdf(Path(artifact.path))

        self.assertEqual(generated.title, "Reviewed Title")
        self.assertEqual(generated.language, "en-US")

    def test_output_report_separates_fixed_and_remaining_issues(self):
        result = analyse_document(
            DocumentModel(
                original_filename="needs-fixes.pdf",
                source_format="pdf",
                elements=[
                    DocumentElement(
                        type=ElementType.IMAGE,
                        source=SourceLocation(element_id="chart-1"),
                        metadata={"nearby_text": "Annual revenue chart."},
                    ),
                ],
            )
        )
        suggestion = next(
            suggestion
            for suggestion in result.suggestions
            if suggestion.action.value == "generate_alt_text"
        )
        reviewed = record_user_decisions(
            result,
            [
                UserDecision(
                    suggestion_id=suggestion.id,
                    issue_id=suggestion.issue_id,
                    decision=ReviewDecision.EDIT,
                    final_value="Bar chart showing annual revenue.",
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmp:
            artifact = generate_remediated_pdf(reviewed, output_dir=tmp)

        summary = artifact.validation_report["remediation_summary"]

        self.assertGreaterEqual(summary["fixed_issue_count"], 3)
        self.assertIn("missing_document_title", summary["fixed_issue_type_counts"])
        self.assertIn("missing_document_language", summary["fixed_issue_type_counts"])
        self.assertIn("missing_image_alt_text", summary["fixed_issue_type_counts"])
        self.assertEqual(summary["remaining_issue_count"], 0)
        self.assertEqual(summary["manual_review_count"], 0)

    def test_output_report_keeps_rejected_and_remaining_review_items(self):
        result = analyse_document(
            DocumentModel(
                original_filename="rejected-table.pdf",
                source_format="pdf",
                title="Rejected Table",
                language="en-AU",
                elements=[
                    DocumentElement(
                        type=ElementType.TABLE,
                        text="Revenue\t100\nCosts\t50",
                    ),
                ],
            )
        )
        suggestion = next(
            suggestion
            for suggestion in result.suggestions
            if suggestion.action.value == "confirm_table_headers"
        )
        reviewed = record_user_decisions(
            result,
            [
                UserDecision(
                    suggestion_id=suggestion.id,
                    issue_id=suggestion.issue_id,
                    decision=ReviewDecision.REJECT,
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmp:
            artifact = generate_remediated_pdf(reviewed, output_dir=tmp)

        summary = artifact.validation_report["remediation_summary"]

        self.assertEqual(summary["rejected_issue_count"], 1)
        self.assertEqual(summary["rejected_issue_type_counts"], {"missing_table_headers": 1})
        self.assertIn("missing_heading_structure", summary["remaining_issue_type_counts"])
        self.assertIn("missing_heading_structure", summary["manual_review_type_counts"])

    def test_multiline_element_uses_one_marked_content_section(self):
        result = analyse_document(
            DocumentModel(
                original_filename="wrapped.pdf",
                source_format="pdf",
                title="Wrapped",
                language="en-AU",
                elements=[
                    DocumentElement(
                        type=ElementType.PARAGRAPH,
                        text=(
                            "This paragraph is intentionally long enough to wrap across multiple "
                            "generated PDF text drawing blocks while still representing one logical "
                            "document element in the structure tree."
                        ),
                    ),
                ],
            )
        )

        with tempfile.TemporaryDirectory() as tmp:
            artifact = generate_remediated_pdf(result, output_dir=tmp)
            generated = load_pdf(Path(artifact.path))
            content = PdfReader(artifact.path).pages[0].get_contents().get_data().decode("latin-1")

        self.assertEqual(generated.pdf.marked_content_count, 1)
        self.assertEqual(generated.pdf.parent_tree_entry_count, 1)
        self.assertEqual(generated.pdf.structure_element_count, 1)
        self.assertGreater(content.count("\nq\nBT\n"), 1)
        self.assertEqual(content.count("/MCID"), 1)

    def test_link_structure_references_annotation_object(self):
        result = analyse_document(
            DocumentModel(
                original_filename="link.pdf",
                source_format="pdf",
                title="Link",
                language="en-AU",
                elements=[
                    DocumentElement(
                        type=ElementType.LINK,
                        text="Example link",
                        href="https://example.com",
                    ),
                ],
            )
        )

        with tempfile.TemporaryDirectory() as tmp:
            artifact = generate_remediated_pdf(result, output_dir=tmp)
            generated = load_pdf(Path(artifact.path))
            reader = PdfReader(artifact.path)
            page = reader.pages[0]
            annotation_ref = page["/Annots"][0]
            annotation = annotation_ref.get_object()
            struct_tree = reader.trailer["/Root"]["/StructTreeRoot"].get_object()
            link_element_ref = struct_tree["/K"][0]
            link_element = link_element_ref.get_object()
            parent_tree_nums = struct_tree["/ParentTree"].get_object()["/Nums"]

        self.assertEqual(annotation["/Subtype"], "/Link")
        self.assertIn("/StructParent", annotation)
        self.assertEqual(link_element["/S"], "/Link")
        self.assertEqual(link_element["/K"][0]["/Type"], "/MCR")
        self.assertEqual(link_element["/K"][1]["/Type"], "/OBJR")
        self.assertEqual(link_element["/K"][1].raw_get("/Obj"), annotation_ref)
        self.assertIn(annotation["/StructParent"], parent_tree_nums)
        parent_key_index = parent_tree_nums.index(annotation["/StructParent"])
        self.assertEqual(parent_tree_nums[parent_key_index + 1], link_element_ref)
        self.assertEqual(generated.pdf.marked_content_count, 1)
        self.assertEqual(generated.pdf.parent_tree_entry_count, 2)
        self.assertEqual(generated.pdf.structure_element_count, 1)

    def test_output_skips_text_block_that_duplicates_link_annotation(self):
        link_bbox = (72.0, 136.0, 136.0, 158.0)
        result = analyse_document(
            DocumentModel(
                original_filename="duplicate-link.pdf",
                source_format="pdf",
                title="Duplicate Link",
                language="en-AU",
                elements=[
                    DocumentElement(
                        type=ElementType.PARAGRAPH,
                        text="Read more",
                        source=SourceLocation(page_number=1, element_id="1:2", bbox=link_bbox),
                    ),
                    DocumentElement(
                        type=ElementType.LINK,
                        text="Read more",
                        href="https://example.com/report",
                        source=SourceLocation(
                            page_number=1,
                            element_id="1:link:1",
                            bbox=link_bbox,
                        ),
                    ),
                ],
            )
        )

        with tempfile.TemporaryDirectory() as tmp:
            artifact = generate_remediated_pdf(result, output_dir=tmp)
            text = PdfReader(artifact.path).pages[0].extract_text()

        self.assertEqual(text.count("Read more"), 1)

    def test_image_structure_writes_figure_alt_text(self):
        result = analyse_document(
            DocumentModel(
                original_filename="figure.pdf",
                source_format="pdf",
                title="Figure",
                language="en-AU",
                elements=[
                    DocumentElement(
                        type=ElementType.IMAGE,
                        alt_text="Bar chart comparing quarterly revenue.",
                    ),
                ],
            )
        )

        with tempfile.TemporaryDirectory() as tmp:
            artifact = generate_remediated_pdf(result, output_dir=tmp)
            generated = load_pdf(Path(artifact.path))
            reader = PdfReader(artifact.path)
            struct_tree = reader.trailer["/Root"]["/StructTreeRoot"].get_object()
            figure = struct_tree["/K"][0].get_object()

        self.assertEqual(figure["/S"], "/Figure")
        self.assertEqual(figure["/Alt"], "Bar chart comparing quarterly revenue.")
        self.assertEqual(figure["/K"]["/Type"], "/MCR")
        self.assertEqual(generated.pdf.marked_content_count, 1)
        self.assertEqual(generated.pdf.parent_tree_entry_count, 1)
        self.assertEqual(generated.pdf.structure_element_count, 1)
        self.assertEqual(artifact.validation_report["structure_plan"]["role_counts"]["Figure"], 1)
        self.assertEqual(artifact.validation_report["pdf_structure"]["status"], "passed")
        self.assertFalse(artifact.validation_report["structure_plan"]["mappings"][0]["decorative"])

    def test_structural_validation_flags_missing_figure_alt(self):
        result = analyse_document(
            DocumentModel(
                original_filename="figure-without-alt.pdf",
                source_format="pdf",
                title="Figure Without Alt",
                language="en-AU",
                elements=[DocumentElement(type=ElementType.IMAGE)],
            )
        )

        with tempfile.TemporaryDirectory() as tmp:
            artifact = generate_remediated_pdf(result, output_dir=tmp)

        structure = artifact.validation_report["pdf_structure"]
        failed_checks = {
            check["id"]: check for check in structure["checks"] if check["status"] == "failed"
        }

        self.assertEqual(structure["status"], "failed")
        self.assertIn("structure.figures_have_alt", failed_checks)
        self.assertEqual(structure["counts"]["figure_count"], 1)

    def test_image_structure_uses_reviewed_alt_text(self):
        result = analyse_document(
            DocumentModel(
                original_filename="reviewed-figure.pdf",
                source_format="pdf",
                title="Reviewed Figure",
                language="en-AU",
                elements=[
                    DocumentElement(
                        type=ElementType.IMAGE,
                        source=SourceLocation(element_id="chart-1"),
                        metadata={"nearby_text": "Quarterly revenue rose across all regions."},
                    ),
                ],
            )
        )
        suggestion = next(
            suggestion
            for suggestion in result.suggestions
            if suggestion.action.value == "generate_alt_text"
        )
        reviewed = record_user_decisions(
            result,
            [
                UserDecision(
                    suggestion_id=suggestion.id,
                    issue_id=suggestion.issue_id,
                    decision=ReviewDecision.EDIT,
                    final_value="Line chart showing quarterly revenue growth across all regions.",
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmp:
            artifact = generate_remediated_pdf(reviewed, output_dir=tmp)
            reader = PdfReader(artifact.path)
            struct_tree = reader.trailer["/Root"]["/StructTreeRoot"].get_object()
            figure = struct_tree["/K"][0].get_object()

        self.assertEqual(
            figure["/Alt"],
            "Line chart showing quarterly revenue growth across all regions.",
        )
        self.assertEqual(
            artifact.validation_report["structure_plan"]["mappings"][0]["alt_text"],
            "Line chart showing quarterly revenue growth across all regions.",
        )

    def test_decorative_image_is_marked_in_structure_plan(self):
        result = analyse_document(
            DocumentModel(
                original_filename="decorative.pdf",
                source_format="pdf",
                title="Decorative",
                language="en-AU",
                elements=[DocumentElement(type=ElementType.IMAGE, decorative=True)],
            )
        )

        with tempfile.TemporaryDirectory() as tmp:
            artifact = generate_remediated_pdf(result, output_dir=tmp)
            reader = PdfReader(artifact.path)
            struct_tree = reader.trailer["/Root"]["/StructTreeRoot"].get_object()
            figure = struct_tree["/K"][0].get_object()

        self.assertEqual(figure["/S"], "/Figure")
        self.assertEqual(figure["/Alt"], "")
        self.assertTrue(artifact.validation_report["structure_plan"]["mappings"][0]["decorative"])

    def test_simple_table_structure_uses_rows_and_header_cells(self):
        result = analyse_document(
            DocumentModel(
                original_filename="table.pdf",
                source_format="pdf",
                title="Table",
                language="en-AU",
                elements=[
                    DocumentElement(
                        type=ElementType.TABLE,
                        text="Revenue\t100\nCosts\t50",
                        table_headers=["Metric", "Amount"],
                    ),
                ],
            )
        )

        with tempfile.TemporaryDirectory() as tmp:
            artifact = generate_remediated_pdf(result, output_dir=tmp)
            generated = load_pdf(Path(artifact.path))
            reader = PdfReader(artifact.path)
            struct_tree = reader.trailer["/Root"]["/StructTreeRoot"].get_object()
            table = struct_tree["/K"][0].get_object()
            rows = [row_ref.get_object() for row_ref in table["/K"]]
            header_cells = [cell_ref.get_object() for cell_ref in rows[0]["/K"]]
            data_cells = [cell_ref.get_object() for cell_ref in rows[1]["/K"]]

        self.assertEqual(table["/S"], "/Table")
        self.assertEqual([row["/S"] for row in rows], ["/TR", "/TR", "/TR"])
        self.assertEqual([cell["/S"] for cell in header_cells], ["/TH", "/TH"])
        self.assertEqual([cell["/Scope"] for cell in header_cells], ["/Column", "/Column"])
        self.assertEqual([cell["/S"] for cell in data_cells], ["/TD", "/TD"])
        self.assertEqual(generated.pdf.marked_content_count, 6)
        self.assertEqual(generated.pdf.parent_tree_entry_count, 6)
        self.assertEqual(generated.pdf.structure_element_count, 10)
        self.assertEqual(artifact.validation_report["pdf_structure"]["status"], "passed")
        self.assertEqual(
            artifact.validation_report["pdf_structure"]["role_counts"],
            {"Table": 1, "TR": 3, "TH": 2, "TD": 4},
        )
        self.assertEqual(artifact.validation_report["structure_plan"]["role_counts"]["Table"], 1)
        self.assertEqual(
            artifact.validation_report["structure_plan"]["mappings"][0]["table_rows"],
            [["Metric", "Amount"], ["Revenue", "100"], ["Costs", "50"]],
        )

    def test_job_store_persists_output_artifact(self):
        with tempfile.TemporaryDirectory() as job_dir, tempfile.TemporaryDirectory() as output_dir:
            store = LocalJobStore(job_dir)
            result = analyse_document(
                DocumentModel(
                    original_filename="source.pdf",
                    source_format="pdf",
                    title="Source",
                    language="en-AU",
                    elements=[DocumentElement(type=ElementType.PARAGRAPH, text="Body text")],
                )
            )
            job = store.create(result)
            artifact = generate_remediated_pdf(job.result, output_dir=output_dir)

            updated = store.add_output_artifact(job.id, artifact)
            reloaded = store.get(job.id)

        self.assertEqual(updated.status, JobStatus.OUTPUT_GENERATED)
        self.assertEqual(len(reloaded.output_artifacts), 1)
        self.assertEqual(reloaded.output_artifacts[0].filename, "source_accessible.pdf")


if __name__ == "__main__":
    unittest.main()
