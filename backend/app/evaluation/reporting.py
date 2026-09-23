"""Deterministic JSON, Markdown, and manifest rendering."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from ..domain.evaluation import EvaluationReport


def write_reports(
    report: EvaluationReport, output_root: Path
) -> tuple[Path, Path, Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    json_path = output_root / "evaluation_report.json"
    markdown_path = output_root / "evaluation_report.md"
    manifest_path = output_root / "reproducibility_manifest.json"
    payload = report.model_dump(mode="json")
    _atomic_write(
        json_path,
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
    )
    # Independent typed read-back catches serialization/schema drift.
    EvaluationReport.model_validate_json(json_path.read_text(encoding="utf-8"))
    _atomic_write(markdown_path, render_markdown(report))
    manifest = {
        "schema_version": "1.0",
        "formal_run_count": report.reproducibility.run_count,
        "evaluation_mode": report.evaluation_mode,
        "configuration_fingerprint": report.configuration_fingerprint,
        "input_fingerprints": [item.model_dump(mode="json") for item in report.inputs],
        "environment_fingerprint": report.environment.model_dump(mode="json"),
        "runs": [item.model_dump(mode="json") for item in report.reproducibility.runs],
        "canonical_artifact_comparisons": [
            item.model_dump(mode="json") for item in report.reproducibility.comparisons
        ],
        "overall_reproducible": report.reproducibility.overall_reproducible,
    }
    _atomic_write(
        manifest_path,
        json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
    )
    json.loads(manifest_path.read_text(encoding="utf-8"))
    return json_path, markdown_path, manifest_path


def render_markdown(report: EvaluationReport) -> str:
    failures = [
        item for item in report.checks if item.blocking and item.status.value != "pass"
    ]
    domain_status = {}
    for domain in sorted(
        {item.domain for item in report.checks}, key=lambda item: item.value
    ):
        domain_status[domain.value] = (
            "PASS"
            if all(
                item.status.value == "pass"
                for item in report.checks
                if item.domain == domain and item.blocking
            )
            else "FAIL"
        )
    lines = [
        "# FreightGuard evaluation report",
        "",
        "## Executive result",
        "",
        f"**Overall: {report.overall_status.upper()}**",
        "",
        f"Mode: `{report.evaluation_mode}`  ",
        f"Formal runs: {report.run_count}  ",
        f"Configuration fingerprint: `{report.configuration_fingerprint}`",
        "",
        "| Domain | Status |",
        "|---|---|",
        *[f"| {name} | {status} |" for name, status in domain_status.items()],
        "",
        "## Blocking failures",
        "",
        *(
            ["None."]
            if not failures
            else [
                f"- `{item.check_id}`: {item.description} (expected `{item.expected}`, actual `{item.actual}`)"
                for item in failures
            ]
        ),
        "",
        "## Input and environment fingerprints",
        "",
        "| Input | Bytes | SHA-256 |",
        "|---|---:|---|",
        *[
            f"| {item.relative_path} | {item.byte_size} | `{item.sha256}` |"
            for item in report.inputs
        ],
        "",
        f"Python: `{report.environment.python}`  ",
        f"OS/architecture: `{report.environment.operating_system} / {report.environment.architecture}`  ",
        f"Timezone/locale: `{report.environment.timezone} / {report.environment.locale}`",
        "",
        "## Mathematical regression summary",
        "",
        _section_summary(report, "weekly_analytics", "baseline_correctness"),
        "",
        "## Candidate and verdict summary",
        "",
        _section_summary(report, "candidate_detection", "context_compilation"),
        "",
        "## Retrieval metrics",
        "",
        _metric_table(report, "retrieval_quality"),
        "",
        "## Evidence safety metrics",
        "",
        _metric_table(report, "evidence_gate"),
        "",
        "## Explanation-grounding metrics",
        "",
        _metric_table(report, "explanation_grounding"),
        "",
        "## Investigation-assistant metrics",
        "",
        _metric_table(report, "investigation_assistant"),
        "",
        "## Output-contract results",
        "",
        _section_summary(report, "output_contract"),
        "",
        "## Metamorphic results",
        "",
        _section_summary(report, "metamorphic_invariants"),
        "",
        "## Three-run reproducibility table",
        "",
        "| Run | Exit | Duration ms | Rows | Columns | Final SHA-256 |",
        "|---|---:|---:|---:|---:|---|",
        *[_run_line(item) for item in report.reproducibility.runs],
        "",
        "## Artifact hashes",
        "",
        *[
            f"- `{item.artifact_name}`: {'identical' if item.identical else 'different'} — {', '.join(item.hashes)}"
            for item in report.reproducibility.comparisons
        ],
        "",
        "## Performance observations",
        "",
        "Durations are informational; the configured subprocess timeout is the only blocking performance threshold.",
        "",
        "## Limitations and skipped non-blocking checks",
        "",
        "Dense-rank floating-point values are observed but are not blocking when structured recall preserves all accepted evidence. Peak memory is not measured because the project has no established profiler.",
        "",
        "## Exact rerun command",
        "",
        "```text",
        "cd backend",
        "python -m scripts.evaluate_pipeline --runs 3 --mode template",
        "```",
        "",
    ]
    return "\n".join(lines)


def _section_summary(report: EvaluationReport, *domains: str) -> str:
    selected = [item for item in report.checks if item.domain.value in domains]
    passed = sum(item.status.value == "pass" for item in selected)
    return f"{passed}/{len(selected)} checks passed."


def _metric_table(report: EvaluationReport, domain: str) -> str:
    selected = [item for item in report.metrics if item.domain.value == domain]
    if not selected:
        return "No metrics recorded."
    rows = ["| Metric | Value | Target |", "|---|---:|---:|"]
    rows.extend(
        f"| {item.metric_id} | {item.value} | {item.target_relation} {item.target if item.target is not None else '-'} |"
        for item in selected
    )
    return "\n".join(rows)


def _run_line(run) -> str:
    final = next(
        (
            item
            for item in run.artifacts
            if Path(item.relative_path).name == "final_submission.csv"
        ),
        None,
    )
    return f"| {run.run_id} | {run.exit_code} | {run.duration_ms} | {run.final_csv_rows} | {run.final_csv_columns} | `{final.sha256 if final else 'missing'}` |"


def _atomic_write(path: Path, content: str) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            delete=False,
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        ) as handle:
            temporary = Path(handle.name)
            handle.write(content)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
