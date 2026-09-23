import csv
from pathlib import Path

from backend.app.evaluation.outputs import (
    evaluate_final_csv,
    evaluate_negative_controls,
)
from backend.app.services.ingestion.contracts import OUTPUT_COLUMNS


def _record() -> dict[str, str]:
    return dict(
        zip(
            OUTPUT_COLUMNS,
            (
                "A-B",
                "2025-01-06",
                "1.23",
                "+20.0% vs this route's past average",
                "+21.0% vs similar-length routes this week",
                "Yes",
                "",
                "A grounded reason long enough for safe output review.",
            ),
            strict=True,
        )
    )


def test_correct_csv_passes_and_all_required_mutations_fail(tmp_path: Path) -> None:
    record = _record()
    path = tmp_path / "final_submission.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerow(record)
    assert all(
        item.status.value == "pass" for item in evaluate_final_csv(path, (record,))
    )
    control = evaluate_negative_controls(path, (record,), tmp_path / "mutations")
    assert control.status.value == "pass"


def test_changed_authoritative_number_is_detected(tmp_path: Path) -> None:
    record = _record()
    path = tmp_path / "final_submission.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerow(record)
    expected = {**record, "cost_per_tonne_km": "1.24"}
    checks = evaluate_final_csv(path, (expected,))
    assert (
        next(
            item
            for item in checks
            if item.check_id == "output.authoritative_reconciliation"
        ).status.value
        == "fail"
    )
