"""Retrieval discovery metrics kept separate from Evidence Gate correctness."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from ...domain.evidence import RetrievalHit


@dataclass(frozen=True, slots=True)
class RetrievalMetrics:
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    mean_reciprocal_rank: float


def evaluate_retrieval(
    rankings: Mapping[tuple[str, object], Sequence[RetrievalHit]],
    relevance: Mapping[tuple[str, object], frozenset[str]],
) -> RetrievalMetrics:
    """Evaluate labelled discovery only; these metrics never affect verdicts."""
    if not relevance:
        raise ValueError("Retrieval evaluation requires relevance labels.")
    recalls = {1: [], 3: [], 5: []}
    reciprocal_ranks = []
    for key, relevant in relevance.items():
        if not relevant:
            raise ValueError("Every retrieval label must include a relevant note.")
        ranked_ids = [hit.note_id for hit in rankings.get(key, ())]
        for cutoff in recalls:
            found = len(set(ranked_ids[:cutoff]) & relevant)
            recalls[cutoff].append(found / len(relevant))
        rank = next(
            (index for index, note_id in enumerate(ranked_ids, start=1) if note_id in relevant),
            None,
        )
        reciprocal_ranks.append(0.0 if rank is None else 1 / rank)
    count = len(relevance)
    return RetrievalMetrics(
        recall_at_1=sum(recalls[1]) / count,
        recall_at_3=sum(recalls[3]) / count,
        recall_at_5=sum(recalls[5]) / count,
        mean_reciprocal_rank=sum(reciprocal_ranks) / count,
    )
