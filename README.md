# Universal Digital Accessibility Platform

PDF-first MVP for an AI-powered accessibility remediation platform.

The product goal is:

```text
Upload -> Analyse -> Suggest fixes -> Confirm -> Rebuild -> Validate -> Report
```

The MVP success condition is producing a meaningfully accessible PDF plus a validation report. HTML may be useful internally, but it is not a substitute deliverable.

## Current Implementation

This repository currently contains the first backend foundation:

- Neutral document model
- WCAG 2.2-oriented accessibility rule metadata
- Deterministic analysis engine for the first issue categories
- FastAPI app skeleton
- Standard-library tests for the core rule engine

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

## Product Docs

- `PLAN.md`
- `AGENT.md`
