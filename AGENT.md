# Agent Guide

## Project Context

This project is an AI-powered digital accessibility platform.

The product goal is to let a user upload a digital document, select an accessibility standard and output format, review AI-suggested fixes where needed, then download an accessible version plus an accessibility report.

Core product loop:

```text
Upload -> Analyse -> Suggest fixes -> Confirm -> Rebuild -> Validate -> Report
```

This is not intended to be only an accessibility checker. The differentiator is accessibility remediation and transformation.

## Current Planning Source

Use `PLAN.md` as the primary planning document.

When implementation decisions are unclear, prefer the MVP direction in `PLAN.md`:

```text
DOCX/PDF input -> Accessible PDF output -> Validation report
```

Accessible PDF is the first-priority user-facing output and the make-or-break MVP capability. If the platform cannot produce a meaningfully accessible PDF, accessible HTML does not prove the product. The implementation may use intermediate HTML or DOCX internally if useful, but HTML must not be treated as a substitute MVP deliverable.

## MVP Boundaries

Prioritize:

- DOCX input
- Text-based PDF input
- Accessible PDF output
- WCAG 2.2 A and AA checks
- Human review for uncertain AI-generated fixes
- Final validation report
- Clear audit trail

Avoid expanding early into:

- Full country-specific standards
- Organisation-specific rules
- PowerPoint, Excel, EPUB, and complex publishing formats
- Complex scanned documents
- Complex fillable PDF forms
- Standalone accessible HTML export before accessible PDF is proven
- Legal compliance guarantees

## Product Principles

- Keep the user shielded from accessibility implementation complexity.
- Explain accessibility problems in plain language.
- Separate automatically fixable issues from issues needing user judgement.
- Never claim guaranteed legal compliance.
- Say "passed automated validation checks" or "aligned with selected rules" instead of promising legal compliance.
- Treat AI output as assistive and reviewable, not as unquestionable truth.
- Keep accessibility standards as structured rules, separate from AI prompts and model behavior.

## Architecture Principles

Build around a neutral intermediate document model.

Input formats should be parsed into structured content before remediation or reconstruction. The model should preserve:

- Text content
- Document structure
- Source location
- Reading order
- Accessibility properties
- Confidence scores
- Remediation history

Keep these concerns separate:

- Ingestion
- Document understanding
- Accessibility rules
- AI remediation
- User review
- Reconstruction
- Validation
- Reporting

Do not hard-code standards directly into remediation code. A rule should be represented as structured data wherever practical.

## Suggested Stack Direction

Unless the project later chooses something else, assume:

- Frontend: Next.js, React, TypeScript
- Backend: Python, FastAPI
- Database: PostgreSQL
- Background jobs: Redis plus Celery or RQ
- Development storage: local filesystem
- Production storage: S3-compatible object storage
- DOCX processing: python-docx and OOXML inspection when needed
- PDF processing: PyMuPDF, pdfplumber, pypdf
- PDF validation: veraPDF for accessible PDF checks
- PDF structural checks for tags, reading order, language, metadata, links, images, headings, and tables
- HTML validation: axe-core or pa11y only if an HTML export or intermediate validation path is added

## Implementation Guidance

- Prefer small, testable modules over one large document-processing function.
- Design processing as a job pipeline with explicit states.
- Store original files separately from generated output artifacts.
- Preserve an audit trail for every detected issue, suggestion, user decision, remediation, and validation result.
- Use confidence scores for extraction and AI-generated suggestions.
- Require user confirmation for meaningful image alt text, charts, diagrams, policy content, legal content, medical content, financial content, and any ambiguous document meaning.
- Generate machine-readable data first, then render UI and reports from that data.

## Accessibility Issue Categories

Start with:

- Missing document title or metadata
- Missing document language
- Missing or weak heading structure
- Incorrect heading order
- Missing image alt text
- Decorative image identification
- Weak or unclear link text
- Simple table header issues
- Lists not represented as lists
- Basic reading order issues
- Basic color contrast issues where detectable

Each issue should include:

- Issue type
- Severity
- Related standard or rule
- Source location
- Plain-language explanation
- Suggested fix
- Confidence
- Automation status
- User decision
- Final status

## Validation Rules

Always validate generated output after remediation.

The pipeline should be:

```text
Analyse -> Remediate -> Generate -> Validate -> Report
```

Validation reports must distinguish:

- Issues fixed automatically
- Issues fixed after user confirmation
- Issues rejected by the user
- Issues that remain unresolved
- Checks that could not be automated

## UI Guidance

Build the real workflow first, not a marketing landing page.

Primary screens:

- Upload
- Configuration
- Analysis progress
- Accessibility assessment
- Human review
- Results and downloads

The UI should feel operational, clear, and trustworthy. Prioritize scanability, accessible controls, keyboard usability, strong contrast, and visible processing states.

## Testing Guidance

Use sample documents to test the full loop.

Create fixtures for:

- A clean accessible document
- A document with missing headings
- A document with images missing alt text
- A document with weak link text
- A document with simple table header problems
- A text-based PDF with extractable content

Tests should cover:

- File type detection
- Document model extraction
- Rule evaluation
- Issue generation
- Remediation suggestion storage
- User decision handling
- Output generation
- Validation report generation

## Documentation Guidance

Keep project docs current as decisions are made.

Recommended docs:

- `PLAN.md`
- `PRD.md`
- `ARCHITECTURE.md`
- `MVP_BACKLOG.md`
- `DECISIONS.md`

When adding a major technical choice, document:

- Decision
- Rationale
- Alternatives considered
- Tradeoffs

## Working Style

- Keep changes scoped.
- Prefer implementation that proves the product loop over broad infrastructure.
- Do not introduce unsupported standards or formats casually.
- Do not bury business logic inside UI components.
- Do not make AI prompts the only representation of accessibility logic.
- Favor clear, inspectable data structures.
- Be careful with claims, reporting language, and user trust.
