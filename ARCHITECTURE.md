# Solution Architecture

UDAP is a PDF-first accessibility remediation MVP. The system accepts a source
document, extracts a neutral document model, runs deterministic accessibility
checks, produces reviewable remediation suggestions, records user decisions, and
generates a first-pass tagged PDF plus a machine-readable report.

The current architecture is intentionally modular: extraction, analysis,
review, persistence, PDF generation, and validation are separated so each layer
can improve without rewriting the whole product.

## Architecture At A Glance

```text
Browser UI            CLI
   |                   |
   | HTTP              | local file path
   v                   v
FastAPI API        cli.py
   |                   |
   +-------> extractors.load_document()
                    |
                    v
             DocumentModel
                    |
                    v
          pipeline.analyse_document()
                    |
       +------------+-------------+
       |                          |
 rules.evaluate_document()   suggestions.generate_remediation_suggestions()
       |                          |
       +------------+-------------+
                    v
              AnalysisResult
                    |
                    v
          LocalJobStore JSON files
                    |
          review.record_user_decisions()
                    |
                    v
       pdf_output.generate_remediated_pdf_outputs()
                    |
       +------------+-------------+
       |                          |
  Generated PDF              JSON report
       |
       v
 pdf_tagging.apply_minimal_structure_tree()
       |
       v
 pdf_validation structural checks + optional veraPDF
```

## Runtime Flows

### Analyse A Document

1. A user uploads a `.pdf` or `.docx` file through the backend-served UI, or a
   developer runs the CLI against a local file.
2. `extractors.load_document()` chooses the appropriate extractor by file
   extension.
3. PDF files are inspected by `pdf_inspection.inspect_pdf()` for metadata,
   tagging signals, page count, images, links, text blocks, marked content, and
   structure-tree indicators.
4. The extractor returns a `DocumentModel`, which is the internal source of truth
   for analysis. PDF extraction currently uses layout/text heuristics to infer
   headings, paragraphs, simple tables, links, images, confidence scores, and
   source locations.
5. `pipeline.analyse_document()` evaluates the model with deterministic rules
   and generates remediation suggestions.
6. API requests persist the result as an `AnalysisJob` in `LocalJobStore`.

### Review Suggestions

1. The UI loads a job report from `GET /jobs/{job_id}`.
2. The user accepts, edits, or rejects suggestions.
3. `POST /jobs/{job_id}/review` converts the payload into `UserDecision`
   records.
4. `review.record_user_decisions()` updates issue final statuses and appends
   audit events. Decisions are immutable audit history, not direct in-place
   edits to the original source model.
5. `LocalJobStore` saves the updated job.

### Generate Outputs

1. `POST /jobs/{job_id}/outputs/pdf` loads the reviewed job.
2. `pdf_output.generate_remediated_pdf_outputs()` creates two artifacts:
   a rebuilt PDF and a JSON accessibility report.
3. The generated PDF is rebuilt from `DocumentModel` content rather than patched
   directly in place. It writes title and language metadata, readable text,
   simple links, image placeholders, simple tables, and list items.
4. `pdf_tagging.apply_minimal_structure_tree()` adds `/MarkInfo`, a minimal
   `/StructTreeRoot`, parent-tree entries, MCID marked content, figure `/Alt`
   text, link `/OBJR` references, list roles, and simple table roles.
5. `pdf_validation.validate_generated_pdf_structure()` verifies the relationships
   this MVP writes itself. `validate_pdf_ua()` also runs veraPDF when the
   `verapdf` executable is installed.
6. Artifacts are added to the persisted job and can be downloaded through
   `GET /jobs/{job_id}/outputs/{artifact_id}`.

## Main Modules

`src/udap/models.py` defines the domain model. Important types include
`DocumentModel`, `DocumentElement`, `PdfInspection`, `AccessibilityIssue`,
`RemediationSuggestion`, `UserDecision`, `AuditEvent`, `AnalysisResult`,
`AnalysisJob`, and `OutputArtifact`.

`src/udap/extractors.py` is the input boundary. It loads PDF and DOCX sources and
converts them into the neutral model. Third-party dependencies are optional at
import time and are checked when a format-specific extractor runs.

`src/udap/pdf_inspection.py` gathers PDF-specific signals before remediation. It
uses `pypdf` for catalog, metadata, structure-tree, parent-tree, and marked
content signals, and PyMuPDF for page-level text, image, and link counts.

`src/udap/standards.py` stores rule metadata for the MVP WCAG 2.2 AA checks.
`src/udap/rules.py` contains the deterministic rule engine that turns document
model conditions into `AccessibilityIssue` instances.

`src/udap/suggestions.py` maps issues to remediation suggestions. The current
implementation is deterministic but shaped like a future AI provider boundary:
each suggestion has an action, source, proposed value, explanation, confidence,
and review requirement.

`src/udap/review.py` applies user decisions to analysis results. It updates issue
statuses and records audit events for traceability.

`src/udap/pipeline.py` is the high-level analysis/reporting orchestrator. It
runs rules, creates suggestions, records suggestion audit events, and builds the
JSON report shape returned by both the API and CLI.

`src/udap/job_store.py` persists `AnalysisJob` records as JSON files under
`.local/jobs` by default. The API can override this with `UDAP_JOB_STORE_DIR`.

`src/udap/serialization.py` converts persisted JSON back into dataclass and enum
instances.

`src/udap/pdf_output.py` generates rebuilt PDFs and JSON report artifacts. It
also re-analyses generated output and adds remediation summaries, internal PDF
structure validation, and optional PDF/UA validation results.

`src/udap/pdf_tagging.py` writes the minimal logical PDF structure tree for
generated PDFs. It is a stepping stone toward PDF/UA, not a full PDF/UA engine.

`src/udap/pdf_validation.py` contains two validation paths: optional veraPDF
integration and internal structure checks for tag-tree presence, marked content,
parent-tree mappings, reading order, figures, links, lists, and simple tables.

`src/udap/api.py` exposes the FastAPI application, static UI assets, job review
endpoints, output generation, and artifact downloads.

`src/udap/ui.py` contains the backend-served HTML, CSS, and JavaScript for the
demo workflow. There is no separate frontend build pipeline yet.

`src/udap/cli.py` provides a local developer CLI for running analysis and
printing JSON reports.

`demo/` contains controlled customer demo PDFs, sample-generation scripts, demo
instructions, and an automated rehearsal script.

`tests/` contains focused coverage for extraction, rules, suggestions, review,
job persistence, API jobs, PDF output, PDF tagging, PDF validation, structure
regressions, and demo rehearsal.

## Data Model

`DocumentModel` is the neutral internal representation. It stores source
metadata, source format, optional PDF inspection data, and a tree of
`DocumentElement` instances.

`DocumentElement` represents semantic content such as headings, paragraphs,
images, links, tables, and list items. Each element carries source location,
confidence, optional accessibility metadata, and free-form extraction metadata.

`AccessibilityIssue` is the rule-engine output. It includes rule id, issue type,
severity, location, explanation, suggested fix, confidence, automation status,
and final review status.

`RemediationSuggestion` is the reviewable proposed action for an issue. The
suggestion can come from a rule, an AI-assisted boundary, or the user.

`UserDecision` captures accept, edit, and reject review actions. Decisions are
converted to `AuditEvent` entries so the final report can explain what happened.

`AnalysisResult` groups the document, target standard, issues, suggestions, and
audit events. `AnalysisJob` wraps that result with job status, timestamps, and
generated output artifacts.

## Persistence And Files

The default local job store is `.local/jobs`. Each job is stored as a JSON file
named by job id. Generated output artifacts are written under `.local/outputs`
by default.

The FastAPI upload endpoint writes incoming files to a temporary file only long
enough to extract the document model. The persisted job stores the model and
analysis state, not the original uploaded file.

The API returns artifact metadata from the persisted job and streams artifact
files from their stored paths. Artifact ids are generated UUIDs and should be
treated as opaque.

## PDF Strategy

PDF is the first-priority deliverable. HTML is not the primary remediation path
for this MVP.

The system currently rebuilds a PDF from the extracted model instead of trying
to surgically repair the original PDF. That makes the output pipeline easier to
reason about and gives the code direct control over text drawing, metadata,
links, structure roles, MCIDs, parent-tree entries, and validation reports.

Generated PDFs currently target a useful tagged-output baseline. They include
document title, language, readable text, simple links, figures with alternate
text, simple table roles, list structure, `/MarkInfo`, `/StructTreeRoot`, marked
content IDs, and parent-tree mappings. The code does not claim full PDF/UA
compliance yet.

The main technical risk is source extraction quality. Real customer PDFs can
have complex reading order, scanned content, nested tables, artifacts, forms,
footnotes, sidebars, and decorative elements. Those cases should improve at the
extraction/modeling layer before the output layer tries to generate a final PDF.

## API Surface

`GET /` serves the current demo UI.

`GET /health` returns a simple health check.

`POST /documents/analyse` and `POST /documents/analyze` accept a PDF or DOCX
upload, run extraction and analysis, persist a job, and return the job report.

`GET /jobs/{job_id}` returns the persisted job report.

`POST /jobs/{job_id}/review` applies review decisions to suggestions.

`POST /jobs/{job_id}/outputs/pdf` generates the rebuilt PDF and JSON report.

`GET /jobs/{job_id}/outputs/{artifact_id}` downloads a generated artifact.

`POST /reviews/apply` is a compatibility endpoint for review payloads.

## Extension Points

Improve real-world PDF extraction in `extractors.py` and `pdf_inspection.py`
before expanding output claims. This is where reading order, OCR routing,
artifact detection, form fields, tables, lists, and image semantics should
become more robust.

Add new rules by defining metadata in `standards.py` and evaluation logic in
`rules.py`. Keep deterministic checks separate from AI-assisted suggestions.

Replace or augment deterministic suggestion generation in `suggestions.py` with
an AI provider behind the existing suggestion contract.

Move beyond local JSON persistence by replacing `LocalJobStore` with a database
or object-storage-backed implementation that preserves the `AnalysisJob`
contract.

Split `ui.py` into a real frontend application when the demo UI needs routing,
state management, authentication, or richer review tools.

Add background processing when PDF extraction or generation becomes too slow for
synchronous HTTP requests.

## Developer Commands

Install dependencies:

```bash
pip install -e '.[dev]'
```

Run tests:

```bash
pytest -q
```

Run the API and UI:

```bash
uvicorn udap.api:create_app --factory --reload
```

Run local analysis:

```bash
python -m udap.cli path/to/document.pdf --pretty
```

Rehearse the controlled demo:

```bash
python demo/rehearse_demo.py
```

## Current Non-Goals

The current implementation does not guarantee legal compliance.

The current PDF generator does not preserve original visual fidelity.

The current UI is a backend-served demo workflow, not a production frontend.

The current store is local JSON persistence, not multi-user production storage.

The current DOCX path exists for model validation and basic analysis, but the
product direction remains PDF-first.
