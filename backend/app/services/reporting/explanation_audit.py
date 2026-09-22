"""Deterministic Phase 8 audit JSONL persistence and validation."""

from collections.abc import Sequence
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import tempfile

from pydantic import ValidationError

from ...domain.explanations import ExplanationAuditRecord, FinalExplanationRecord
from .errors import ExplanationAuditError

EXPLANATION_AUDIT_FILENAME = "explanation_generation_audit.jsonl"


def build_explanation_audits(
    records: Sequence[FinalExplanationRecord],
) -> tuple[ExplanationAuditRecord, ...]:
    return tuple(
        ExplanationAuditRecord(
            route=record.route,
            week_of=record.week_of,
            verdict=record.verdict,
            selected_note_id=record.selected_note_id,
            supporting_note_ids=record.supporting_note_ids,
            allowed_note_ids=record.allowed_note_ids,
            explanation_source=record.explanation_source,
            provider=record.provider,
            model=record.model,
            prompt_version=record.prompt_version,
            cache_key=record.cache_key,
            cache_hit=record.cache_hit,
            provider_attempts=record.provider_attempts,
            validation_status=record.validation_status,
            failure_codes=record.failure_codes,
            cited_note_ids=record.cited_note_ids,
            usage=record.usage,
            estimated_cost_usd=record.estimated_cost_usd,
            pricing_snapshot_date=record.pricing_snapshot_date,
            provider_request_id=record.provider_request_id,
            latency_ms=record.latency_ms,
            reason_sha256=hashlib.sha256(record.reason.encode("utf-8")).hexdigest(),
        )
        for record in sorted(records, key=lambda item: (item.route, item.week_of))
    )


def write_explanation_audit_jsonl(
    audits: Sequence[ExplanationAuditRecord], destination: Path
) -> Path:
    ordered = _validate_audits(audits)
    temporary_path: Path | None = None
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", delete=False,
            dir=destination.parent, prefix=f".{destination.name}.", suffix=".tmp",
        ) as temporary:
            temporary_path = Path(temporary.name)
            for audit in ordered:
                payload = audit.model_dump(mode="json")
                if isinstance(audit.estimated_cost_usd, Decimal):
                    payload["estimated_cost_usd"] = str(audit.estimated_cost_usd)
                temporary.write(
                    json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
                )
        os.replace(temporary_path, destination)
    except (OSError, TypeError, ValueError) as exc:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
        raise ExplanationAuditError("Unable to write explanation audit.") from exc
    return destination


def read_explanation_audit_jsonl(path: Path) -> tuple[ExplanationAuditRecord, ...]:
    try:
        raw = Path(path).read_bytes()
        if not raw or not raw.endswith(b"\n") or raw.endswith(b"\n\n"):
            raise ExplanationAuditError("Explanation audit trailing newline is invalid.")
        records = tuple(
            ExplanationAuditRecord.model_validate(json.loads(line))
            for line in raw.decode("utf-8").splitlines()
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
        raise ExplanationAuditError("Explanation audit contains an invalid record.") from exc
    return _validate_audits(records)


def validate_explanation_audit_jsonl(
    path: Path, expected: Sequence[ExplanationAuditRecord]
) -> tuple[ExplanationAuditRecord, ...]:
    actual = read_explanation_audit_jsonl(path)
    if actual != _validate_audits(expected):
        raise ExplanationAuditError("Explanation audit round-trip mismatch.")
    return actual


def explanation_audit_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _validate_audits(
    audits: Sequence[ExplanationAuditRecord],
) -> tuple[ExplanationAuditRecord, ...]:
    if not audits:
        raise ExplanationAuditError("Explanation audit must not be empty.")
    ordered = tuple(sorted(audits, key=lambda item: (item.route, item.week_of)))
    keys = [(item.route, item.week_of) for item in ordered]
    if len(keys) != len(set(keys)):
        raise ExplanationAuditError("Explanation audit keys must be unique.")
    return ordered
