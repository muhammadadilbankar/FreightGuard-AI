"""File access and orchestration for validated FreightGuard inputs."""

import csv
import logging
from pathlib import Path

import pandas as pd
from pandas.errors import ParserError

from ...core.config import Settings
from ...core.logging import LOGGER_NAME
from ...schemas.ingestion import ValidationIssue, ValidationReport, ValidationSeverity
from .contracts import (
    CONTEXT_NOTE_COLUMNS,
    CONTEXT_NOTE_DATASET,
    CONTEXT_NOTES_FILENAME,
    InputBundle,
    OUTPUT_COLUMNS,
    OUTPUT_CONTRACT_DATASET,
    OUTPUT_CONTRACT_FILENAME,
    SHIPMENT_COLUMNS,
    SHIPMENTS_DATASET,
    SHIPMENTS_FILENAME,
)
from .errors import DataValidationError, InputFileError
from .normalization import normalize_context_notes, normalize_shipments
from .validation import (
    make_report,
    sorted_issues,
    validate_context_notes,
    validate_header,
    validate_output_header,
    validate_shipments,
)

logger = logging.getLogger(f"{LOGGER_NAME}.ingestion")


def load_shipments(path: Path) -> tuple[pd.DataFrame, ValidationReport]:
    """Load, strictly validate, and normalize a shipment CSV."""
    resolved = path.resolve()
    logger.info("Validating dataset=%s file=%s", SHIPMENTS_DATASET, resolved.name)
    header = _read_header(resolved, SHIPMENTS_DATASET)
    header_issues = validate_header(header, SHIPMENT_COLUMNS, SHIPMENTS_DATASET)
    if header_issues:
        report = make_report(
            SHIPMENTS_DATASET, resolved, 0, header_issues, "invalid header"
        )
        raise DataValidationError(report.errors, (report,))
    frame = _read_frame(resolved, SHIPMENTS_DATASET)
    issues = validate_shipments(frame)
    report = make_report(
        SHIPMENTS_DATASET,
        resolved,
        len(frame),
        issues,
        f"{len(frame)} rows, {len(SHIPMENT_COLUMNS)} source columns",
    )
    if not report.is_valid:
        raise DataValidationError(report.errors, (report,))
    normalized = normalize_shipments(frame)
    logger.info(
        "Validated dataset=%s rows=%d columns=%d warnings=%d errors=0",
        SHIPMENTS_DATASET,
        len(frame),
        len(frame.columns),
        len(report.warnings),
    )
    return normalized, report


def load_context_notes(path: Path) -> tuple[pd.DataFrame, ValidationReport]:
    """Load and validate context notes without semantic interpretation."""
    resolved = path.resolve()
    logger.info("Validating dataset=%s file=%s", CONTEXT_NOTE_DATASET, resolved.name)
    header = _read_header(resolved, CONTEXT_NOTE_DATASET)
    header_issues = validate_header(
        header, CONTEXT_NOTE_COLUMNS, CONTEXT_NOTE_DATASET
    )
    if header_issues:
        report = make_report(
            CONTEXT_NOTE_DATASET, resolved, 0, header_issues, "invalid header"
        )
        raise DataValidationError(report.errors, (report,))
    frame = _read_frame(resolved, CONTEXT_NOTE_DATASET)
    issues = validate_context_notes(frame)
    report = make_report(
        CONTEXT_NOTE_DATASET,
        resolved,
        len(frame),
        issues,
        f"{len(frame)} rows, {len(CONTEXT_NOTE_COLUMNS)} source columns",
    )
    if not report.is_valid:
        raise DataValidationError(report.errors, (report,))
    normalized = normalize_context_notes(frame)
    logger.info(
        "Validated dataset=%s rows=%d columns=%d warnings=%d errors=0",
        CONTEXT_NOTE_DATASET,
        len(frame),
        len(frame.columns),
        len(report.warnings),
    )
    return normalized, report


def load_output_contract(path: Path) -> tuple[tuple[str, ...], ValidationReport]:
    """Validate the authoritative first record and diagnose malformed body rows."""
    resolved = path.resolve()
    logger.info("Validating dataset=%s file=%s", OUTPUT_CONTRACT_DATASET, resolved.name)
    _ensure_readable_nonempty(resolved, OUTPUT_CONTRACT_DATASET)
    issues: list[ValidationIssue] = []
    body_rows = 0
    try:
        with resolved.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle, strict=True)
            header = next(reader, None)
            if header is None:
                raise _empty_file_error(resolved, OUTPUT_CONTRACT_DATASET)
            issues.extend(validate_output_header(header))
            try:
                for row in reader:
                    body_rows += 1
                    if len(row) != len(OUTPUT_COLUMNS):
                        issues.append(
                            ValidationIssue(
                                severity=ValidationSeverity.WARNING,
                                code="malformed_sample_row",
                                dataset=OUTPUT_CONTRACT_DATASET,
                                message=(
                                    "Illustrative body row has an inconsistent field "
                                    "count; the header remains authoritative."
                                ),
                                row_number=reader.line_num,
                            )
                        )
            except csv.Error:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        code="malformed_sample_row",
                        dataset=OUTPUT_CONTRACT_DATASET,
                        message=(
                            "Illustrative body rows contain malformed CSV; the "
                            "header remains authoritative."
                        ),
                        row_number=reader.line_num,
                    )
                )
    except UnicodeDecodeError as exc:
        raise _file_error(
            resolved,
            OUTPUT_CONTRACT_DATASET,
            "file_not_readable",
            "Input file must be valid UTF-8 text.",
        ) from exc
    except OSError as exc:
        raise _file_error(
            resolved,
            OUTPUT_CONTRACT_DATASET,
            "file_not_readable",
            "Input file could not be read.",
        ) from exc

    report = make_report(
        OUTPUT_CONTRACT_DATASET,
        resolved,
        body_rows,
        issues,
        f"{len(header)} header columns, {body_rows} illustrative rows",
    )
    if not report.is_valid:
        raise DataValidationError(report.errors, (report,))
    logger.info(
        "Validated dataset=%s header_columns=%d warnings=%d errors=0",
        OUTPUT_CONTRACT_DATASET,
        len(header),
        len(report.warnings),
    )
    return tuple(header), report


def load_input_bundle(settings: Settings) -> InputBundle:
    """Load every configured input and aggregate all blocking validation issues."""
    loaders = (
        (
            "shipments",
            load_shipments,
            settings.input_data_dir / SHIPMENTS_FILENAME,
        ),
        (
            "context_notes",
            load_context_notes,
            settings.input_data_dir / CONTEXT_NOTES_FILENAME,
        ),
        (
            "output_columns",
            load_output_contract,
            settings.input_data_dir / OUTPUT_CONTRACT_FILENAME,
        ),
    )
    results: dict[str, object] = {}
    reports: list[ValidationReport] = []
    file_issues: list[ValidationIssue] = []
    data_issues: list[ValidationIssue] = []

    for result_name, loader, path in loaders:
        try:
            result, report = loader(path)
            results[result_name] = result
            reports.append(report)
        except InputFileError as exc:
            file_issues.extend(exc.issues)
            reports.extend(exc.reports)
        except DataValidationError as exc:
            data_issues.extend(exc.issues)
            reports.extend(exc.reports)

    all_issues = sorted_issues(file_issues + data_issues)
    ordered_reports = tuple(sorted(reports, key=lambda report: report.dataset))
    if file_issues:
        raise InputFileError(all_issues, ordered_reports)
    if data_issues:
        raise DataValidationError(all_issues, ordered_reports)

    return InputBundle(
        shipments=results["shipments"],  # type: ignore[arg-type]
        context_notes=results["context_notes"],  # type: ignore[arg-type]
        output_columns=results["output_columns"],  # type: ignore[arg-type]
        reports=ordered_reports,
    )


def _read_header(path: Path, dataset: str) -> tuple[str, ...]:
    _ensure_readable_nonempty(path, dataset)
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            header = next(csv.reader(handle, strict=True), None)
    except (UnicodeDecodeError, csv.Error) as exc:
        raise _file_error(
            path,
            dataset,
            "file_not_readable",
            "Input file must be valid UTF-8 CSV.",
        ) from exc
    except OSError as exc:
        raise _file_error(
            path, dataset, "file_not_readable", "Input file could not be read."
        ) from exc
    if header is None or not any(field.strip() for field in header):
        raise _empty_file_error(path, dataset)
    return tuple(header)


def _read_frame(path: Path, dataset: str) -> pd.DataFrame:
    try:
        return pd.read_csv(
            path,
            dtype=str,
            encoding="utf-8",
            keep_default_na=False,
            na_filter=False,
            skip_blank_lines=False,
        )
    except (ParserError, UnicodeDecodeError) as exc:
        issue = ValidationIssue(
            severity=ValidationSeverity.ERROR,
            code="malformed_csv",
            dataset=dataset,
            message="Input contains malformed CSV records; correct the source file.",
        )
        report = make_report(dataset, path, 0, (issue,), "malformed CSV")
        raise DataValidationError(report.errors, (report,)) from exc
    except OSError as exc:
        raise _file_error(
            path, dataset, "file_not_readable", "Input file could not be read."
        ) from exc


def _ensure_readable_nonempty(path: Path, dataset: str) -> None:
    if not path.is_file():
        raise _file_error(
            path,
            dataset,
            "file_not_found",
            f"Required input file '{path.name}' was not found.",
        )
    try:
        if path.stat().st_size == 0:
            raise _empty_file_error(path, dataset)
    except OSError as exc:
        raise _file_error(
            path, dataset, "file_not_readable", "Input file could not be inspected."
        ) from exc


def _empty_file_error(path: Path, dataset: str) -> InputFileError:
    return _file_error(
        path,
        dataset,
        "empty_file",
        f"Required input file '{path.name}' is empty.",
    )


def _file_error(
    path: Path, dataset: str, code: str, message: str
) -> InputFileError:
    issue = ValidationIssue(
        severity=ValidationSeverity.ERROR,
        code=code,
        dataset=dataset,
        message=message,
    )
    report = make_report(dataset, path, 0, (issue,), "input file error")
    return InputFileError((issue,), (report,))
