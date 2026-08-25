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
- Optional PDF/UA validation through `veraPDF`
- Minimal logical structure tree embedding for generated PDF content
- MCID and parent-tree association checks for generated PDF tags
- Local JSON job persistence
- FastAPI endpoints for upload, analysis, job retrieval, and review
- Tests for extraction, rules, suggestions, review, and persisted jobs

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
with `/OBJR` entries and annotation `/StructParent` mappings. Full PDF/UA
compliance is not claimed yet.

## Product Docs

- `PLAN.md`
- `AGENT.md`
