"""Candidate supplied-data regression evaluator."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ..domain.evaluation import EvaluationCheck, EvaluationDomain
from .contracts import check


def evaluate_candidates(
    candidate_metrics: pd.DataFrame, fixture_path: Path
) -> list[EvaluationCheck]:
    candidates = candidate_metrics[candidate_metrics.candidate_anomaly].sort_values(
        ["route", "week_of"]
    )
    actual_keys = [
        (row.route, row.week_of.date().isoformat()) for row in candidates.itertuples()
    ]
    expected_keys = [
        tuple(item) for item in json.loads(fixture_path.read_text(encoding="utf-8"))
    ]
    domain = EvaluationDomain.CANDIDATE_DETECTION
    return [
        check(
            "candidate.count",
            domain,
            "Exactly 19 supplied candidates",
            len(candidates) == 19,
            expected=19,
            actual=len(candidates),
        ),
        check(
            "candidate.own_breaches",
            domain,
            "Own-history breach count",
            int(candidates.own_threshold_breached.sum()) == 6,
            expected=6,
            actual=int(candidates.own_threshold_breached.sum()),
        ),
        check(
            "candidate.peer_breaches",
            domain,
            "Peer breach count",
            int(candidates.peer_threshold_breached.sum()) == 18,
            expected=18,
            actual=int(candidates.peer_threshold_breached.sum()),
        ),
        check(
            "candidate.both_breaches",
            domain,
            "Both-baseline breach count",
            int(
                (
                    candidates.own_threshold_breached
                    & candidates.peer_threshold_breached
                ).sum()
            )
            == 5,
            expected=5,
            actual=int(
                (
                    candidates.own_threshold_breached
                    & candidates.peer_threshold_breached
                ).sum()
            ),
        ),
        check(
            "candidate.keys",
            domain,
            "Candidate keys match checked-in fixture",
            actual_keys == expected_keys,
            expected=expected_keys,
            actual=actual_keys,
        ),
        check(
            "candidate.rising",
            domain,
            "All candidates have positive own-history movement",
            bool((candidates.vs_own_history_pct > 0).all()),
        ),
        check(
            "candidate.unique_sorted",
            domain,
            "Candidate rows are unique and sorted",
            len(actual_keys) == len(set(actual_keys))
            and actual_keys == sorted(actual_keys),
        ),
    ]
