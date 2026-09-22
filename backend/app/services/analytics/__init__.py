"""Public deterministic analytics services."""

from .baselines import (
    add_comparison_baselines,
    summarize_baselines,
    validate_baseline_reconciliation,
)
from .candidates import detect_candidate_anomalies
from .comparisons import add_percentage_comparisons
from .errors import (
    AnalyticsError,
    AnalyticsInputError,
    AnalyticsInvariantError,
    CandidateDetectionError,
)
from .weekly_cost import (
    calculate_weekly_route_metrics,
    summarize_weekly_metrics,
    validate_weekly_metrics_reconciliation,
)

__all__ = [
    "AnalyticsError",
    "AnalyticsInputError",
    "AnalyticsInvariantError",
    "CandidateDetectionError",
    "add_comparison_baselines",
    "add_percentage_comparisons",
    "calculate_weekly_route_metrics",
    "detect_candidate_anomalies",
    "summarize_baselines",
    "summarize_weekly_metrics",
    "validate_baseline_reconciliation",
    "validate_weekly_metrics_reconciliation",
]
