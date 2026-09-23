from __future__ import annotations

import json
from pathlib import Path

from backend.scripts.report_run_usage import build_usage_report


def test_template_usage_report_is_honest_and_deterministic(tmp_path: Path) -> None:
    audit = tmp_path / "audit.jsonl"
    csv = tmp_path / "final.csv"
    record = {
        "verdict": "justified",
        "explanation_source": "template",
        "provider": None,
        "model": None,
        "pricing_snapshot_date": None,
        "provider_attempts": 0,
        "failure_codes": [],
        "cache_hit": False,
        "estimated_cost_usd": "0",
        "usage": {
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "output_tokens": 0,
            "reasoning_tokens": None,
        },
    }
    audit.write_text(json.dumps(record) + "\n", encoding="utf-8")
    csv.write_text("route,week_of\nR1,2024-01-01\n", encoding="utf-8")

    first = build_usage_report(audit, csv)
    second = build_usage_report(audit, csv)

    assert first == second
    assert first["run_mode"] == "template"
    assert first["provider_calls"] == 0
    assert first["input_tokens"] == 0
    assert first["estimated_total_cost_usd"] == "not_applicable"
    assert first["pricing_snapshot_date"] is None
