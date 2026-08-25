# Universal Digital Accessibility Platform

PDF-first MVP for an AI-powered accessibility remediation platform.

The product goal is:

```text
Upload -> Analyse -> Suggest fixes -> Confirm -> Rebuild -> Validate -> Report
```

The MVP success condition is producing a meaningfully accessible PDF plus a validation report. HTML may be useful internally, but it is not a substitute deliverable.

## Current Implementation

This repository currently contains the PDF-first backend foundation:

- Neutral document model
- WCAG 2.2-oriented accessibility rule metadata
- PDF inspection and extraction signals
- Deterministic analysis engine for the first issue categories
- Remediation suggestion generation
- Accept/edit/reject review workflow
- First-pass remediated PDF generation
- Downloadable JSON accessibility/remediation report artifacts
- Optional PDF/UA validation through `veraPDF`
- Minimal logical structure tree embedding for generated PDF content
- MCID and parent-tree association checks for generated PDF tags
- Generated-PDF structural validation for tags, MCIDs, reading order, figures, links, lists, and simple tables
- Generated-output remediation summaries for fixed, remaining, manual-review, and rejected issues
- Local JSON job persistence
- FastAPI endpoints for upload, analysis, job retrieval, review, and downloads
- Backend-served workflow UI for upload, job reload, review, generation, remediation summary, human-readable report view, and artifact downloads
- Tests for extraction, rules, suggestions, review, persisted jobs, and positive/negative generated-PDF structural regression fixtures

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest
```

Run the API:

```bash
uvicorn udap.api:create_app --factory --reload
```

Open the workflow UI at:

```text
http://127.0.0.1:8000/
```

Useful endpoints:

```text
GET  /health
POST /documents/analyse
POST /documents/analyze
GET  /jobs/{job_id}
POST /jobs/{job_id}/review
POST /jobs/{job_id}/outputs/pdf
GET  /jobs/{job_id}/outputs/{artifact_id}
```

`POST /jobs/{job_id}/outputs/pdf` creates two downloadable artifacts: the rebuilt
PDF and a JSON accessibility/remediation report.

By default, local analysis jobs are stored under `.local/jobs`. Override with:

```bash
export UDAP_JOB_STORE_DIR=/path/to/jobs
```

PDF/UA validation is run with `veraPDF` when the `verapdf` command is installed.
If it is not installed, artifact reports explicitly mark PDF/UA validation as
`unavailable`.

Generated PDFs currently include title metadata, language metadata, readable text,
simple link annotations, `/MarkInfo`, a minimal `/StructTreeRoot`, marked-content
IDs, and parent-tree entries. Generated text drawing blocks are now wrapped per
logical document element, including multi-line elements that span multiple PDF
drawing blocks. Link structure elements also reference generated link annotations
with `/OBJR` entries and annotation `/StructParent` mappings. Image elements are
rebuilt as generated figure placeholders with `/Figure` structure elements and
`/Alt` text from the source model or accepted review decisions; decorative images
are marked in the structure plan and receive empty `/Alt` text. Simple text tables
are rebuilt with `/Table`, `/TR`, `/TH`, and `/TD` structure elements. List items
are grouped under `/L` containers with `/LI`, `/Lbl`, and `/LBody` structure.
Full PDF/UA compliance is not claimed yet. Generated artifact reports include a
remediation summary that separates fixed issues, remaining generated-output
issues, manual review items, and user-rejected issues. They also include
generated-PDF structural checks for the tag tree, parent-tree MCID mappings,
reading order, figure alternate text entries, link annotation references, list
hierarchy, and simple table roles.

## Product Docs

- `PLAN.md`
- `AGENT.md`
