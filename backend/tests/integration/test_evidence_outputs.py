"""Evidence audit and reviewed CSV deterministic round-trip tests."""

import csv
from pathlib import Path

from backend.app.services.reporting import (
    build_evidence_reviewed_output,
    candidate_csv_sha256,
    evidence_audit_sha256,
    read_evidence_audit_jsonl,
    validate_evidence_audit_jsonl,
    validate_evidence_reviewed_csv,
    write_evidence_audit_jsonl,
    write_evidence_reviewed_csv,
)
from backend.tests.integration.test_evidence_pipeline_supplied_data import supplied_result


def test_evidence_artifacts_are_complete_valid_and_byte_stable(tmp_path: Path) -> None:
    bundle, _, detected, _, result = supplied_result()
    decisions = tuple(packet.decision for packet in result.packets)
    output = build_evidence_reviewed_output(detected, decisions, bundle.output_columns)
    audit_path = tmp_path / "audit.jsonl"
    csv_path = tmp_path / "reviewed.csv"
    write_evidence_audit_jsonl(result.audits, audit_path)
    write_evidence_reviewed_csv(output, csv_path)
    first_audit = audit_path.read_bytes()
    first_csv = csv_path.read_bytes()
    first_hashes = (evidence_audit_sha256(audit_path), candidate_csv_sha256(csv_path))

    assert read_evidence_audit_jsonl(audit_path) == result.audits
    validate_evidence_audit_jsonl(audit_path, result.audits)
    validate_evidence_reviewed_csv(csv_path, decisions)
    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 19
    assert sum(row["flagged"] == "No (justified)" for row in rows) == 3
    assert sum(row["flagged"] == "Yes" for row in rows) == 16
    assert sum(bool(row["matched_note_id"]) for row in rows) == 3

    write_evidence_audit_jsonl(result.audits, audit_path)
    write_evidence_reviewed_csv(output, csv_path)
    assert audit_path.read_bytes() == first_audit
    assert csv_path.read_bytes() == first_csv
    assert (evidence_audit_sha256(audit_path), candidate_csv_sha256(csv_path)) == first_hashes
