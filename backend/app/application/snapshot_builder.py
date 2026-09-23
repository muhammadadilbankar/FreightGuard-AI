"""Projection of trusted pipeline results into a deeply immutable API snapshot."""

from __future__ import annotations

import hashlib
import math
from collections import Counter, defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from types import MappingProxyType

import pandas as pd

from ..domain.evaluation import ArtifactFingerprint
from ..domain.evidence import EvidenceAssessment, EvidenceVerdict
from ..evaluation.contracts import fingerprint_file
from ..state.errors import AnalysisRunFailedError
from ..state.models import (
    AnalysisSnapshot,
    AnalysisSummary,
    AnomalyView,
    EvidenceGateResult,
    EvidenceSummary,
    RunMetricsView,
    TimelinePoint,
)
from .pipeline import PipelineExecutionResult


def build_snapshot(
    result: PipelineExecutionResult, *, mode: str, threshold: float
) -> AnalysisSnapshot:
    decision_by_key = {
        (packet.decision.route, packet.decision.week_of): packet.decision
        for packet in result.evidence.packets
    }
    record_by_key = {
        (record.route, record.week_of): record for record in result.explanation_records
    }
    audit_by_key = {
        (audit.route, audit.week_of): audit for audit in result.evidence.audits
    }
    final_by_key = {
        (row["route"], pd.Timestamp(row["week_of"]).date()): row
        for row in result.final_output.to_dict(orient="records")
    }
    notes_by_id = {note.note_id: note for note in result.notes}
    anomalies = []
    timelines: dict[str, list[TimelinePoint]] = defaultdict(list)
    for row in result.candidate_metrics.itertuples(index=False):
        week = pd.Timestamp(row.week_of).date()
        key = (row.route, week)
        decision = decision_by_key.get(key)
        verdict = decision.verdict if decision else None
        timelines[row.route].append(
            TimelinePoint(
                week_of=week,
                route_type=row.route_type,
                cost_per_tonne_km=_finite(row.cost_per_tonne_km),
                own_history_baseline=_optional(row.own_history_avg_cost_per_tonne_km),
                peer_baseline=_optional(row.similar_routes_avg_cost_per_tonne_km),
                vs_own_history_pct=_optional(row.vs_own_history_pct),
                vs_similar_routes_pct=_optional(row.vs_similar_routes_pct),
                history_weeks_used=int(row.history_weeks_used),
                peer_routes_used=int(row.peer_routes_used),
                candidate=bool(row.candidate_anomaly),
                verdict=verdict,
            )
        )
        if not row.candidate_anomaly:
            continue
        if decision is None or key not in record_by_key or key not in final_by_key:
            raise AnalysisRunFailedError("Candidate snapshot reconciliation failed.")
        record = record_by_key[key]
        audit = audit_by_key[key]
        final_row = final_by_key[key]
        trigger = (
            "both"
            if row.own_threshold_breached and row.peer_threshold_breached
            else "own_history"
            if row.own_threshold_breached
            else "peer"
        )
        anomalies.append(
            AnomalyView(
                candidate_key=f"{row.route}|{week.isoformat()}",
                route=row.route,
                route_type=row.route_type,
                week_of=week,
                cost_per_tonne_km=_finite(row.cost_per_tonne_km),
                own_history_baseline=_optional(row.own_history_avg_cost_per_tonne_km),
                peer_baseline=_optional(row.similar_routes_avg_cost_per_tonne_km),
                vs_own_history_pct=_finite(row.vs_own_history_pct),
                vs_similar_routes_pct=_optional(row.vs_similar_routes_pct),
                history_weeks_used=int(row.history_weeks_used),
                peer_routes_used=int(row.peer_routes_used),
                own_threshold_breached=bool(row.own_threshold_breached),
                peer_threshold_breached=bool(row.peer_threshold_breached),
                trigger=trigger,
                verdict=decision.verdict,
                flagged=str(final_row["flagged"]),
                matched_note_id=decision.selected_note_id,
                supporting_note_ids=decision.supporting_note_ids,
                decision_code=decision.reason_template_key.value,
                reason=record.reason,
                evidence=tuple(
                    EvidenceSummary(
                        note_id=item.note_id,
                        evidence_level=item.evidence_level.value,
                        role=(
                            "primary"
                            if item.note_id == decision.selected_note_id
                            else "supporting"
                            if item.note_id in decision.supporting_note_ids
                            else "rejected"
                        ),
                        rejection_codes=tuple(
                            code.value for code in item.rejection_codes
                        ),
                        original_text=notes_by_id[item.note_id].original_text,
                        scope_type=notes_by_id[item.note_id].scope_type.value,
                        applies_to_routes=notes_by_id[item.note_id].applies_to_routes,
                        effective_from=notes_by_id[item.note_id].effective_from,
                        effective_to=notes_by_id[item.note_id].effective_to,
                        event_type=notes_by_id[item.note_id].event_type.value,
                        impact_direction=notes_by_id[item.note_id].impact_direction.value,
                        affects_transport_cost=notes_by_id[
                            item.note_id
                        ].affects_transport_cost,
                        magnitude_text=notes_by_id[item.note_id].magnitude_text,
                        gate_results=_gate_results(item),
                    )
                    for item in audit.assessments
                ),
                explanation_source=record.explanation_source.value,
                fallback_used=record.explanation_source.value == "fallback",
            )
        )
    anomalies.sort(key=lambda item: (item.week_of, item.route, item.route_type))
    if len({item.candidate_key for item in anomalies}) != len(anomalies):
        raise AnalysisRunFailedError("Snapshot candidate keys must be unique.")
    frozen_timelines = AnalysisSnapshot.freeze_timelines(
        {
            route: tuple(sorted(points, key=lambda item: item.week_of))
            for route, points in timelines.items()
        }
    )
    verdicts = Counter(item.verdict for item in anomalies)
    summary = AnalysisSummary(
        shipment_count=len(result.bundle.shipments),
        route_count=len(frozen_timelines),
        route_type_count=int(result.weekly["route_type"].nunique()),
        weekly_record_count=len(result.weekly),
        candidate_count=len(anomalies),
        justified_count=verdicts[EvidenceVerdict.JUSTIFIED],
        partially_explained_count=verdicts[EvidenceVerdict.PARTIALLY_EXPLAINED],
        unexplained_count=verdicts[EvidenceVerdict.UNEXPLAINED],
        analysis_from=min(
            point.week_of for points in frozen_timelines.values() for point in points
        ),
        analysis_to=max(
            point.week_of for points in frozen_timelines.values() for point in points
        ),
        anomaly_threshold_percent=threshold,
        explanation_mode=mode,
        evaluation_status=result.evaluation.overall_status,
        final_csv_sha256=result.final_csv_sha256,
    )
    if (
        summary.justified_count
        + summary.partially_explained_count
        + summary.unexplained_count
        != summary.candidate_count
    ):
        raise AnalysisRunFailedError("Snapshot verdict counts do not reconcile.")
    for anomaly in anomalies:
        points = frozen_timelines.get(anomaly.route, ())
        if not any(
            point.week_of == anomaly.week_of and point.candidate for point in points
        ):
            raise AnalysisRunFailedError("Anomaly is missing from its route timeline.")
    timeline_candidate_keys = {
        (route, point.week_of)
        for route, points in frozen_timelines.items()
        for point in points
        if point.candidate
    }
    anomaly_keys = {(item.route, item.week_of) for item in anomalies}
    if timeline_candidate_keys != anomaly_keys:
        raise AnalysisRunFailedError(
            "Candidate timeline points do not reconcile with anomalies."
        )
    usage_input = sum(item.usage.input_tokens for item in result.explanation_records)
    usage_output = sum(item.usage.output_tokens for item in result.explanation_records)
    costs = [item.estimated_cost_usd for item in result.explanation_records]
    metrics = RunMetricsView(
        stage_durations_ms=MappingProxyType(dict(result.stage_durations_ms)),
        total_duration_ms=result.total_duration_ms,
        row_counts=MappingProxyType(
            {
                "shipments": len(result.bundle.shipments),
                "weekly": len(result.weekly),
                "candidates": len(anomalies),
                "compiled_notes": len(result.notes),
            }
        ),
        retrieval_hit_count=sum(
            len(items) for items in result.evidence.fused_rankings.values()
        ),
        explanation_request_count=sum(
            item.verdict != EvidenceVerdict.UNEXPLAINED
            for item in result.explanation_records
        ),
        hosted_model_call_count=sum(
            item.provider_attempts for item in result.explanation_records
        ),
        input_tokens=usage_input,
        output_tokens=usage_output,
        estimated_cost_usd=(
            None if any(item is None for item in costs) else sum(costs, Decimal(0))
        ),
        cache_hits=sum(item.cache_hit for item in result.explanation_records),
        cache_misses=sum(
            not item.cache_hit and item.provider_attempts > 0
            for item in result.explanation_records
        ),
        fallback_count=sum(
            item.explanation_source.value == "fallback"
            for item in result.explanation_records
        ),
    )
    config = result.evaluation.configuration_fingerprint
    snapshot_id = hashlib.sha256(
        f"{result.final_csv_sha256}:{config}".encode()
    ).hexdigest()[:16]
    return AnalysisSnapshot(
        snapshot_id=snapshot_id,
        created_at=datetime.now(UTC),
        configuration_fingerprint=config,
        input_fingerprints=result.evaluation.inputs,
        artifact_fingerprints=(
            ArtifactFingerprint(
                **fingerprint_file(result.final_csv_path).model_dump(), run_id=None
            ),
            ArtifactFingerprint(
                **fingerprint_file(result.explanation_audit_path).model_dump(),
                run_id=None,
            ),
        ),
        summary=summary,
        anomalies=tuple(anomalies),
        route_timelines=frozen_timelines,
        evaluation=result.evaluation,
        evaluation_report_sha256=result.evaluation_report_sha256,
        run_metrics=metrics,
        export_csv_path=result.final_csv_path.resolve(),
        export_csv_sha256=result.final_csv_sha256,
    )


def _optional(value: object) -> float | None:
    return None if pd.isna(value) else _finite(value)


def _finite(value: object) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise AnalysisRunFailedError("Snapshot contains a non-finite number.")
    return number


def _gate_results(
    assessment: EvidenceAssessment,
) -> tuple[EvidenceGateResult, ...]:
    """Project existing deterministic checks into UI-safe audit statements."""
    rejection_codes = {code.value for code in assessment.rejection_codes}
    definitions = (
        ("route", assessment.route_check, ("route_mismatch",)),
        ("date", assessment.date_check, ("date_no_overlap",)),
        (
            "direction",
            assessment.direction_check,
            ("impact_direction_not_increase",),
        ),
        (
            "cost_impact",
            assessment.cost_impact_check,
            ("cost_impact_not_positive", "cost_increase_negated"),
        ),
        (
            "scope",
            assessment.scope_check,
            (
                "scope_outside_dataset",
                "scope_unresolved",
                "global_scope_cannot_explain_peer_premium",
                "global_magnitude_insufficient",
            ),
        ),
    )
    labels = {
        "pass": "The deterministic Evidence Gate passed this check.",
        "fail": "The deterministic Evidence Gate rejected this check.",
        "not_applicable": "This check was not applicable.",
    }
    return tuple(
        EvidenceGateResult(
            gate=gate,
            status=status.value,
            reason_code=next(
                (code for code in codes if code in rejection_codes), None
            ),
            reason=labels[status.value],
        )
        for gate, status, codes in definitions
    )
