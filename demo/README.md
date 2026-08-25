# Customer Demo Guide

Use this folder to run a predictable PDF-first demo.

## Demo Files

- `samples/udap-demo-foundation.pdf`
  - Shows the baseline PDF rebuild path.
  - Expected finding: source PDF is not tagged.
- `samples/udap-demo-needs-review.pdf`
  - Shows the review workflow.
  - Expected findings: untagged PDF, missing title, missing language, missing image alt text, and weak link text.

Regenerate the samples with:

```bash
python demo/create_demo_pdfs.py
```

## UI Demo Flow

1. Start the app:

```bash
uvicorn udap.api:create_app --factory --reload
```

2. Open:

```text
http://127.0.0.1:8000/
```

3. Upload `demo/samples/udap-demo-needs-review.pdf`.
4. Point out the detected issues and review suggestions.
5. Accept the automatic fixes.
6. Edit the language suggestion to `en-AU`.
7. Edit the image alt text suggestion to `Bar chart showing quarterly accessibility progress.`
8. Edit the link text suggestion to `Read the quarterly accessibility report`.
9. Apply review.
10. Generate PDF and report.
11. Download the accessible PDF and remediation report.

## Customer-Safe Talk Track

This demo shows automated accessibility remediation for text-based PDFs. It
rebuilds the PDF with accessibility metadata, logical structure, marked content,
links, lists, tables where detected, and a machine-readable report.

Do not say this guarantees legal compliance. Say:

```text
The generated output passed the platform's automated structural checks. Some accessibility requirements still require human review and external validation.
```

## Automated Rehearsal

Run:

```bash
python demo/rehearse_demo.py
```

Expected result:

```text
Final status: output_generated
PDF structure: passed
Reading order: passed
```
