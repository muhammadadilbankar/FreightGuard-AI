"""Deterministic in-memory dense cosine retrieval."""

from collections.abc import Mapping, Sequence
from datetime import date

import numpy as np

from ...domain.context_notes import CompiledContextNote
from ...domain.evidence import CandidateEvidenceQuery, RetrievalHit
from ..evidence.errors import RetrievalContractError
from ..evidence.queries import candidate_key
from ..evidence.retrieval_documents import build_retrieval_documents
from .embeddings import EmbeddingProvider

CandidateKey = tuple[str, date]


def retrieve_dense(
    queries: Sequence[CandidateEvidenceQuery],
    notes: Sequence[CompiledContextNote],
    provider: EmbeddingProvider,
    top_k: int,
) -> Mapping[CandidateKey, tuple[RetrievalHit, ...]]:
    """Encode once per side, normalize, and rank by cosine dot product."""
    if top_k < 1:
        raise RetrievalContractError("Dense retrieval top_k must be positive.")
    documents = build_retrieval_documents(notes)
    if not queries:
        raise RetrievalContractError("Dense retrieval requires queries.")
    document_vectors = _normalized_matrix(
        provider.encode_documents([text for _, text in documents]),
        len(documents),
        "document",
    )
    query_vectors = _normalized_matrix(
        provider.encode_queries([query.query_text for query in queries]),
        len(queries),
        "query",
    )
    if document_vectors.shape[1] != query_vectors.shape[1]:
        raise RetrievalContractError("Dense query and document dimensions must match.")
    similarities = query_vectors @ document_vectors.T
    limit = min(top_k, len(documents))
    results: dict[CandidateKey, tuple[RetrievalHit, ...]] = {}
    for query_index, query in enumerate(queries):
        ranked = sorted(
            zip((note_id for note_id, _ in documents), similarities[query_index], strict=True),
            key=lambda item: (-float(item[1]), item[0]),
        )[:limit]
        results[candidate_key(query)] = tuple(
            RetrievalHit(note_id=note_id, dense_rank=rank, dense_score=float(score))
            for rank, (note_id, score) in enumerate(ranked, start=1)
        )
    return results


def _normalized_matrix(values: object, rows: int, label: str) -> np.ndarray:
    matrix = np.asarray(values, dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] != rows or matrix.shape[1] < 1:
        raise RetrievalContractError(
            f"Dense {label} vectors must be a two-dimensional row matrix."
        )
    if not np.isfinite(matrix).all():
        raise RetrievalContractError(f"Dense {label} vectors must be finite.")
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    if (norms == 0).any():
        raise RetrievalContractError(f"Dense {label} vectors must be non-zero.")
    return matrix / norms
