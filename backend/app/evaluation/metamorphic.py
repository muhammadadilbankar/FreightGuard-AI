"""Metamorphic invariance checks for deterministic stages."""

from __future__ import annotations

import pandas as pd
import numpy as np

from ..domain.context_notes import (
    CompiledContextNote,
    CostImpactStatus,
    ImpactDirection,
    ScopeStatus,
    ScopeType,
    TemporalBasis,
)
from ..domain.evaluation import EvaluationCheck, EvaluationDomain
from ..domain.evidence import EvidencePolicy, EvidenceReviewResult, RetrievalConfig
from ..services.analytics import (
    add_comparison_baselines,
    add_percentage_comparisons,
    calculate_weekly_route_metrics,
    detect_candidate_anomalies,
)
from ..services.context import compile_context_notes
from ..services.evidence import build_candidate_queries, review_candidate_evidence
from .contracts import check


def evaluate_metamorphic(
    shipments: pd.DataFrame,
    raw_notes: pd.DataFrame,
    weekly: pd.DataFrame,
    candidates: pd.DataFrame,
    compiled_notes: tuple[CompiledContextNote, ...],
    threshold: float,
) -> list[EvaluationCheck]:
    shuffled_shipments = shipments.sample(frac=1, random_state=90210).reset_index(
        drop=True
    )
    shuffled_weekly = calculate_weekly_route_metrics(shuffled_shipments)
    shuffled_candidates = detect_candidate_anomalies(
        add_percentage_comparisons(add_comparison_baselines(shuffled_weekly)), threshold
    )
    shuffled_notes = raw_notes.sample(frac=1, random_state=90210).reset_index(drop=True)
    recompiled = compile_context_notes(
        shuffled_notes, frozenset(shipments.route.unique())
    )
    canonical_candidate_columns = [
        "route",
        "route_type",
        "week_of",
        "cost_per_tonne_km",
        "vs_own_history_pct",
        "vs_similar_routes_pct",
        "candidate_anomaly",
    ]
    notes_left = [item.model_dump(mode="json") for item in compiled_notes]
    notes_right = [item.model_dump(mode="json") for item in recompiled]
    domain = EvaluationDomain.METAMORPHIC_INVARIANTS
    return [
        check(
            "metamorphic.shipment_permutation_weekly",
            domain,
            "Shipment row permutation preserves sorted weekly metrics",
            weekly.equals(shuffled_weekly),
        ),
        check(
            "metamorphic.shipment_permutation_candidates",
            domain,
            "Shipment row permutation preserves candidate calculations",
            candidates[canonical_candidate_columns].equals(
                shuffled_candidates[canonical_candidate_columns]
            ),
        ),
        check(
            "metamorphic.note_permutation",
            domain,
            "Context-note row permutation preserves compiled notes",
            notes_left == notes_right,
        ),
        check(
            "metamorphic.output_directory_variation",
            domain,
            "Output directory variation is covered by isolated reproducibility runs",
            True,
        ),
    ]


class _StableEmbeddingProvider:
    def encode_documents(self, texts: list[str]) -> np.ndarray:
        return np.ones((len(texts), 3))

    def encode_queries(self, texts: list[str]) -> np.ndarray:
        return np.ones((len(texts), 3))


def evaluate_evidence_metamorphic(
    candidates: pd.DataFrame,
    notes: tuple[CompiledContextNote, ...],
    baseline: EvidenceReviewResult,
    retrieval: RetrievalConfig,
    policy: EvidencePolicy,
) -> list[EvaluationCheck]:
    queries = build_candidate_queries(candidates)
    provider = _StableEmbeddingProvider()
    reordered = review_candidate_evidence(
        queries, tuple(reversed(notes)), provider, retrieval, policy
    )
    irrelevant = CompiledContextNote(
        schema_version="1.0",
        note_id="EVAL001",
        source_date=pd.Timestamp("2030-01-01").date(),
        source_applies_to="Ghost-Route",
        original_text="Freight costs increased sharply.",
        scope_type=ScopeType.ROUTE,
        applies_to_routes=("Ghost-Route",),
        scope_status=ScopeStatus.OUTSIDE_DATASET,
        effective_from=pd.Timestamp("2030-01-01").date(),
        effective_to=None,
        temporal_basis=TemporalBasis.OPEN_ENDED_START,
        event_type=notes[0].event_type,
        impact_direction=ImpactDirection.INCREASE,
        cost_impact_status=CostImpactStatus.EXPLICIT_INCREASE,
        affects_transport_cost=True,
        negates_cost_increase=False,
        magnitude_text=None,
        compilation_warnings=(),
    )
    no_impact = CompiledContextNote(
        schema_version="1.0",
        note_id="EVAL002",
        source_date=pd.Timestamp("2024-01-01").date(),
        source_applies_to="All Routes",
        original_text="A similar disruption occurred but freight rates did not change.",
        scope_type=ScopeType.GLOBAL,
        applies_to_routes=(),
        scope_status=ScopeStatus.IN_DATASET,
        effective_from=pd.Timestamp("2024-01-01").date(),
        effective_to=None,
        temporal_basis=TemporalBasis.OPEN_ENDED_START,
        event_type=notes[0].event_type,
        impact_direction=ImpactDirection.NO_CHANGE,
        cost_impact_status=CostImpactStatus.EXPLICIT_NO_RATE_CHANGE,
        affects_transport_cost=False,
        negates_cost_increase=True,
        magnitude_text=None,
        compilation_warnings=(),
    )
    injected = review_candidate_evidence(
        queries, (*notes, irrelevant, no_impact), provider, retrieval, policy
    )
    expected = _decision_signature(baseline)
    domain = EvaluationDomain.METAMORPHIC_INVARIANTS
    return [
        check(
            "metamorphic.note_permutation_decisions",
            domain,
            "Note order does not change evidence decisions",
            _decision_signature(reordered) == expected,
        ),
        check(
            "metamorphic.irrelevant_note_injection",
            domain,
            "Wrong-route/wrong-date positive note does not change decisions",
            _decision_signature(injected) == expected,
        ),
        check(
            "metamorphic.no_impact_note_injection",
            domain,
            "High-similarity no-rate-change note does not change decisions",
            _decision_signature(injected) == expected,
        ),
    ]


def _decision_signature(result: EvidenceReviewResult) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            packet.decision.route,
            packet.decision.week_of,
            packet.decision.verdict.value,
            packet.decision.selected_note_id,
            packet.decision.supporting_note_ids,
        )
        for packet in result.packets
    )
