# AI-Powered Universal Digital Accessibility Platform - Plan

## 1. Product Goal

Build an AI-powered platform that transforms ordinary digital documents into accessible, standards-aligned documents.

The platform should let a user upload a document, choose a target accessibility standard and output format, review AI-suggested fixes where human judgement is needed, then download an accessible version plus an accessibility report.

The core product loop is:

```text
Upload -> Analyse -> Suggest fixes -> Confirm -> Rebuild -> Validate -> Report
```

## 2. Product Positioning

This should not be only an accessibility checker.

Most accessibility tools tell users what is wrong. This platform should:

- Identify accessibility issues.
- Explain them in plain language.
- Automatically fix issues where safe.
- Ask for user confirmation where meaning or judgement is required.
- Reconstruct the document into an accessible output.
- Validate the generated output.
- Produce a clear remediation and validation report.

## 3. MVP Scope

The first version should prove the core transformation engine without trying to support every format, standard, or jurisdiction.

### MVP Inputs

- DOCX
- Text-based PDF
- Simple image-based documents only if OCR is easy to add later

### MVP Outputs

Priority:

1. Accessible PDF
2. Accessibility validation report
3. Accessible DOCX only if it helps support the PDF remediation workflow

Accessible PDF is the first product priority and the make-or-break MVP capability. If the platform cannot produce a meaningfully accessible PDF, then producing accessible HTML does not prove the core product. The implementation may use intermediate HTML or DOCX internally if that improves PDF reconstruction and validation, but HTML should not be treated as a substitute MVP deliverable.

### MVP Accessibility Standard

- WCAG 2.2
- Level A
- Level AA

Level AA should be the primary product path. Level AAA can be shown as a future option but should not be the first build target.

### MVP Issue Types

Start with issues that are common, valuable, and reasonably automatable:

- Missing document title or metadata
- Missing document language
- Missing or weak heading structure
- Incorrect heading order
- Missing image alt text
- Decorative image identification
- Weak or unclear link text
- Simple table header issues
- Reading order problems in simple documents
- Untagged or poorly structured content
- Basic color contrast issues where detectable

### Out of Scope for MVP

- Full country-specific standards library
- Organisation-specific custom standards
- PowerPoint, Excel, EPUB, and complex publishing formats
- Fully automated legal compliance claims
- Complex scanned documents with poor OCR quality
- Complex charts, maps, diagrams, and infographics without human review
- Complex fillable PDF forms
- Multimedia captions and transcripts
- Standalone accessible HTML export before accessible PDF is proven

## 4. Key User Journey

1. User uploads a document.
2. Platform detects file type and extracts document content.
3. User selects:
   - Output format
   - WCAG version
   - Conformance level
4. Platform analyses the document.
5. Platform displays an accessibility assessment.
6. Platform separates issues into:
   - Automatically fixable
   - Needs user confirmation
   - Cannot safely be automated
7. User reviews AI suggestions.
8. User accepts, edits, or rejects suggestions.
9. Platform remediates approved issues.
10. Platform generates the requested output.
11. Platform validates the output.
12. User downloads:
   - Accessible document
   - Accessibility report

## 5. Main Screens

### Upload Screen

- File upload
- Supported formats
- Basic file validation
- Upload progress

### Configuration Screen

- Output format selector
- Standard selector
- WCAG version selector
- Conformance level selector

### Analysis Progress Screen

- Processing state
- Current stage
- Clear failure messages

### Accessibility Assessment Screen

- Issue count
- Issue categories
- Severity
- Related standard or success criterion
- Suggested action
- Confidence level

### Human Review Screen

- Issue explanation
- Original content context
- AI-suggested fix
- Accept, edit, or reject controls

### Results Screen

- Final validation status
- Download accessible document
- Download report
- Remaining issues
- Audit trail summary

## 6. Core Architecture

### 6.1 Document Ingestion Engine

Responsibilities:

- Accept uploads.
- Store original files.
- Detect file type.
- Extract basic metadata.
- Reject unsupported or unsafe files.
- Create a processing job.

### 6.2 Document Understanding Engine

Responsibilities:

- Extract text.
- Detect headings.
- Extract images.
- Extract tables.
- Extract links.
- Infer reading order.
- Identify document structure.
- Convert source files into a neutral internal representation.

### 6.3 Intermediate Document Model

This is the heart of the platform.

All input formats should be converted into a structured internal model before remediation or reconstruction.

Example model concepts:

- Document
- Page
- Section
- Heading
- Paragraph
- List
- Table
- Table row
- Table cell
- Image
- Link
- Form field
- Metadata
- Reading order node

The model should preserve:

- Text content
- Structure
- Source location
- Confidence scores
- Accessibility properties
- Remediation history

### 6.4 Accessibility Rules Engine

Responsibilities:

- Store standards separately from AI logic.
- Map rules to tests.
- Map tests to issue types.
- Map issue types to remediation strategies.

Rules should eventually support:

- Jurisdiction
- Framework
- Version
- Conformance level
- Success criterion
- Requirement
- Test
- Remediation rule

MVP can start with a small WCAG 2.2 AA rule set.

### 6.5 AI Remediation Engine

Responsibilities:

- Generate image alt text.
- Suggest better link text.
- Suggest heading structure repairs.
- Explain issues in plain language.
- Classify whether a fix is safe to automate.
- Generate user-review prompts.

The AI layer should not be the source of truth for standards. It should operate against structured rules supplied by the rules engine.

### 6.6 Reconstruction Engine

Responsibilities:

- Generate tagged accessible PDF as the primary output.
- Generate accessible DOCX only where it supports the remediation workflow or a later product requirement.
- Generate intermediate HTML only as an internal representation when useful for reconstruction or validation.
- Preserve meaningful content and structure.
- Apply approved remediations.

### 6.7 Validation Engine

Responsibilities:

- Re-test generated output.
- Compare before and after issue counts.
- Produce validation results.
- Flag remaining issues.
- Prevent unsupported "guaranteed compliant" claims.

### 6.8 Reporting Engine

Responsibilities:

- Generate human-readable reports.
- Generate machine-readable reports.
- Include:
  - Original filename
  - Target standard
  - Version
  - Conformance level
  - Issues detected
  - Issues fixed automatically
  - Issues confirmed by user
  - Remaining issues
  - Validation results
  - Date and time
  - Remediation summary

## 7. Suggested Tech Stack

### Frontend

- Next.js
- React
- TypeScript
- Tailwind CSS or another accessible component system

### Backend

- Python
- FastAPI
- PostgreSQL
- SQLAlchemy or SQLModel
- Redis
- Celery or RQ for background jobs

### File Storage

- Local storage for development
- S3-compatible object storage for production

### Document Processing

- DOCX: python-docx, Mammoth-style extraction, OOXML inspection where needed
- PDF: PyMuPDF, pdfplumber, pypdf
- HTML: internal semantic representation only where useful
- OCR later: OCRmyPDF, Tesseract, or a cloud OCR provider

### Accessibility Validation

- PDF: veraPDF for PDF/UA checks
- PDF structural checks for tags, reading order, language, metadata, links, images, headings, and tables
- HTML: axe-core or pa11y only if an HTML export or intermediate validation path is added
- Custom rules for document model validation

### AI

- LLM for structured reasoning and remediation suggestions
- Vision-capable model for image understanding and alt text
- Strict structured outputs for issue classification and remediation plans

## 8. Data Model Draft

Core entities:

- User
- Project
- Document
- DocumentVersion
- ProcessingJob
- AccessibilityStandard
- AccessibilityRule
- AccessibilityIssue
- RemediationSuggestion
- UserDecision
- ValidationRun
- AccessibilityReport
- OutputArtifact

Important issue fields:

- id
- document_id
- standard_id
- rule_id
- issue_type
- severity
- source_location
- original_content
- explanation
- suggested_fix
- confidence
- automation_status
- user_decision
- final_status

## 9. Job Pipeline

```text
1. upload_received
2. file_validated
3. content_extracted
4. document_model_created
5. accessibility_analysis_completed
6. remediation_suggestions_created
7. waiting_for_user_review
8. approved_remediations_applied
9. output_generated
10. validation_completed
11. report_generated
12. ready_for_download
```

## 10. Milestones

### Milestone 1: Planning and Foundation

- Create PRD.
- Create technical architecture.
- Define MVP rule set.
- Define intermediate document model.
- Choose stack.
- Create sample test documents.

### Milestone 2: Upload and Extraction

- Build upload flow.
- Store original files.
- Extract DOCX content.
- Extract text-based PDF content.
- Create first internal document model.

### Milestone 3: Accessibility Analysis

- Implement WCAG 2.2 AA rule subset.
- Detect missing language and metadata.
- Detect heading issues.
- Detect images without alt text.
- Detect weak links.
- Detect basic table issues.
- Show assessment dashboard.

### Milestone 4: AI Suggestions and Review

- Generate alt text suggestions.
- Generate heading repair suggestions.
- Generate link text suggestions.
- Build accept, edit, reject workflow.
- Store audit trail.

### Milestone 5: Accessible PDF Output

- Generate tagged accessible PDF from the internal model or from a controlled accessible source format.
- Apply accepted remediations.
- Preserve headings, reading order, alt text, tables, links, language, and metadata.
- Validate with PDF/UA tooling where possible.
- Run structural checks for the selected WCAG rule subset.
- Generate report.

### Milestone 6: DOCX Output

- Generate accessible DOCX.
- Preserve headings, lists, tables, alt text, language, and metadata.
- Validate as much as possible with automated and structural checks.

### Milestone 7: PDF Hardening

- Improve tagged PDF generation quality.
- Add more PDF/UA-oriented structural checks.
- Expand coverage for headings, lists, links, image alternatives, tables, and reading order.
- Add regression fixtures for generated accessible PDFs.

## 11. Acceptance Criteria for MVP

- User can upload a supported document.
- User can select output format.
- User can select WCAG version and conformance level.
- System analyses the uploaded document.
- System identifies accessibility issues.
- System maps issues to the selected standard.
- System separates automatically fixable issues from human-review issues.
- System explains issues in plain language.
- User can accept, edit, or reject AI recommendations.
- System applies approved remediations.
- System generates an accessible output file.
- System performs a second validation.
- System generates an accessibility report.
- User can download final artifacts.
- System maintains an audit trail.

## 12. Risk Register

### Accessible PDF Generation

Generating truly accessible PDFs is hard, but PDF is the product's first-priority output. Plan for extra engineering and validation effort around tags, reading order, metadata, language, headings, tables, links, and PDF/UA checks.

### Legal Compliance Claims

The platform should not claim guaranteed legal compliance. Use careful language such as "passed automated validation checks" or "aligned with selected accessibility rules."

### AI Hallucination

Standards and rules must be structured and deterministic. AI should suggest remediations, not invent requirements.

### Alt Text Quality

AI-generated alt text may be wrong or incomplete. Require user confirmation for meaningful images, charts, diagrams, and content with legal, medical, financial, or policy meaning.

### Complex Documents

Scanned files, complex PDFs, charts, tables, forms, and multi-column layouts may fail extraction. Track confidence and ask for review when needed.

### Validation Limits

Automated validation cannot prove every accessibility requirement. Reports must clearly distinguish machine-checkable results from human-review items.

## 13. First Build Tasks

1. Create `PRD.md`.
2. Create `ARCHITECTURE.md`.
3. Create `MVP_BACKLOG.md`.
4. Create sample documents for testing.
5. Scaffold frontend and backend.
6. Implement upload endpoint.
7. Implement document storage.
8. Implement DOCX text and structure extraction.
9. Implement text-based PDF extraction.
10. Define the first intermediate document model.
11. Implement first WCAG 2.2 AA rules.
12. Build first assessment screen.

## 14. Initial Rule Set

Start with a compact rule set that is useful and testable:

- Document has a title.
- Document has a language.
- Headings are present where structure exists.
- Heading levels do not skip unexpectedly.
- Images have alt text or are marked decorative.
- Links have meaningful text.
- Tables have identifiable headers.
- Lists are represented as lists.
- Reading order can be derived with acceptable confidence.
- Generated PDF has tags, language, title metadata, reading order, image alternatives, and table structure where applicable.

## 15. Naming

Working project name:

```text
Universal Digital Accessibility Platform
```

Potential shorter names can be explored later.

## 16. Immediate Next Decision

First output target:

Recommended:

```text
DOCX/PDF input -> Accessible PDF output -> Validation report
```

This path focuses the MVP on the highest-priority user outcome. HTML may be useful internally, but it should not be used to redefine success away from accessible PDF.
