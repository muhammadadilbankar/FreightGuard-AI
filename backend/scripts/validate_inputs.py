"""Validate all configured FreightGuard source files without writing output."""

from pathlib import Path

from backend.app.core.config import Settings, get_settings
from backend.app.core.logging import configure_logging
from backend.app.schemas.ingestion import ValidationIssue, ValidationReport
from backend.app.services.ingestion import (
    DataValidationError,
    InputFileError,
    load_input_bundle,
)


def main(settings: Settings | None = None) -> int:
    """Print deterministic validation results and return the documented exit code."""
    active_settings = settings or get_settings()
    configure_logging(active_settings.log_level)
    print("FreightGuard input validation")
    try:
        bundle = load_input_bundle(active_settings)
    except InputFileError as exc:
        _print_reports(exc.reports)
        _print_issues(exc.issues)
        print("Result: FAIL (input file error)")
        return 2
    except DataValidationError as exc:
        _print_reports(exc.reports)
        _print_issues(exc.issues)
        print("Result: FAIL (data validation error)")
        return 1

    _print_reports(bundle.reports)
    print("Result: PASS")
    return 0


def _print_reports(reports: tuple[ValidationReport, ...]) -> None:
    for report in reports:
        filename = Path(report.source_path).name
        if report.is_valid:
            detail = report.summary
            if report.warnings:
                detail += f", {len(report.warnings)} warning(s)"
            print(f"{filename}: valid ({detail})")
        else:
            print(f"{filename}: invalid ({len(report.errors)} error(s))")
        _print_issues(report.warnings)


def _print_issues(issues: tuple[ValidationIssue, ...]) -> None:
    for issue in issues:
        location = f" row {issue.row_number}" if issue.row_number else ""
        column = f" column {issue.column}" if issue.column else ""
        print(
            f"  {issue.severity.value}: {issue.dataset}{location}{column} "
            f"[{issue.code}] {issue.message}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
