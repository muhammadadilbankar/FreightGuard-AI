"""Pure structural and value validation for canonical input frames."""

from collections.abc import Sequence
from datetime import datetime
import math
from pathlib import Path
import re

import pandas as pd

from ...schemas.ingestion import (
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
)
from .contracts import (
    ALLOWED_ROUTE_TYPES,
    CONTEXT_NOTE_DATASET,
    CONTEXT_NOTE_IDENTIFIER_COLUMN,
    CONTEXT_NOTE_TEXT_COLUMNS,
    OUTPUT_COLUMNS,
    OUTPUT_CONTRACT_DATASET,
    SHIPMENT_IDENTIFIER_COLUMN,
    SHIPMENT_NUMERIC_COLUMNS,
    SHIPMENT_TEXT_COLUMNS,
    SHIPMENTS_DATASET,
)

ISO_DATE_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


def issue_sort_key(issue: ValidationIssue) -> tuple[str, int, str, str]:
    """Return the stable sort key used for reports and CLI output."""
    return (
        issue.dataset,
        issue.row_number if issue.row_number is not None else 0,
        issue.column or "",
        issue.code,
    )


def sorted_issues(issues: Sequence[ValidationIssue]) -> tuple[ValidationIssue, ...]:
    """Sort issues deterministically without mutating the caller's collection."""
    return tuple(sorted(issues, key=issue_sort_key))


def make_report(
    dataset: str,
    source_path: Path,
    row_count: int,
    issues: Sequence[ValidationIssue],
    summary: str,
) -> ValidationReport:
    """Build a report with stable error and warning ordering."""
    ordered = sorted_issues(issues)
    errors = tuple(
        issue for issue in ordered if issue.severity == ValidationSeverity.ERROR
    )
    warnings = tuple(
        issue for issue in ordered if issue.severity == ValidationSeverity.WARNING
    )
    return ValidationReport(
        dataset=dataset,
        source_path=source_path,
        is_valid=not errors,
        row_count=row_count,
        errors=errors,
        warnings=warnings,
        summary=summary,
    )


def validate_header(
    actual: Sequence[str],
    expected: Sequence[str],
    dataset: str,
    *,
    require_order: bool = False,
) -> tuple[ValidationIssue, ...]:
    """Validate duplicate, missing, unexpected, and optionally ordered columns."""
    issues: list[ValidationIssue] = []
    duplicates = sorted({name for name in actual if actual.count(name) > 1})
    for name in duplicates:
        issues.append(
            _error(
                "duplicate_column",
                dataset,
                f"Column '{name}' appears more than once; keep one canonical column.",
                column=name,
                row_number=1,
            )
        )
    for name in expected:
        if name not in actual:
            issues.append(
                _error(
                    "missing_column",
                    dataset,
                    f"Required column '{name}' is missing.",
                    column=name,
                    row_number=1,
                )
            )
    for name in sorted(set(actual) - set(expected)):
        issues.append(
            _error(
                "unexpected_column",
                dataset,
                f"Unexpected column '{name}' must be removed.",
                column=name,
                row_number=1,
            )
        )
    if require_order and tuple(actual) != tuple(expected):
        issues.append(
            _error(
                "invalid_output_header",
                dataset,
                "Output header must contain exactly the required columns in order.",
                row_number=1,
            )
        )
    return sorted_issues(issues)


def validate_shipments(frame: pd.DataFrame) -> tuple[ValidationIssue, ...]:
    """Validate shipment values after the canonical header has passed."""
    issues: list[ValidationIssue] = []
    if frame.empty:
        issues.append(
            _error(
                "empty_dataset",
                SHIPMENTS_DATASET,
                "Shipment file has a header but no data rows.",
            )
        )
        return sorted_issues(issues)

    issues.extend(_validate_text(frame, SHIPMENT_TEXT_COLUMNS, SHIPMENTS_DATASET))
    issues.extend(
        _validate_identifier(
            frame, SHIPMENT_IDENTIFIER_COLUMN, SHIPMENTS_DATASET
        )
    )
    issues.extend(_validate_numeric(frame, SHIPMENT_NUMERIC_COLUMNS, SHIPMENTS_DATASET))
    issues.extend(_validate_date(frame, "shipment_date", SHIPMENTS_DATASET))

    for index, value in frame["route_type"].items():
        if _is_missing_or_blank(value):
            continue
        if not isinstance(value, str) or value.strip() not in ALLOWED_ROUTE_TYPES:
            issues.append(
                _error(
                    "invalid_route_type",
                    SHIPMENTS_DATASET,
                    "Route type must be exactly Short, Medium, or Long.",
                    column="route_type",
                    row_number=_csv_row(index),
                )
            )

    quantity = pd.to_numeric(frame["quantity_tonnes"], errors="coerce")
    distance = pd.to_numeric(frame["distance_km"], errors="coerce")
    products = quantity * distance
    finite_products = products.map(
        lambda value: math.isfinite(value) if not pd.isna(value) else False
    )
    for index in frame.index[(quantity > 0) & (distance > 0) & ~finite_products]:
        issues.append(
            _error(
                "non_finite_value",
                SHIPMENTS_DATASET,
                "Derived tonne_km must be finite.",
                column="tonne_km",
                row_number=_csv_row(index),
            )
        )
    return sorted_issues(issues)


def validate_context_notes(frame: pd.DataFrame) -> tuple[ValidationIssue, ...]:
    """Validate context-note values without interpreting their meaning."""
    issues: list[ValidationIssue] = []
    if frame.empty:
        issues.append(
            _error(
                "empty_dataset",
                CONTEXT_NOTE_DATASET,
                "Context-note file has a header but no data rows.",
            )
        )
        return sorted_issues(issues)
    issues.extend(
        _validate_text(frame, CONTEXT_NOTE_TEXT_COLUMNS, CONTEXT_NOTE_DATASET)
    )
    issues.extend(
        _validate_identifier(
            frame, CONTEXT_NOTE_IDENTIFIER_COLUMN, CONTEXT_NOTE_DATASET
        )
    )
    issues.extend(_validate_date(frame, "date", CONTEXT_NOTE_DATASET))
    return sorted_issues(issues)


def validate_output_header(actual: Sequence[str]) -> tuple[ValidationIssue, ...]:
    """Validate the authoritative eight-column submission header."""
    return validate_header(
        actual,
        OUTPUT_COLUMNS,
        OUTPUT_CONTRACT_DATASET,
        require_order=True,
    )


def _validate_text(
    frame: pd.DataFrame, columns: Sequence[str], dataset: str
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for column in columns:
        for index, value in frame[column].items():
            if pd.isna(value):
                issues.append(
                    _error(
                        "missing_value",
                        dataset,
                        f"Column '{column}' requires a value.",
                        column=column,
                        row_number=_csv_row(index),
                    )
                )
            elif not isinstance(value, str):
                issues.append(
                    _error(
                        "invalid_type",
                        dataset,
                        f"Column '{column}' must contain text.",
                        column=column,
                        row_number=_csv_row(index),
                    )
                )
            elif not value.strip():
                issues.append(
                    _error(
                        "blank_value",
                        dataset,
                        f"Column '{column}' cannot be blank.",
                        column=column,
                        row_number=_csv_row(index),
                    )
                )
    return issues


def _validate_identifier(
    frame: pd.DataFrame, column: str, dataset: str
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    normalized = frame[column].map(
        lambda value: value.strip() if isinstance(value, str) else None
    )
    duplicate_mask = normalized.notna() & normalized.ne("") & normalized.duplicated(False)
    for index in frame.index[duplicate_mask]:
        issues.append(
            _error(
                "duplicate_identifier",
                dataset,
                f"Column '{column}' must contain unique identifiers.",
                column=column,
                row_number=_csv_row(index),
            )
        )
    return issues


def _validate_numeric(
    frame: pd.DataFrame, columns: Sequence[str], dataset: str
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for column in columns:
        for index, value in frame[column].items():
            row_number = _csv_row(index)
            if pd.isna(value):
                issues.append(
                    _error(
                        "missing_value",
                        dataset,
                        f"Column '{column}' requires a numeric value.",
                        column=column,
                        row_number=row_number,
                    )
                )
                continue
            text = str(value).strip()
            if not text:
                issues.append(
                    _error(
                        "blank_value",
                        dataset,
                        f"Column '{column}' cannot be blank.",
                        column=column,
                        row_number=row_number,
                    )
                )
                continue
            try:
                number = float(text)
            except ValueError:
                issues.append(
                    _error(
                        "invalid_type",
                        dataset,
                        f"Column '{column}' must contain a number.",
                        column=column,
                        row_number=row_number,
                    )
                )
                continue
            if not math.isfinite(number):
                issues.append(
                    _error(
                        "non_finite_value",
                        dataset,
                        f"Column '{column}' must be finite.",
                        column=column,
                        row_number=row_number,
                    )
                )
            elif number <= 0:
                issues.append(
                    _error(
                        "non_positive_value",
                        dataset,
                        f"Column '{column}' must be greater than zero.",
                        column=column,
                        row_number=row_number,
                    )
                )
    return issues


def _validate_date(
    frame: pd.DataFrame, column: str, dataset: str
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for index, value in frame[column].items():
        row_number = _csv_row(index)
        if pd.isna(value):
            issues.append(
                _error(
                    "missing_value",
                    dataset,
                    f"Column '{column}' requires an ISO date.",
                    column=column,
                    row_number=row_number,
                )
            )
            continue
        text = str(value)
        if not text.strip():
            issues.append(
                _error(
                    "blank_value",
                    dataset,
                    f"Column '{column}' cannot be blank.",
                    column=column,
                    row_number=row_number,
                )
            )
            continue
        try:
            if not ISO_DATE_PATTERN.fullmatch(text):
                raise ValueError
            datetime.strptime(text, "%Y-%m-%d")
        except ValueError:
            issues.append(
                _error(
                    "invalid_date",
                    dataset,
                    f"Column '{column}' must use a valid YYYY-MM-DD date.",
                    column=column,
                    row_number=row_number,
                )
            )
    return issues


def _is_missing_or_blank(value: object) -> bool:
    return bool(pd.isna(value)) or (isinstance(value, str) and not value.strip())


def _csv_row(index: object) -> int:
    return int(index) + 2


def _error(
    code: str,
    dataset: str,
    message: str,
    *,
    column: str | None = None,
    row_number: int | None = None,
) -> ValidationIssue:
    return ValidationIssue(
        severity=ValidationSeverity.ERROR,
        code=code,
        dataset=dataset,
        message=message,
        column=column,
        row_number=row_number,
    )
