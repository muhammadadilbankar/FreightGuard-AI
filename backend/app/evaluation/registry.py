"""Stable registry validation and ordering."""

from __future__ import annotations

from collections.abc import Iterable

from ..domain.evaluation import EvaluationCheck, EvaluationMetric


def normalize_registry(
    checks: Iterable[EvaluationCheck], metrics: Iterable[EvaluationMetric]
) -> tuple[tuple[EvaluationCheck, ...], tuple[EvaluationMetric, ...]]:
    ordered_checks = tuple(
        sorted(checks, key=lambda item: (item.domain.value, item.check_id))
    )
    ordered_metrics = tuple(
        sorted(metrics, key=lambda item: (item.domain.value, item.metric_id))
    )
    if len({item.check_id for item in ordered_checks}) != len(ordered_checks):
        raise ValueError("Duplicate evaluation check ID.")
    if len({item.metric_id for item in ordered_metrics}) != len(ordered_metrics):
        raise ValueError("Duplicate evaluation metric ID.")
    return ordered_checks, ordered_metrics
