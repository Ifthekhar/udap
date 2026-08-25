"""Reusable generated-PDF regression cases for Milestone 7 hardening."""

from __future__ import annotations

from dataclasses import dataclass, field

from udap.models import DocumentElement, DocumentModel, ElementType


@dataclass(frozen=True)
class PdfRegressionCase:
    name: str
    document: DocumentModel
    expected_top_level_roles: dict[str, int]
    expected_role_counts: dict[str, int]
    expected_marked_content_count: int
    expected_parent_tree_entry_count: int
    expected_structure_element_count: int
    expected_page_count: int | None = None
    expected_figure_alt: str | None = None
    expected_link_count: int = 0
    expected_table_count: int = 0
    expected_list_count: int = 0
    expected_wrapped_mcid_count: int | None = None
    minimum_text_block_count: int | None = None
    expected_checks: set[str] = field(
        default_factory=lambda: {
            "structure.root_present",
            "structure.mark_info_marked",
            "structure.mcid_parent_tree",
            "structure.figures_have_alt",
            "structure.links_reference_annotations",
            "structure.link_annotations_mapped",
            "structure.tables_have_roles",
            "structure.lists_have_roles",
            "structure.reading_order_matches_plan",
            "structure.matches_plan",
        }
    )


def generated_pdf_regression_cases() -> list[PdfRegressionCase]:
    long_paragraph = (
        "This paragraph is intentionally long enough to wrap across multiple generated PDF text "
        "drawing blocks while remaining one logical paragraph in the structure tree."
    )

    return [
        PdfRegressionCase(
            name="heading_paragraph",
            document=DocumentModel(
                original_filename="heading-paragraph.pdf",
                source_format="pdf",
                title="Heading Paragraph",
                language="en-AU",
                elements=[
                    DocumentElement(
                        type=ElementType.HEADING,
                        text="Annual Report 2026",
                        heading_level=1,
                    ),
                    DocumentElement(type=ElementType.PARAGRAPH, text="Accessible summary text."),
                ],
            ),
            expected_top_level_roles={"H1": 1, "P": 1},
            expected_role_counts={"H1": 1, "P": 1},
            expected_marked_content_count=2,
            expected_parent_tree_entry_count=2,
            expected_structure_element_count=2,
            expected_page_count=1,
        ),
        PdfRegressionCase(
            name="link_annotation",
            document=DocumentModel(
                original_filename="link-annotation.pdf",
                source_format="pdf",
                title="Link Annotation",
                language="en-AU",
                elements=[
                    DocumentElement(
                        type=ElementType.LINK,
                        text="Read the accessibility report",
                        href="https://example.com/report",
                    )
                ],
            ),
            expected_top_level_roles={"Link": 1},
            expected_role_counts={"Link": 1},
            expected_marked_content_count=1,
            expected_parent_tree_entry_count=2,
            expected_structure_element_count=1,
            expected_page_count=1,
            expected_link_count=1,
        ),
        PdfRegressionCase(
            name="figure_alt",
            document=DocumentModel(
                original_filename="figure-alt.pdf",
                source_format="pdf",
                title="Figure Alt",
                language="en-AU",
                elements=[
                    DocumentElement(
                        type=ElementType.IMAGE,
                        alt_text="Bar chart comparing quarterly revenue.",
                    )
                ],
            ),
            expected_top_level_roles={"Figure": 1},
            expected_role_counts={"Figure": 1},
            expected_marked_content_count=1,
            expected_parent_tree_entry_count=1,
            expected_structure_element_count=1,
            expected_page_count=1,
            expected_figure_alt="Bar chart comparing quarterly revenue.",
        ),
        PdfRegressionCase(
            name="decorative_figure",
            document=DocumentModel(
                original_filename="decorative-figure.pdf",
                source_format="pdf",
                title="Decorative Figure",
                language="en-AU",
                elements=[DocumentElement(type=ElementType.IMAGE, decorative=True)],
            ),
            expected_top_level_roles={"Figure": 1},
            expected_role_counts={"Figure": 1},
            expected_marked_content_count=1,
            expected_parent_tree_entry_count=1,
            expected_structure_element_count=1,
            expected_page_count=1,
            expected_figure_alt="",
        ),
        PdfRegressionCase(
            name="simple_table",
            document=DocumentModel(
                original_filename="simple-table.pdf",
                source_format="pdf",
                title="Simple Table",
                language="en-AU",
                elements=[
                    DocumentElement(
                        type=ElementType.TABLE,
                        text="Revenue\t100\nCosts\t50",
                        table_headers=["Metric", "Amount"],
                    )
                ],
            ),
            expected_top_level_roles={"Table": 1},
            expected_role_counts={"Table": 1, "TR": 3, "TH": 2, "TD": 4},
            expected_marked_content_count=6,
            expected_parent_tree_entry_count=6,
            expected_structure_element_count=10,
            expected_page_count=1,
            expected_table_count=1,
        ),
        PdfRegressionCase(
            name="simple_list",
            document=DocumentModel(
                original_filename="simple-list.pdf",
                source_format="pdf",
                title="Simple List",
                language="en-AU",
                elements=[
                    DocumentElement(type=ElementType.LIST_ITEM, text="Check source metadata."),
                    DocumentElement(type=ElementType.LIST_ITEM, text="Generate tagged PDF output."),
                ],
            ),
            expected_top_level_roles={"LI": 2},
            expected_role_counts={"L": 1, "LI": 2, "Lbl": 2, "LBody": 2},
            expected_marked_content_count=2,
            expected_parent_tree_entry_count=2,
            expected_structure_element_count=7,
            expected_page_count=1,
            expected_list_count=1,
        ),
        PdfRegressionCase(
            name="wrapped_paragraph",
            document=DocumentModel(
                original_filename="wrapped-paragraph.pdf",
                source_format="pdf",
                title="Wrapped Paragraph",
                language="en-AU",
                elements=[DocumentElement(type=ElementType.PARAGRAPH, text=long_paragraph)],
            ),
            expected_top_level_roles={"P": 1},
            expected_role_counts={"P": 1},
            expected_marked_content_count=1,
            expected_parent_tree_entry_count=1,
            expected_structure_element_count=1,
            expected_page_count=1,
            expected_wrapped_mcid_count=1,
            minimum_text_block_count=2,
        ),
        PdfRegressionCase(
            name="multi_page_parent_tree",
            document=DocumentModel(
                original_filename="multi-page-parent-tree.pdf",
                source_format="pdf",
                title="Multi Page Parent Tree",
                language="en-AU",
                elements=[
                    DocumentElement(
                        type=ElementType.PARAGRAPH,
                        text=f"Regression paragraph {index + 1}.",
                    )
                    for index in range(40)
                ],
            ),
            expected_top_level_roles={"P": 40},
            expected_role_counts={"P": 40},
            expected_marked_content_count=40,
            expected_parent_tree_entry_count=40,
            expected_structure_element_count=40,
            expected_page_count=2,
        ),
    ]
