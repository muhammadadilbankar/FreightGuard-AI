"""Sparse and dense retrieval contract tests without model downloads."""

import numpy as np
import pytest

from backend.app.domain.evidence import CandidateEvidenceQuery
from backend.app.services.context import compile_context_notes
from backend.app.services.evidence import build_candidate_queries
from backend.app.services.evidence.errors import RetrievalContractError
from backend.app.services.ingestion import load_input_bundle
from backend.app.services.retrieval import retrieve_dense, retrieve_sparse
from backend.app.services.analytics import (
    add_comparison_baselines,
    add_percentage_comparisons,
    calculate_weekly_route_metrics,
    detect_candidate_anomalies,
)
from backend.app.core.config import get_settings


class FakeProvider:
    """Stable injected vectors; tests never instantiate Sentence Transformers."""

    def encode_documents(self, texts: list[str]) -> np.ndarray:
        return np.asarray([[index + 1.0, 1.0] for index in range(len(texts))])

    def encode_queries(self, texts: list[str]) -> np.ndarray:
        return np.asarray([[1.0, 1.0] for _ in texts])


def _inputs() -> tuple[tuple[CandidateEvidenceQuery, ...], tuple]:
    settings = get_settings()
    bundle = load_input_bundle(settings)
    weekly = calculate_weekly_route_metrics(bundle.shipments)
    detected = detect_candidate_anomalies(
        add_percentage_comparisons(add_comparison_baselines(weekly)),
        settings.anomaly_threshold_percent,
    )
    queries = build_candidate_queries(detected)
    notes = compile_context_notes(
        bundle.context_notes, frozenset(bundle.shipments["route"].unique())
    )
    return queries[:2], notes


def test_sparse_retrieval_is_ranked_finite_and_deterministic() -> None:
    queries, notes = _inputs()
    first = retrieve_sparse(queries, notes, 5)
    second = retrieve_sparse(tuple(reversed(queries)), tuple(reversed(notes)), 5)
    for query in queries:
        key = (query.route, query.week_of)
        assert first[key] == second[key]
        assert [hit.sparse_rank for hit in first[key]] == [1, 2, 3, 4, 5]
        assert all(hit.sparse_score is not None for hit in first[key])


def test_dense_retrieval_uses_injected_provider_and_stable_ties() -> None:
    queries, notes = _inputs()
    result = retrieve_dense(queries, notes, FakeProvider(), 3)
    for query in queries:
        hits = result[(query.route, query.week_of)]
        assert len(hits) == 3
        assert [hit.dense_rank for hit in hits] == [1, 2, 3]
        assert all(np.isfinite(hit.dense_score) for hit in hits)


def test_dense_retrieval_rejects_zero_vectors() -> None:
    queries, notes = _inputs()

    class ZeroProvider(FakeProvider):
        def encode_documents(self, texts: list[str]) -> np.ndarray:
            return np.zeros((len(texts), 2))

    with pytest.raises(RetrievalContractError, match="non-zero"):
        retrieve_dense(queries, notes, ZeroProvider(), 3)
