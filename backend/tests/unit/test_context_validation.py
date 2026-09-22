"""Context-note validation and preservation tests."""

import csv
from pathlib import Path

import pytest

from backend.app.services.ingestion.contracts import CONTEXT_NOTE_COLUMNS
from backend.app.services.ingestion.errors import DataValidationError
from backend.app.services.ingestion.loaders import load_context_notes

FIXTURES = Path(__file__).parents[1] / "fixtures"


def _write_notes(path: Path, rows: list[dict[str, str]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CONTEXT_NOTE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _row(**overrides: str) -> dict[str, str]:
    row = {
        "note_id": "N-1",
        "date": "2024-01-01",
        "applies_to": "All Routes",
        "note": "Fuel costs rose, but service continued.",
    }
    row.update(overrides)
    return row


def test_valid_notes_preserve_scope_and_original_wording() -> None:
    frame, report = load_context_notes(FIXTURES / "context_notes_valid_minimal.csv")

    assert report.is_valid
    assert frame.loc[0, "applies_to"] == "All Routes"
    assert frame.loc[0, "note"] == "Fuel costs rose, but service continued."
    assert frame.loc[1, "note"] == "Carrier's surcharge remained in effect."


def test_duplicate_note_ids_fail_after_trimming(tmp_path: Path) -> None:
    path = _write_notes(
        tmp_path / "notes.csv", [_row(note_id="N-1"), _row(note_id=" N-1 ")]
    )

    with pytest.raises(DataValidationError) as caught:
        load_context_notes(path)

    assert [issue.code for issue in caught.value.issues].count(
        "duplicate_identifier"
    ) == 2


@pytest.mark.parametrize(
    ("overrides", "expected_code"),
    [
        ({"note": "   "}, "blank_value"),
        ({"date": "01/01/2024"}, "invalid_date"),
        ({"date": "2024-02-30"}, "invalid_date"),
    ],
)
def test_invalid_context_values_fail(
    tmp_path: Path, overrides: dict[str, str], expected_code: str
) -> None:
    path = _write_notes(tmp_path / "notes.csv", [_row(**overrides)])

    with pytest.raises(DataValidationError) as caught:
        load_context_notes(path)

    assert expected_code in [issue.code for issue in caught.value.issues]
