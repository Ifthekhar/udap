"""Local persisted job store for the Milestone 4 review workflow."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .models import (
    AnalysisJob,
    AnalysisResult,
    IssueStatus,
    JobStatus,
    OutputArtifact,
    UserDecision,
)
from .review import record_user_decisions
from .serialization import job_from_dict, job_to_dict


class JobNotFoundError(KeyError):
    pass


class LocalJobStore:
    def __init__(self, root: Path | str = ".local/jobs") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def create(self, result: AnalysisResult) -> AnalysisJob:
        now = _now()
        job = AnalysisJob(
            id=str(uuid4()),
            result=result,
            status=JobStatus.AWAITING_REVIEW,
            created_at=now,
            updated_at=now,
        )
        self.save(job)
        return job

    def get(self, job_id: str) -> AnalysisJob:
        path = self._path(job_id)
        if not path.exists():
            raise JobNotFoundError(job_id)
        return job_from_dict(json.loads(path.read_text(encoding="utf-8")))

    def save(self, job: AnalysisJob) -> None:
        path = self._path(job.id)
        payload = json.dumps(job_to_dict(job), indent=2, sort_keys=True)
        path.write_text(payload + "\n", encoding="utf-8")

    def apply_decisions(self, job_id: str, decisions: list[UserDecision]) -> AnalysisJob:
        job = self.get(job_id)
        reviewed_result = record_user_decisions(job.result, decisions)
        updated = replace(
            job,
            result=reviewed_result,
            status=_job_status(reviewed_result),
            updated_at=_now(),
        )
        self.save(updated)
        return updated

    def add_output_artifact(self, job_id: str, artifact: OutputArtifact) -> AnalysisJob:
        job = self.get(job_id)
        updated = replace(
            job,
            status=JobStatus.OUTPUT_GENERATED,
            updated_at=_now(),
            output_artifacts=[*job.output_artifacts, artifact],
        )
        self.save(updated)
        return updated

    def _path(self, job_id: str) -> Path:
        if "/" in job_id or "\\" in job_id:
            raise JobNotFoundError(job_id)
        return self.root / f"{job_id}.json"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _job_status(result: AnalysisResult) -> JobStatus:
    if result.issues and all(issue.final_status != IssueStatus.OPEN for issue in result.issues):
        return JobStatus.REVIEWED
    return JobStatus.AWAITING_REVIEW
