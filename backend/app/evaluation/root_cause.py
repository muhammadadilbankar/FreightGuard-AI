"""Independent acceptance checks for Phase 12 operational leads."""

from ..domain.evaluation import EvaluationCheck, EvaluationDomain, EvaluationMetric
from ..domain.root_cause import RootCauseAnalysis
from .contracts import check


def evaluate_root_causes(
    results: tuple[RootCauseAnalysis, ...], *, expected_eligible: int, tolerance: float
) -> tuple[tuple[EvaluationCheck, ...], tuple[EvaluationMetric, ...]]:
    checks = (
        check(
            "root_cause.eligible_coverage",
            EvaluationDomain.OPERATIONAL_ROOT_CAUSE,
            "Every unexplained anomaly has one operational analysis",
            len(results) == expected_eligible,
            expected=expected_eligible,
            actual=len(results),
        ),
        check(
            "root_cause.reconstruction",
            EvaluationDomain.OPERATIONAL_ROOT_CAUSE,
            "Both independent lenses reconstruct the canonical own-history gap",
            all(
                abs(result.transporter.reconstruction_error) <= tolerance
                and abs(result.material.reconstruction_error) <= tolerance
                for result in results
            ),
            expected=f"absolute error <= {tolerance}",
            actual=max(
                (
                    max(
                        abs(result.transporter.reconstruction_error),
                        abs(result.material.reconstruction_error),
                    )
                    for result in results
                ),
                default=0.0,
            ),
        ),
        check(
            "root_cause.no_lookahead",
            EvaluationDomain.OPERATIONAL_ROOT_CAUSE,
            "All reference weeks strictly precede their candidate week",
            all(
                all(week < result.week_of for week in result.reference_weeks)
                for result in results
            ),
        ),
        check(
            "root_cause.verdict_boundary",
            EvaluationDomain.OPERATIONAL_ROOT_CAUSE,
            "Operational analyses retain the unexplained canonical verdict",
            all(result.canonical_verdict == "unexplained" for result in results),
        ),
    )
    metrics = (
        EvaluationMetric(
            metric_id="root_cause.analysis_count",
            domain=EvaluationDomain.OPERATIONAL_ROOT_CAUSE,
            value=len(results),
            unit="analyses",
            target=expected_eligible,
            target_relation="eq",
            blocking=True,
            numerator=len(results),
            denominator=expected_eligible,
        ),
    )
    return checks, metrics
