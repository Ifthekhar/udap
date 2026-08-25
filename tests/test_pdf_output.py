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
    UserDecision,
)
from udap.pdf_output import generate_remediated_pdf
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
        self.assertNotIn(
            "untagged_pdf",
            artifact.validation_report["summary"]["issue_type_counts"],
        )

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
