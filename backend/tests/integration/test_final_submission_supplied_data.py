"""Supplied-data Phase 2-through-8 template-mode regression."""

import csv

from backend.app.domain.explanations import ExplanationSettings, GenerationMode
from backend.app.services.explanations import ExplanationCache, generate_explanations
from backend.app.services.explanations.providers import TemplateExplanationProvider
from backend.app.services.reporting import (
    build_evidence_reviewed_output,
    build_explanation_audits,
    build_final_submission,
    read_explanation_audit_jsonl,
    validate_explanation_audit_jsonl,
    validate_final_submission_csv,
    write_explanation_audit_jsonl,
    write_final_submission,
)
from backend.tests.integration.test_evidence_pipeline_supplied_data import supplied_result


def test_template_mode_final_submission_preserves_phase7_authority(tmp_path) -> None:
    bundle, weekly, detected, notes, evidence = supplied_result()
    decisions = tuple(packet.decision for packet in evidence.packets)
    reviewed = build_evidence_reviewed_output(detected, decisions, bundle.output_columns)
    records = generate_explanations(
        evidence.packets,
        TemplateExplanationProvider(),
        ExplanationCache(tmp_path / "cache.jsonl"),
        ExplanationSettings(
            mode=GenerationMode.TEMPLATE,
            prompt_version="fg-explanation-v1",
        ),
    )
    final = build_final_submission(reviewed, records)
    fixed_columns = [column for column in reviewed.columns if column != "reason"]
    assert len(weekly) == 728
    assert int(detected["candidate_anomaly"].sum()) == 19
    assert len(notes) == len(decisions) - 9 == 10
    assert len(records) == 19
    assert final[fixed_columns].equals(reviewed[fixed_columns])
    assert all(record.provider_attempts == 0 for record in records)
    assert all(record.usage.total_tokens == 0 for record in records)
    assert all(record.estimated_cost_usd == 0 for record in records)

    audit_path = tmp_path / "audit.jsonl"
    csv_path = tmp_path / "final.csv"
    audits = build_explanation_audits(records)
    write_explanation_audit_jsonl(audits, audit_path)
    validate_explanation_audit_jsonl(audit_path, audits)
    write_final_submission(final, csv_path)
    validate_final_submission_csv(csv_path, reviewed, records)
    assert len(read_explanation_audit_jsonl(audit_path)) == 19
    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 19
    assert sum(row["flagged"] == "Yes" for row in rows) == 16
    assert sum(row["flagged"] == "No (justified)" for row in rows) == 3
    assert sum(bool(row["matched_note_id"]) for row in rows) == 3
    assert all(
        set(record.cited_note_ids).issubset(set(record.allowed_note_ids))
        for record in records
    )
