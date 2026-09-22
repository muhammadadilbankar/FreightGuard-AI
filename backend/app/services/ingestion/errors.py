"""Structured exceptions exposed by the ingestion service."""

from collections.abc import Iterable

from ...schemas.ingestion import ValidationIssue, ValidationReport


class IngestionError(Exception):
    """Base class for expected input ingestion failures."""

    def __init__(
        self,
        issues: Iterable[ValidationIssue],
        reports: Iterable[ValidationReport] = (),
    ) -> None:
        self.issues = tuple(issues)
        self.reports = tuple(reports)
        message = "; ".join(issue.message for issue in self.issues)
        super().__init__(message or "Input ingestion failed.")


class InputFileError(IngestionError):
    """A required input is missing, empty, unreadable, or undecodable."""


class DataValidationError(IngestionError):
    """One or more source values violate a declared data contract."""
