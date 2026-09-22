"""Pure orchestration across retrieval, recall, gate, decisions, and packets."""

from collections import Counter
from collections.abc import Sequence
from datetime import date
import logging
from time import perf_counter

from ...core.logging import LOGGER_NAME
from ...domain.context_notes import CompiledContextNote
from ...domain.evidence import (
    CandidateEvidenceAudit,
    CandidateEvidenceQuery,
    EvidencePolicy,
    EvidenceReviewResult,
    RetrievalConfig,
)
from ..retrieval import EmbeddingProvider, retrieve_dense, retrieve_sparse
from .decisions import build_evidence_packet, decide_evidence
from .errors import EvidenceInputError
from .gate import assess_evidence
from .hybrid import fuse_rankings
from .queries import candidate_key
from .recall import structured_recall, union_retrieval_and_recall

logger = logging.getLogger(f"{LOGGER_NAME}.evidence")


def review_candidate_evidence(
    queries: Sequence[CandidateEvidenceQuery],
    notes: Sequence[CompiledContextNote],
    provider: EmbeddingProvider,
    retrieval_config: RetrievalConfig,
    evidence_policy: EvidencePolicy,
) -> EvidenceReviewResult:
    """Review every candidate while keeping retrieval subordinate to the gate."""
    ordered_queries = tuple(sorted(queries, key=lambda item: (item.route, item.week_of)))
    ordered_notes = tuple(sorted(notes, key=lambda item: item.note_id))
    if not ordered_queries or not ordered_notes:
        raise EvidenceInputError("Evidence review requires candidates and compiled notes.")
    if len({candidate_key(query) for query in ordered_queries}) != len(ordered_queries):
        raise EvidenceInputError("Candidate evidence keys must be unique.")
    if len({note.note_id for note in ordered_notes}) != len(ordered_notes):
        raise EvidenceInputError("Compiled note IDs must be unique.")

    logger.info(
        "Starting evidence review candidates=%d notes=%d top_k=%d rrf_k=%d "
        "sparse_weight=%g dense_weight=%g",
        len(ordered_queries),
        len(ordered_notes),
        retrieval_config.top_k,
        retrieval_config.rrf_k,
        retrieval_config.sparse_weight,
        retrieval_config.dense_weight,
    )
    started = perf_counter()
    sparse = dict(retrieve_sparse(ordered_queries, ordered_notes, retrieval_config.top_k))
    sparse_seconds = perf_counter() - started
    started = perf_counter()
    dense = dict(
        retrieve_dense(
            ordered_queries, ordered_notes, provider, retrieval_config.top_k
        )
    )
    dense_seconds = perf_counter() - started
    notes_by_id = {note.note_id: note for note in ordered_notes}
    fused: dict[tuple[str, date], tuple] = {}
    packets = []
    audits = []
    structured_additions = 0
    for query in ordered_queries:
        key = candidate_key(query)
        fused_hits = fuse_rankings(sparse[key], dense[key], retrieval_config)
        fused[key] = fused_hits
        recalled = structured_recall(query, ordered_notes)
        fused_ids = {hit.note_id for hit in fused_hits}
        structured_additions += len(set(recalled) - fused_ids)
        evaluated_hits = union_retrieval_and_recall(fused_hits, recalled)
        assessments = tuple(
            assess_evidence(query, notes_by_id[hit.note_id], hit, evidence_policy)
            for hit in evaluated_hits
        )
        decision = decide_evidence(query, assessments)
        packets.append(build_evidence_packet(query, decision, notes_by_id))
        audits.append(
            CandidateEvidenceAudit(
                route=query.route,
                week_of=query.week_of,
                query_text=query.query_text,
                verdict=decision.verdict,
                selected_note_id=decision.selected_note_id,
                supporting_note_ids=decision.supporting_note_ids,
                assessments=assessments,
            )
        )
    result = EvidenceReviewResult(
        queries=ordered_queries,
        packets=tuple(packets),
        audits=tuple(audits),
        sparse_rankings=sparse,
        dense_rankings=dense,
        fused_rankings=fused,
    )
    verdicts = Counter(packet.decision.verdict.value for packet in result.packets)
    rejections = Counter(
        code.value
        for audit in result.audits
        for assessment in audit.assessments
        for code in assessment.rejection_codes
    )
    logger.info(
        "Completed evidence review sparse_seconds=%.6f dense_seconds=%.6f "
        "structured_additions=%d verdicts=%s rejections=%s",
        sparse_seconds,
        dense_seconds,
        structured_additions,
        dict(sorted(verdicts.items())),
        dict(sorted(rejections.items())),
    )
    return result
