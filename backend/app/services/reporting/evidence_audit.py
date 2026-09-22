"""Deterministic evidence-gate audit JSONL persistence and validation."""

from collections.abc import Sequence
import hashlib
import json
import os
from pathlib import Path
import tempfile

from pydantic import ValidationError

from ...domain.evidence import CandidateEvidenceAudit
from .errors import EvidenceAuditError

EVIDENCE_AUDIT_FILENAME = "evidence_gate_audit.jsonl"


def write_evidence_audit_jsonl(
    audits: Sequence[CandidateEvidenceAudit], destination: Path
) -> Path:
    ordered = _validated_audits(audits)
    destination = Path(destination)
    temporary_path: Path | None = None
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", delete=False,
            dir=destination.parent, prefix=f".{destination.name}.", suffix=".tmp",
        ) as temporary:
            temporary_path = Path(temporary.name)
            for audit in ordered:
                temporary.write(
                    json.dumps(
                        audit.model_dump(mode="json"),
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    + "\n"
                )
        os.replace(temporary_path, destination)
    except (OSError, TypeError, ValueError) as exc:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
        raise EvidenceAuditError(f"Unable to write evidence audit: {exc}") from exc
    return destination


def read_evidence_audit_jsonl(path: Path) -> tuple[CandidateEvidenceAudit, ...]:
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise EvidenceAuditError(f"Unable to read evidence audit: {exc}") from exc
    if not raw or not raw.endswith(b"\n") or raw.endswith(b"\n\n"):
        raise EvidenceAuditError("Evidence audit must end with exactly one newline.")
    try:
        lines = raw.decode("utf-8").splitlines()
        parsed = tuple(
            CandidateEvidenceAudit.model_validate(json.loads(line)) for line in lines
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
        raise EvidenceAuditError("Evidence audit contains an invalid JSONL record.") from exc
    return _validated_audits(parsed)


def validate_evidence_audit_jsonl(
    path: Path, expected: Sequence[CandidateEvidenceAudit]
) -> tuple[CandidateEvidenceAudit, ...]:
    expected_ordered = _validated_audits(expected)
    actual = read_evidence_audit_jsonl(path)
    if actual != expected_ordered:
        raise EvidenceAuditError("Evidence audit does not match in-memory decisions.")
    return actual


def evidence_audit_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _validated_audits(
    audits: Sequence[CandidateEvidenceAudit],
) -> tuple[CandidateEvidenceAudit, ...]:
    if not audits:
        raise EvidenceAuditError("Evidence audit must contain candidates.")
    ordered = tuple(sorted(audits, key=lambda item: (item.route, item.week_of)))
    keys = [(item.route, item.week_of) for item in ordered]
    if len(set(keys)) != len(keys):
        raise EvidenceAuditError("Evidence audit candidate keys must be unique.")
    for audit in ordered:
        note_ids = tuple(item.note_id for item in audit.assessments)
        if note_ids != tuple(sorted(set(note_ids))):
            raise EvidenceAuditError("Evidence assessments must be unique and sorted.")
    return ordered
