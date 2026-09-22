"""Typed validation outcomes for the ingestion boundary."""

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class ValidationSeverity(str, Enum):
    """Severity levels emitted by deterministic input validation."""

    ERROR = "error"
    WARNING = "warning"


class ValidationIssue(BaseModel):
    """A stable, machine-testable input validation finding."""

    model_config = ConfigDict(frozen=True)

    severity: ValidationSeverity
    code: str
    dataset: str
    message: str
    column: str | None = None
    row_number: int | None = Field(default=None, ge=1)


class ValidationReport(BaseModel):
    """Deterministic validation result for one source dataset."""

    model_config = ConfigDict(frozen=True)

    dataset: str
    source_path: Path
    is_valid: bool
    row_count: int
    errors: tuple[ValidationIssue, ...] = ()
    warnings: tuple[ValidationIssue, ...] = ()
    summary: str
