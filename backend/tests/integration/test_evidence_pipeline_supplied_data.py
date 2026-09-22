"""Phase 2-through-7 supplied-data decision regression."""

from collections import Counter

import numpy as np

from backend.app.core.config import get_settings
from backend.app.domain.evidence import EvidencePolicy, EvidenceVerdict, RetrievalConfig
from backend.app.services.analytics import (
    add_comparison_baselines,
    add_percentage_comparisons,
    calculate_weekly_route_metrics,
    detect_candidate_anomalies,
)
from backend.app.services.context import compile_context_notes
from backend.app.services.evidence import build_candidate_queries, review_candidate_evidence
from backend.app.services.ingestion import load_input_bundle


class OfflineFakeProvider:
    def encode_documents(self, texts: list[str]) -> np.ndarray:
        return np.ones((len(texts), 3))

    def encode_queries(self, texts: list[str]) -> np.ndarray:
        return np.ones((len(texts), 3))


def supplied_result():
    settings = get_settings()
    bundle = load_input_bundle(settings)
    weekly = calculate_weekly_route_metrics(bundle.shipments)
    detected = detect_candidate_anomalies(
        add_percentage_comparisons(add_comparison_baselines(weekly)),
        settings.anomaly_threshold_percent,
    )
    notes = compile_context_notes(
        bundle.context_notes, frozenset(bundle.shipments["route"].unique())
    )
    result = review_candidate_evidence(
        build_candidate_queries(detected),
        notes,
        OfflineFakeProvider(),
        RetrievalConfig(top_k=5, rrf_k=60, sparse_weight=1, dense_weight=1),
        EvidencePolicy(global_magnitude_tolerance_percent=2),
    )
    return bundle, weekly, detected, notes, result


def test_supplied_data_exact_decision_contract() -> None:
    _, weekly, detected, notes, result = supplied_result()
    decisions = [packet.decision for packet in result.packets]
    counts = Counter(item.verdict for item in decisions)
    assert len(weekly) == 728
    assert int(detected["candidate_anomaly"].sum()) == 19
    assert len(notes) == 10
    assert len(decisions) == 19
    assert counts == {
        EvidenceVerdict.JUSTIFIED: 3,
        EvidenceVerdict.PARTIALLY_EXPLAINED: 12,
        EvidenceVerdict.UNEXPLAINED: 4,
    }
    selected = {
        (item.route, item.week_of.isoformat()): item.selected_note_id
        for item in decisions
        if item.selected_note_id
    }
    assert selected == {
        ("Ahmedabad-Mumbai", "2025-01-20"): "N002",
        ("Chennai-Bangalore", "2025-02-24"): "N001",
        ("Chennai-Bangalore", "2025-03-03"): "N001",
    }
    partial = [
        item for item in decisions
        if item.verdict == EvidenceVerdict.PARTIALLY_EXPLAINED
    ]
    assert all(item.route == "Mumbai-Pune" for item in partial)
    assert all(item.supporting_note_ids == ("N003",) for item in partial)


def test_phase8_packets_allow_only_accepted_notes() -> None:
    *_, result = supplied_result()
    for packet in result.packets:
        assert packet.allowed_note_ids == tuple(
            sorted(
                ({packet.selected_note.note_id} if packet.selected_note else set())
                | {note.note_id for note in packet.supporting_notes}
            )
        )
        assert set(packet.allowed_note_ids).isdisjoint(
            assessment.note_id
            for assessment in next(
                audit for audit in result.audits
                if audit.route == packet.candidate.route
                and audit.week_of == packet.candidate.week_of
            ).assessments
            if assessment.evidence_level.value == "rejected"
        )
