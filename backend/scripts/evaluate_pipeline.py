"""CLI for Phase 9 evaluation and three-run reproducibility."""

from __future__ import annotations

import argparse
from pathlib import Path

from backend.app.core.config import get_settings
from backend.app.evaluation import run_evaluation
from backend.app.evaluation.errors import EvaluationConfigurationError, EvaluationError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate FreightGuard deterministically."
    )
    parser.add_argument("--runs", type=int, default=None)
    parser.add_argument("--mode", choices=("template", "replay", "live"), default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--explanation-cache", type=Path, default=None)
    args = parser.parse_args(argv)
    base = get_settings()
    updates = {}
    if args.output_root is not None:
        updates["evaluation_output_root"] = args.output_root.resolve()
    if args.explanation_cache is not None:
        updates["explanation_cache_path"] = args.explanation_cache.resolve()
    settings = base.model_copy(update=updates)
    runs = args.runs if args.runs is not None else settings.evaluation_runs
    mode = args.mode if args.mode is not None else settings.evaluation_mode
    print("FreightGuard evaluation")
    print(f"Mode: {mode}")
    print(f"Formal runs: {runs}")
    try:
        report, paths = run_evaluation(settings, run_count=runs, mode=mode)
    except EvaluationConfigurationError as exc:
        print(f"Configuration: FAIL ({exc})")
        return 2
    except EvaluationError as exc:
        print(f"Evaluation: FAIL ({exc})")
        return 3
    domains = sorted(
        {item.domain for item in report.checks}, key=lambda item: item.value
    )
    for domain in domains:
        passed = all(
            item.status.value == "pass"
            for item in report.checks
            if item.domain == domain and item.blocking
        )
        print(f"{domain.value}: {'PASS' if passed else 'FAIL'}")
    metric_map = {item.metric_id: item.value for item in report.metrics}
    print(
        f"False clearance rate: {metric_map.get('evidence.false_clearance_rate', 0.0):.1%}"
    )
    print(
        f"Unsafe evidence acceptance rate: {metric_map.get('evidence.unsafe_evidence_acceptance_rate', 0.0):.1%}"
    )
    comparison = next(
        item
        for item in report.reproducibility.comparisons
        if item.artifact_name == "final_submission.csv"
    )
    print(
        f"Final CSV SHA-256: {comparison.hashes[0] if comparison.hashes else 'missing'}"
    )
    print(f"Overall: {report.overall_status.upper()}")
    print(f"JSON report: {paths[0]}")
    print(f"Markdown report: {paths[1]}")
    print(f"Manifest: {paths[2]}")
    return 0 if report.overall_status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
