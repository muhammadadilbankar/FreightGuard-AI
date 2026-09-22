"""Public hybrid retrieval and deterministic Evidence Gate services."""

from .decisions import build_evidence_packet, decide_evidence
from .errors import (
    EmbeddingProviderError,
    EvidenceDecisionError,
    EvidenceError,
    EvidenceGateError,
    EvidenceInputError,
    RetrievalConfigurationError,
    RetrievalContractError,
)
from .gate import assess_evidence
from .hybrid import fuse_rankings
from .metrics import RetrievalMetrics, evaluate_retrieval
from .pipeline import review_candidate_evidence
from .queries import build_candidate_queries, build_candidate_query, candidate_key
from .recall import structured_recall, union_retrieval_and_recall
from .retrieval_documents import build_retrieval_document, build_retrieval_documents

__all__ = [
    "EmbeddingProviderError",
    "EvidenceDecisionError",
    "EvidenceError",
    "EvidenceGateError",
    "EvidenceInputError",
    "RetrievalConfigurationError",
    "RetrievalContractError",
    "RetrievalMetrics",
    "assess_evidence",
    "build_candidate_queries",
    "build_candidate_query",
    "build_evidence_packet",
    "build_retrieval_document",
    "build_retrieval_documents",
    "candidate_key",
    "decide_evidence",
    "evaluate_retrieval",
    "fuse_rankings",
    "review_candidate_evidence",
    "structured_recall",
    "union_retrieval_and_recall",
]
