import csv

from backend.app.evaluation.outputs import evaluate_final_csv
from backend.app.services.ingestion.contracts import OUTPUT_COLUMNS


def test_bad_header_is_a_blocking_failure(tmp_path) -> None:
    row = [
        "A-B",
        "2025-01-06",
        "1.23",
        "+20.0% vs this route's past average",
        "+21.0% vs similar-length routes this week",
        "Yes",
        "",
        "A sufficiently descriptive grounded reason for review.",
    ]
    path = tmp_path / "bad.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows([["bad", *OUTPUT_COLUMNS[1:]], row])
    expected = [dict(zip(OUTPUT_COLUMNS, row, strict=True))]
    checks = evaluate_final_csv(path, expected)
    assert any(item.blocking and item.status.value == "fail" for item in checks)
