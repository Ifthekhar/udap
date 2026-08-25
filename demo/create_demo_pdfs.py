"""Create stable sample PDFs for customer demos.

The demo files are intentionally simple text-based PDFs so the MVP extraction
and remediation path is deterministic.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent
SAMPLE_DIR = ROOT / "samples"


def create_demo_pdfs(output_dir: str | Path = SAMPLE_DIR) -> list[Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)

    paths = [
        _create_foundation_pdf(target / "udap-demo-foundation.pdf"),
        _create_needs_review_pdf(target / "udap-demo-needs-review.pdf"),
    ]
    return paths


def _create_foundation_pdf(path: Path) -> Path:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 72), "Accessible Policy Update", fontsize=20)
    page.insert_text((72, 116), "Overview", fontsize=15)
    page.insert_text(
        (72, 148),
        "This text-based PDF has title and language metadata and is useful for showing the baseline rebuild path.",
        fontsize=11,
    )
    page.insert_text((72, 186), "Key points", fontsize=15)
    page.insert_text((72, 218), "- The source file can be analysed.", fontsize=11)
    page.insert_text((72, 238), "- The platform can rebuild a tagged PDF.", fontsize=11)
    doc.set_metadata({"title": "Accessible Policy Update"})
    doc.xref_set_key(doc.pdf_catalog(), "Lang", "(en-AU)")
    doc.save(path)
    doc.close()
    return path


def _create_needs_review_pdf(path: Path) -> Path:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 72), "Quarterly Accessibility Snapshot", fontsize=20)
    page.insert_text(
        (72, 118),
        "This demo file intentionally omits document metadata and includes review-worthy content.",
        fontsize=11,
    )
    page.insert_text((72, 150), "Read more", fontsize=11)
    page.insert_link(
        {
            "kind": pymupdf.LINK_URI,
            "from": pymupdf.Rect(72, 136, 136, 158),
            "uri": "https://example.com/accessibility-report",
        }
    )

    chart_rect = pymupdf.Rect(72, 188, 292, 286)
    chart_image = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 220, 98), False)
    chart_image.clear_with(0xE0F0F7)
    page.insert_image(chart_rect, pixmap=chart_image)
    page.draw_rect(chart_rect, color=(0.15, 0.42, 0.62), width=0.8)
    page.draw_rect(pymupdf.Rect(96, 244, 124, 270), color=(0.15, 0.42, 0.62), fill=(0.15, 0.42, 0.62))
    page.draw_rect(pymupdf.Rect(142, 220, 170, 270), color=(0.15, 0.42, 0.62), fill=(0.15, 0.42, 0.62))
    page.draw_rect(pymupdf.Rect(188, 204, 216, 270), color=(0.15, 0.42, 0.62), fill=(0.15, 0.42, 0.62))
    page.insert_text((96, 302), "Revenue  100", fontsize=11)
    page.insert_text((96, 322), "Costs    65", fontsize=11)
    page.insert_text((96, 342), "Margin   35", fontsize=11)

    page.insert_text((72, 386), "Customer actions", fontsize=15)
    page.insert_text((72, 420), "Confirm image alternative text.", fontsize=11)
    page.insert_text((72, 440), "Confirm whether the table needs headers.", fontsize=11)
    doc.save(path)
    doc.close()
    return path


if __name__ == "__main__":
    for pdf_path in create_demo_pdfs():
        print(pdf_path)
