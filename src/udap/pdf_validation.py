"""PDF/UA validation integration.

The validator is optional because local development machines may not have
veraPDF installed. Missing tooling is reported explicitly in the artifact
validation result instead of being treated as success.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class PdfUaValidationResult:
    status: str
    tool: str
    passed: bool | None
    details: str
    raw: dict | None = None


def validate_pdf_ua(path: str | Path) -> PdfUaValidationResult:
    executable = shutil.which("verapdf")
    if executable is None:
        return PdfUaValidationResult(
            status="unavailable",
            tool="veraPDF",
            passed=None,
            details="veraPDF is not installed; PDF/UA validation was not run.",
        )

    command = [executable, "--format", "json", str(path)]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    raw = _parse_json(completed.stdout)

    if completed.returncode not in {0, 1}:
        return PdfUaValidationResult(
            status="error",
            tool="veraPDF",
            passed=False,
            details=completed.stderr.strip() or "veraPDF failed to run.",
            raw=raw,
        )

    passed = _extract_passed(raw)
    return PdfUaValidationResult(
        status="completed",
        tool="veraPDF",
        passed=passed,
        details="veraPDF validation completed.",
        raw=raw,
    )


def validation_to_dict(result: PdfUaValidationResult) -> dict:
    return asdict(result)


def _parse_json(output: str) -> dict | None:
    output = output.strip()
    if not output:
        return None
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError:
        return {"unparsed_output": output}
    return parsed if isinstance(parsed, dict) else {"result": parsed}


def _extract_passed(raw: dict | None) -> bool | None:
    if raw is None:
        return None

    jobs = raw.get("jobs")
    if isinstance(jobs, list) and jobs:
        validation_result = jobs[0].get("validationResult", {})
        if isinstance(validation_result, dict) and "isCompliant" in validation_result:
            return bool(validation_result["isCompliant"])

    validation_result = raw.get("validationResult")
    if isinstance(validation_result, dict) and "isCompliant" in validation_result:
        return bool(validation_result["isCompliant"])

    return None
