"""Authoritative sample-output header tests."""

from pathlib import Path

import pytest

from backend.app.services.ingestion.contracts import OUTPUT_COLUMNS
from backend.app.services.ingestion.errors import DataValidationError
from backend.app.services.ingestion.loaders import load_output_contract

FIXTURES = Path(__file__).parents[1] / "fixtures"


def _codes(path: Path) -> list[str]:
    with pytest.raises(DataValidationError) as caught:
        load_output_contract(path)
    return [issue.code for issue in caught.value.issues]


def test_exact_output_header_passes() -> None:
    columns, report = load_output_contract(FIXTURES / "output_contract_valid.csv")

    assert columns == OUTPUT_COLUMNS
    assert report.is_valid


@pytest.mark.parametrize(
    "header",
    [
        OUTPUT_COLUMNS[1:] + OUTPUT_COLUMNS[:1],
        OUTPUT_COLUMNS[:-1],
        OUTPUT_COLUMNS + ("extra",),
        OUTPUT_COLUMNS[:-1] + ("route",),
    ],
)
def test_invalid_output_headers_fail(tmp_path: Path, header: tuple[str, ...]) -> None:
    path = tmp_path / "output.csv"
    path.write_text(",".join(header) + "\n", encoding="utf-8")

    assert "invalid_output_header" in _codes(path)


def test_unquoted_body_commas_are_a_nonblocking_warning(tmp_path: Path) -> None:
    path = tmp_path / "output.csv"
    path.write_text(
        ",".join(OUTPUT_COLUMNS)
        + "\nA-B,2024-01-01,1,2,3,Yes,,Reason with, an unquoted comma\n",
        encoding="utf-8",
    )

    columns, report = load_output_contract(path)

    assert columns == OUTPUT_COLUMNS
    assert report.is_valid
    assert [warning.code for warning in report.warnings] == ["malformed_sample_row"]


def test_duplicate_output_column_has_a_specific_issue(tmp_path: Path) -> None:
    path = tmp_path / "output.csv"
    path.write_text(
        ",".join(OUTPUT_COLUMNS[:-1] + ("route",)) + "\n", encoding="utf-8"
    )

    assert "duplicate_column" in _codes(path)
