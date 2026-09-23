"""Independent final CSV contract evaluator and tampering controls."""

from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence

from ..domain.evaluation import EvaluationCheck, EvaluationDomain
from ..services.ingestion.contracts import OUTPUT_COLUMNS
from .contracts import check

_COST = re.compile(r"-?\d+\.\d{2}")
_PERCENT = re.compile(r"[+-]\d+\.\d% vs ")
_NOTE = re.compile(r"\bN\d+\b", re.IGNORECASE)


def evaluate_final_csv(
    destination: Path,
    authoritative_records: Sequence[Mapping[str, str]],
) -> list[EvaluationCheck]:
    domain = EvaluationDomain.OUTPUT_CONTRACT
    try:
        raw = Path(destination).read_text(encoding="utf-8")
        with Path(destination).open(encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle, strict=True))
    except (OSError, UnicodeError, csv.Error) as exc:
        return [
            check(
                "output.readable",
                domain,
                "CSV is valid UTF-8 and parseable",
                False,
                actual=type(exc).__name__,
            )
        ]
    header = tuple(rows[0]) if rows else ()
    body = rows[1:] if rows else []
    records = [
        dict(zip(OUTPUT_COLUMNS, row, strict=False)) for row in body if len(row) == 8
    ]
    expected = [dict(item) for item in authoritative_records]
    keys = [(row.get("route", ""), row.get("week_of", "")) for row in records]
    checks = [
        check("output.readable", domain, "CSV is valid UTF-8 and parseable", True),
        check(
            "output.header",
            domain,
            "Exact eight-column header and order",
            header == OUTPUT_COLUMNS,
            expected=list(OUTPUT_COLUMNS),
            actual=list(header),
        ),
        check(
            "output.header_once",
            domain,
            "Header appears exactly once",
            raw.count(",".join(OUTPUT_COLUMNS)) == 1,
            expected=1,
            actual=raw.count(",".join(OUTPUT_COLUMNS)),
        ),
        check(
            "output.row_count",
            domain,
            "Exactly one row per authoritative candidate",
            len(body) == len(expected),
            expected=len(expected),
            actual=len(body),
        ),
        check(
            "output.field_count",
            domain,
            "Every logical record has eight fields",
            all(len(row) == 8 for row in body),
            expected=8,
            actual=sorted({len(row) for row in body}),
        ),
        check(
            "output.unique_keys",
            domain,
            "Candidate keys are unique",
            len(keys) == len(set(keys)),
            expected=len(keys),
            actual=len(set(keys)),
        ),
        check(
            "output.sorted",
            domain,
            "Rows use deterministic route/week order",
            keys == sorted(keys),
            expected="sorted",
            actual="sorted" if keys == sorted(keys) else "unsorted",
        ),
        check(
            "output.dates",
            domain,
            "Dates use YYYY-MM-DD",
            all(_valid_date(row.get("week_of", "")) for row in records),
        ),
        check(
            "output.cost_format",
            domain,
            "Costs use two decimal places",
            all(_COST.fullmatch(row.get("cost_per_tonne_km", "")) for row in records),
        ),
        check(
            "output.percentage_format",
            domain,
            "Percentage displays use explicit sign and one decimal",
            all(
                _PERCENT.match(row.get("vs_own_history", ""))
                and (
                    _PERCENT.match(row.get("vs_similar_routes", ""))
                    or row.get("vs_similar_routes", "").startswith("Not available")
                )
                for row in records
            ),
        ),
        check(
            "output.flags",
            domain,
            "Flags use only allowed values",
            all(row.get("flagged") in {"Yes", "No (justified)"} for row in records),
        ),
        check(
            "output.note_mapping",
            domain,
            "Matched note appears only on justified rows",
            all(
                bool(row.get("matched_note_id"))
                == (row.get("flagged") == "No (justified)")
                for row in records
            ),
        ),
        check(
            "output.reasons",
            domain,
            "Reasons are non-empty",
            all(row.get("reason", "").strip() for row in records),
        ),
        check(
            "output.authoritative_reconciliation",
            domain,
            "CSV values reconcile with typed pipeline output",
            records == expected,
            expected=len(expected),
            actual=sum(left == right for left, right in zip(records, expected)),
        ),
        check(
            "output.reason_note_authority",
            domain,
            "Reason note IDs agree with matched/supporting authority",
            all(
                not _NOTE.findall(row.get("reason", ""))
                or row.get("matched_note_id")
                or row.get("flagged") == "Yes"
                for row in records
            ),
        ),
    ]
    return checks


def _valid_date(value: str) -> bool:
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d") == value
    except ValueError:
        return False


def evaluate_negative_controls(
    valid_path: Path,
    authoritative_records: Sequence[Mapping[str, str]],
    work_root: Path,
) -> EvaluationCheck:
    """Corrupt valid CSV copies and require the evaluator to reject each one."""
    with Path(valid_path).open(encoding="utf-8", newline="") as handle:
        source = list(csv.reader(handle))
    mutations: dict[str, list[list[str]] | str] = {}
    changed = [row[:] for row in source]
    changed[0][0] = "bad_route"
    mutations["bad_header"] = changed
    changed = [row[:] for row in source]
    changed[0] = ["index", *changed[0]]
    changed[1:] = [[str(i), *row] for i, row in enumerate(changed[1:])]
    mutations["index_column"] = changed
    changed = [row[:] for row in source]
    changed[1][2] = f"{float(changed[1][2]) + 0.01:.2f}"
    mutations["changed_cost"] = changed
    changed = [row[:] for row in source]
    changed[1][3] = "+99.9% vs this route's past average"
    mutations["changed_percentage"] = changed
    changed = [row[:] for row in source]
    changed[1][5] = "Yes" if changed[1][5] == "No (justified)" else "No (justified)"
    mutations["wrong_flag"] = changed
    changed = [row[:] for row in source]
    target = next(row for row in changed[1:] if row[5] == "Yes")
    target[6] = "N999"
    mutations["note_on_flagged"] = changed
    changed = [row[:] for row in source]
    changed[1][7] += " N999"
    mutations["unauthorized_note"] = changed
    changed = [row[:] for row in source]
    changed.append(changed[1][:])
    mutations["duplicate_row"] = changed
    changed = [row[:] for row in source[:-1]]
    mutations["missing_row"] = changed
    mutations["broken_quoting"] = (
        Path(valid_path).read_text(encoding="utf-8") + '"unterminated'
    )
    detected = 0
    work_root.mkdir(parents=True, exist_ok=True)
    for name, payload in mutations.items():
        path = work_root / f"{name}.csv"
        if isinstance(payload, str):
            path.write_text(payload, encoding="utf-8", newline="")
        else:
            with path.open("w", encoding="utf-8", newline="") as handle:
                csv.writer(handle, lineterminator="\n").writerows(payload)
        results = evaluate_final_csv(path, authoritative_records)
        detected += any(item.status.value == "fail" for item in results)
    return check(
        "output.negative_controls",
        EvaluationDomain.OUTPUT_CONTRACT,
        "All deliberate CSV corruptions are detected",
        detected == len(mutations),
        expected=len(mutations),
        actual=detected,
    )
