"""Deterministic TF-IDF lexical retrieval."""

from collections.abc import Mapping, Sequence
from datetime import date

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from ...domain.context_notes import CompiledContextNote
from ...domain.evidence import CandidateEvidenceQuery, RetrievalHit
from ..evidence.queries import candidate_key
from ..evidence.retrieval_documents import build_retrieval_documents
from ..evidence.errors import RetrievalContractError

CandidateKey = tuple[str, date]


def retrieve_sparse(
    queries: Sequence[CandidateEvidenceQuery],
    notes: Sequence[CompiledContextNote],
    top_k: int,
) -> Mapping[CandidateKey, tuple[RetrievalHit, ...]]:
    """Rank note documents by normalized unigram/bigram TF-IDF dot product."""
    if top_k < 1:
        raise RetrievalContractError("Sparse retrieval top_k must be positive.")
    documents = build_retrieval_documents(notes)
    if not queries:
        raise RetrievalContractError("Sparse retrieval requires queries.")
    vectorizer = TfidfVectorizer(
        lowercase=True, ngram_range=(1, 2), sublinear_tf=True, norm="l2"
    )
    try:
        document_matrix = vectorizer.fit_transform(text for _, text in documents)
        query_matrix = vectorizer.transform(query.query_text for query in queries)
    except ValueError as exc:
        raise RetrievalContractError(
            "Sparse retrieval could not build a non-empty vocabulary."
        ) from exc
    similarities = np.asarray((query_matrix @ document_matrix.T).toarray(), dtype=float)
    if not np.isfinite(similarities).all():
        raise RetrievalContractError("Sparse retrieval produced non-finite scores.")
    limit = min(top_k, len(documents))
    results: dict[CandidateKey, tuple[RetrievalHit, ...]] = {}
    for query_index, query in enumerate(queries):
        ranked = sorted(
            zip((note_id for note_id, _ in documents), similarities[query_index], strict=True),
            key=lambda item: (-float(item[1]), item[0]),
        )[:limit]
        results[candidate_key(query)] = tuple(
            RetrievalHit(note_id=note_id, sparse_rank=rank, sparse_score=float(score))
            for rank, (note_id, score) in enumerate(ranked, start=1)
        )
    return results
