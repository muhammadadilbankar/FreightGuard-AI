"""Shipment structure and semantic validation tests."""

import csv
from pathlib import Path

import pytest

from backend.app.services.ingestion.contracts import SHIPMENT_COLUMNS
from backend.app.services.ingestion.errors import DataValidationError, InputFileError
from backend.app.services.ingestion.loaders import load_shipments

FIXTURES = Path(__file__).parents[1] / "fixtures"


def _valid_row(**overrides: str) -> dict[str, str]:
    row = {
        "shipment_id": "SHP-1",
        "origin": "Mumbai",
        "destination": "Pune",
        "route_type": "Short",
        "material": "Food",
        "quantity_tonnes": "12.25",
        "distance_km": "151.4",
        "freight_cost_inr": "5953.75",
        "shipment_date": "2024-01-01",
        "transporter": "Carrier",
    }
    row.update(overrides)
    return row


def _write_shipments(
    path: Path,
    rows: list[dict[str, str]],
    columns: tuple[str, ...] = SHIPMENT_COLUMNS,
) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path


def _error_codes(path: Path) -> list[str]:
    with pytest.raises(DataValidationError) as caught:
        load_shipments(path)
    return [issue.code for issue in caught.value.issues]


def test_valid_minimal_shipment_csv_loads() -> None:
    frame, report = load_shipments(FIXTURES / "shipments_valid_minimal.csv")

    assert report.is_valid
    assert len(frame) == 2
    assert frame["shipment_id"].tolist() == ["SHP-A", "SHP-B"]


def test_valid_reordered_columns_are_returned_canonically(tmp_path: Path) -> None:
    reversed_columns = tuple(reversed(SHIPMENT_COLUMNS))
    path = _write_shipments(
        tmp_path / "shipments.csv", [_valid_row()], reversed_columns
    )

    frame, _ = load_shipments(path)

    assert tuple(frame.columns[: len(SHIPMENT_COLUMNS)]) == SHIPMENT_COLUMNS


@pytest.mark.parametrize(
    ("columns", "expected_code"),
    [
        (tuple(name for name in SHIPMENT_COLUMNS if name != "material"), "missing_column"),
        (SHIPMENT_COLUMNS + ("extra",), "unexpected_column"),
    ],
)
def test_invalid_header_columns_fail(
    tmp_path: Path, columns: tuple[str, ...], expected_code: str
) -> None:
    path = _write_shipments(tmp_path / "shipments.csv", [_valid_row()], columns)

    assert expected_code in _error_codes(path)


def test_duplicate_header_fails(tmp_path: Path) -> None:
    path = tmp_path / "shipments.csv"
    header = ",".join(SHIPMENT_COLUMNS + ("origin",))
    path.write_text(f"{header}\n", encoding="utf-8")

    assert "duplicate_column" in _error_codes(path)


def test_empty_file_is_an_input_file_error(tmp_path: Path) -> None:
    path = tmp_path / "shipments.csv"
    path.touch()

    with pytest.raises(InputFileError) as caught:
        load_shipments(path)

    assert caught.value.issues[0].code == "empty_file"


def test_missing_file_is_an_input_file_error(tmp_path: Path) -> None:
    with pytest.raises(InputFileError) as caught:
        load_shipments(tmp_path / "missing.csv")

    assert caught.value.issues[0].code == "file_not_found"


def test_non_utf8_file_is_a_structured_file_error(tmp_path: Path) -> None:
    path = tmp_path / "shipments.csv"
    path.write_bytes(b"\xff\xfe\x00")

    with pytest.raises(InputFileError) as caught:
        load_shipments(path)

    assert caught.value.issues[0].code == "file_not_readable"


def test_malformed_csv_is_a_structured_validation_error(tmp_path: Path) -> None:
    path = tmp_path / "shipments.csv"
    path.write_text(
        ",".join(SHIPMENT_COLUMNS) + '\nSHP-1,"unterminated\n',
        encoding="utf-8",
    )

    with pytest.raises(DataValidationError) as caught:
        load_shipments(path)

    assert caught.value.issues[0].code == "malformed_csv"


def test_header_only_file_is_an_empty_dataset(tmp_path: Path) -> None:
    path = _write_shipments(tmp_path / "shipments.csv", [])

    assert _error_codes(path) == ["empty_dataset"]


@pytest.mark.parametrize("identifier", ["", "   "])
def test_blank_identifiers_fail(tmp_path: Path, identifier: str) -> None:
    path = _write_shipments(
        tmp_path / "shipments.csv", [_valid_row(shipment_id=identifier)]
    )

    assert "blank_value" in _error_codes(path)


def test_duplicate_identifiers_after_trimming_fail(tmp_path: Path) -> None:
    path = _write_shipments(
        tmp_path / "shipments.csv",
        [_valid_row(shipment_id="SHP-1"), _valid_row(shipment_id=" SHP-1 ")],
    )

    assert _error_codes(path).count("duplicate_identifier") == 2


@pytest.mark.parametrize("route_type", ["Short", "Medium", "Long"])
def test_canonical_route_types_pass(tmp_path: Path, route_type: str) -> None:
    path = _write_shipments(
        tmp_path / "shipments.csv", [_valid_row(route_type=route_type)]
    )

    assert load_shipments(path)[1].is_valid


@pytest.mark.parametrize("route_type", ["short", "LONG", "Unknown", "", "   "])
def test_noncanonical_route_types_fail(tmp_path: Path, route_type: str) -> None:
    path = _write_shipments(
        tmp_path / "shipments.csv", [_valid_row(route_type=route_type)]
    )

    codes = _error_codes(path)
    assert "invalid_route_type" in codes or "blank_value" in codes


@pytest.mark.parametrize("column", ["origin", "destination", "material", "transporter"])
def test_blank_required_text_fails(tmp_path: Path, column: str) -> None:
    path = _write_shipments(
        tmp_path / "shipments.csv", [_valid_row(**{column: "   "})]
    )

    assert "blank_value" in _error_codes(path)


@pytest.mark.parametrize(
    ("column", "value", "expected_code"),
    [
        (column, value, code)
        for column in ("quantity_tonnes", "distance_km", "freight_cost_inr")
        for value, code in (
            ("0", "non_positive_value"),
            ("-1", "non_positive_value"),
            ("word", "invalid_type"),
            ("NaN", "non_finite_value"),
            ("inf", "non_finite_value"),
            ("-inf", "non_finite_value"),
        )
    ],
)
def test_invalid_numeric_values_fail(
    tmp_path: Path, column: str, value: str, expected_code: str
) -> None:
    path = _write_shipments(
        tmp_path / "shipments.csv", [_valid_row(**{column: value})]
    )

    assert expected_code in _error_codes(path)


def test_numeric_values_are_not_rounded(tmp_path: Path) -> None:
    path = _write_shipments(
        tmp_path / "shipments.csv",
        [_valid_row(quantity_tonnes="1.23456789", distance_km="9.87654321")],
    )

    frame, _ = load_shipments(path)

    assert frame.loc[0, "quantity_tonnes"] == 1.23456789
    assert frame.loc[0, "tonne_km"] == 1.23456789 * 9.87654321


@pytest.mark.parametrize(
    ("date_value", "valid"),
    [
        ("2024-02-29", True),
        ("2023-02-29", False),
        ("31/01/2024", False),
        ("2024-01-01T12:00:00", False),
    ],
)
def test_dates_are_strict_iso(tmp_path: Path, date_value: str, valid: bool) -> None:
    path = _write_shipments(
        tmp_path / "shipments.csv", [_valid_row(shipment_date=date_value)]
    )

    if valid:
        assert load_shipments(path)[1].is_valid
    else:
        assert "invalid_date" in _error_codes(path)


def test_multiple_issues_are_collected_and_sorted_without_raw_rows(tmp_path: Path) -> None:
    path = _write_shipments(
        tmp_path / "shipments.csv",
        [_valid_row(origin="", quantity_tonnes="secret-invalid-value")],
    )

    with pytest.raises(DataValidationError) as caught:
        load_shipments(path)

    issues = caught.value.issues
    keys = [
        (issue.dataset, issue.row_number or 0, issue.column or "", issue.code)
        for issue in issues
    ]
    assert keys == sorted(keys)
    assert {issue.code for issue in issues} >= {"blank_value", "invalid_type"}
    assert "secret-invalid-value" not in str(caught.value)
