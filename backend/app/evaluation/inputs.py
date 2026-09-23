"""Independent supplied-input integrity evaluation."""

from __future__ import annotations

import csv
from pathlib import Path

from ..domain.evaluation import EvaluationCheck, EvaluationDomain, FileFingerprint
from ..services.ingestion.contracts import (
    CONTEXT_NOTES_FILENAME,
    OUTPUT_CONTRACT_FILENAME,
    CONTEXT_NOTE_COLUMNS,
    OUTPUT_COLUMNS,
    SHIPMENTS_FILENAME,
    SHIPMENT_COLUMNS,
)
from .contracts import check, fingerprint_file

APPROVED_HASHES = {
    SHIPMENTS_FILENAME: "1a2b4d66c4dc694111ba37b966486b5b0650df9ec8687402f3434117b140f4b6",
    CONTEXT_NOTES_FILENAME: "875c57a896ac3dfac0f712f8865b287bb5d2bd5423d26e798297b74dce87e6dc",
    OUTPUT_CONTRACT_FILENAME: "1ea902faca37bef6816e0878dc17bdb509a88f9ff9d4f101373e3af03994201f",
}


def fingerprint_inputs(input_dir: Path) -> tuple[FileFingerprint, ...]:
    return tuple(
        fingerprint_file(input_dir / name)
        for name in (
            SHIPMENTS_FILENAME,
            CONTEXT_NOTES_FILENAME,
            OUTPUT_CONTRACT_FILENAME,
        )
    )


def evaluate_input_fingerprints(
    before: tuple[FileFingerprint, ...],
    after: tuple[FileFingerprint, ...] | None = None,
) -> list[EvaluationCheck]:
    actual = {Path(item.relative_path).name: item.sha256 for item in before}
    checks = [
        check(
            f"input.hash.{name}",
            EvaluationDomain.INPUT_INTEGRITY,
            f"Approved SHA-256 for {name}",
            actual.get(name) == expected,
            expected=expected,
            actual=actual.get(name),
        )
        for name, expected in APPROVED_HASHES.items()
    ]
    if after is not None:
        checks.append(
            check(
                "input.immutable_after_evaluation",
                EvaluationDomain.INPUT_INTEGRITY,
                "Source inputs are byte-identical after evaluation",
                before == after,
                expected=[item.sha256 for item in before],
                actual=[item.sha256 for item in after],
            )
        )
    return checks


def evaluate_raw_headers(input_dir: Path) -> list[EvaluationCheck]:
    expected = {
        SHIPMENTS_FILENAME: SHIPMENT_COLUMNS,
        CONTEXT_NOTES_FILENAME: CONTEXT_NOTE_COLUMNS,
        OUTPUT_CONTRACT_FILENAME: OUTPUT_COLUMNS,
    }
    checks = []
    for name, header in expected.items():
        with (input_dir / name).open(encoding="utf-8", newline="") as handle:
            actual = tuple(next(csv.reader(handle)))
        checks.append(
            check(
                f"input.header.{name}",
                EvaluationDomain.INPUT_INTEGRITY,
                f"Exact strict header for {name}",
                actual == header,
                expected=list(header),
                actual=list(actual),
            )
        )
    return checks
