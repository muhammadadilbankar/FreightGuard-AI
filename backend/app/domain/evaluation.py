"""Immutable Phase 9 evaluation and reproducibility contracts."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class CheckStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"


class EvaluationDomain(str, Enum):
    INPUT_INTEGRITY = "input_integrity"
    WEEKLY_ANALYTICS = "weekly_analytics"
    BASELINE_CORRECTNESS = "baseline_correctness"
    CANDIDATE_DETECTION = "candidate_detection"
    CONTEXT_COMPILATION = "context_compilation"
    RETRIEVAL_QUALITY = "retrieval_quality"
    EVIDENCE_GATE = "evidence_gate"
    EXPLANATION_GROUNDING = "explanation_grounding"
    OPERATIONAL_ROOT_CAUSE = "operational_root_cause"
    OUTPUT_CONTRACT = "output_contract"
    METAMORPHIC_INVARIANTS = "metamorphic_invariants"
    REPRODUCIBILITY = "reproducibility"


class NumericTolerance(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    relative: float
    absolute: float


class EvaluationCheck(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    check_id: str
    domain: EvaluationDomain
    description: str
    blocking: bool = True
    status: CheckStatus
    expected: Any | None = None
    actual: Any | None = None
    tolerance: NumericTolerance | None = None
    details: tuple[str, ...] = ()


class EvaluationMetric(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    metric_id: str
    domain: EvaluationDomain
    value: float | int
    unit: str
    target: float | int | None = None
    target_relation: Literal["eq", "gte", "lte", "informational"]
    blocking: bool = False
    numerator: int | None = None
    denominator: int | None = None

    def meets_target(self) -> bool:
        if self.target_relation == "informational":
            return True
        if self.target is None:
            return False
        if self.target_relation == "eq":
            return self.value == self.target
        if self.target_relation == "gte":
            return self.value >= self.target
        return self.value <= self.target


class FileFingerprint(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    relative_path: str
    sha256: str
    byte_size: int


class ArtifactFingerprint(FileFingerprint):
    run_id: str | None = None


class EnvironmentFingerprint(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    python: str
    implementation: str
    operating_system: str
    architecture: str
    timezone: str
    locale: str
    dependency_versions: dict[str, str]
    dependency_lock_sha256: str | None
    embedding_model: str
    embedding_revision: str
    explanation_mode: str
    prompt_version: str
    provider_identity: str
    git_commit: str | None
    dirty_worktree: bool


class ReproducibilityRun(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    run_id: str
    exit_code: int
    duration_ms: int
    timed_out: bool = False
    artifacts: tuple[ArtifactFingerprint, ...]
    final_csv_rows: int | None = None
    final_csv_columns: int | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""


class ArtifactComparison(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    artifact_name: str
    identical: bool
    hashes: tuple[str, ...]
    byte_sizes: tuple[int, ...]
    first_difference: str | None = None


class ReproducibilityResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    formal: bool
    run_count: int
    runs: tuple[ReproducibilityRun, ...]
    comparisons: tuple[ArtifactComparison, ...]
    overall_reproducible: bool


class EvaluationReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_version: Literal["1.0", "1.1"] = "1.1"
    overall_status: Literal["pass", "fail"]
    evaluation_mode: str
    run_count: int
    environment: EnvironmentFingerprint
    inputs: tuple[FileFingerprint, ...]
    configuration_fingerprint: str
    checks: tuple[EvaluationCheck, ...]
    metrics: tuple[EvaluationMetric, ...]
    reproducibility: ReproducibilityResult
    artifacts: tuple[ArtifactFingerprint, ...]

    @field_validator("checks")
    @classmethod
    def validate_checks(
        cls, value: tuple[EvaluationCheck, ...]
    ) -> tuple[EvaluationCheck, ...]:
        if len({item.check_id for item in value}) != len(value):
            raise ValueError("Evaluation check IDs must be unique.")
        if value != tuple(
            sorted(value, key=lambda item: (item.domain.value, item.check_id))
        ):
            raise ValueError("Evaluation checks must be sorted by domain and ID.")
        return value

    @field_validator("metrics")
    @classmethod
    def validate_metrics(
        cls, value: tuple[EvaluationMetric, ...]
    ) -> tuple[EvaluationMetric, ...]:
        if len({item.metric_id for item in value}) != len(value):
            raise ValueError("Evaluation metric IDs must be unique.")
        if value != tuple(
            sorted(value, key=lambda item: (item.domain.value, item.metric_id))
        ):
            raise ValueError("Evaluation metrics must be sorted by domain and ID.")
        return value

    @model_validator(mode="after")
    def status_is_derived(self) -> Self:
        failed_check = any(
            item.blocking and item.status != CheckStatus.PASS for item in self.checks
        )
        failed_metric = any(
            item.blocking and not item.meets_target() for item in self.metrics
        )
        derived = (
            "fail"
            if failed_check
            or failed_metric
            or not self.reproducibility.overall_reproducible
            else "pass"
        )
        if self.overall_status != derived:
            raise ValueError(f"overall_status must be derived as {derived}")
        return self


def derive_status(
    checks: tuple[EvaluationCheck, ...],
    metrics: tuple[EvaluationMetric, ...],
    reproducibility: ReproducibilityResult,
) -> Literal["pass", "fail"]:
    failed = any(item.blocking and item.status != CheckStatus.PASS for item in checks)
    failed = failed or any(
        item.blocking and not item.meets_target() for item in metrics
    )
    failed = failed or not reproducibility.overall_reproducible
    return "fail" if failed else "pass"
