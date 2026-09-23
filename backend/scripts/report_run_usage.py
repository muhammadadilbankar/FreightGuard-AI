"""Aggregate one completed explanation audit into evaluator-facing usage evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from backend.app.core.config import PROJECT_ROOT

DEFAULT_AUDIT = PROJECT_ROOT / "backend/data/output/explanation_generation_audit.jsonl"
DEFAULT_CSV = PROJECT_ROOT / "backend/data/output/final_submission.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "backend/data/output/run_usage_report.json"


def build_usage_report(audit_path: Path, csv_path: Path) -> dict[str, Any]:
    records = [
        json.loads(line)
        for line in audit_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not records:
        raise ValueError("Explanation audit contains no records.")
    csv_hash = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    audit_hash = hashlib.sha256(audit_path.read_bytes()).hexdigest()
    modes = {record["explanation_source"] for record in records}
    providers = {record["provider"] for record in records if record["provider"]}
    models = {record["model"] for record in records if record["model"]}
    pricing_dates = {
        record["pricing_snapshot_date"]
        for record in records
        if record["pricing_snapshot_date"]
    }
    attempts = sum(int(record["provider_attempts"]) for record in records)
    failures = sum(
        bool(record["failure_codes"]) and int(record["provider_attempts"]) > 0
        for record in records
    )
    usage = [record["usage"] for record in records]
    estimated = sum(
        (Decimal(str(record["estimated_cost_usd"])) for record in records),
        Decimal(0),
    )
    if attempts == 0:
        estimated_total = "not_applicable"
    elif pricing_dates:
        estimated_total = f"{estimated:.6f}"
    else:
        estimated_total = "not_available"
    return {
        "schema_version": "1.0",
        "run_identifier": hashlib.sha256(
            f"{csv_hash}:{audit_hash}".encode("utf-8")
        ).hexdigest()[:16],
        "run_mode": "template" if modes == {"template"} else "mixed",
        "model_provider_identity": (
            "template (no hosted provider)"
            if not providers and attempts == 0
            else ", ".join(sorted(providers))
        ),
        "model_identity": None if not models else ", ".join(sorted(models)),
        "pricing_snapshot_date": (
            None if not pricing_dates else ", ".join(sorted(pricing_dates))
        ),
        "eligible_requests": sum(record["verdict"] != "unexplained" for record in records),
        "provider_calls": attempts,
        "input_tokens": sum(int(item["input_tokens"]) for item in usage),
        "cached_input_tokens": sum(int(item["cached_input_tokens"]) for item in usage),
        "output_tokens": sum(int(item["output_tokens"]) for item in usage),
        "reasoning_tokens": sum(int(item["reasoning_tokens"] or 0) for item in usage),
        "failed_or_refused_calls": failures,
        "cache_hits": sum(bool(record["cache_hit"]) for record in records),
        "cache_misses": sum(
            not record["cache_hit"] and int(record["provider_attempts"]) > 0
            for record in records
        ),
        "fallback_count": sum(record["explanation_source"] == "fallback" for record in records),
        "estimated_input_cost_usd": "not_available",
        "estimated_output_cost_usd": "not_available",
        "estimated_total_cost_usd": estimated_total,
        "currency": "USD",
        "cost_basis": (
            "No hosted calls occurred; model pricing was not required or configured."
            if attempts == 0
            else "Configured model rates and pricing snapshot date."
        ),
        "assistant_provider_calls_in_formal_evaluation": 0,
        "record_count": len(records),
        "final_csv_sha256": csv_hash,
        "explanation_audit_sha256": audit_hash,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = build_usage_report(args.audit.resolve(), args.csv.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Run usage report: {args.output}")
    print(f"Run identifier: {report['run_identifier']}")
    print(f"Provider calls: {report['provider_calls']}")
    print(f"Total tokens: {report['input_tokens'] + report['output_tokens']}")
    print(f"Estimated hosted cost: {report['estimated_total_cost_usd']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
