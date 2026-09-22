"""Weighted Reciprocal Rank Fusion with stable deterministic ordering."""

from collections.abc import Sequence

from ...domain.evidence import RetrievalConfig, RetrievalHit
from .errors import RetrievalContractError


def fuse_rankings(
    sparse_hits: Sequence[RetrievalHit],
    dense_hits: Sequence[RetrievalHit],
    config: RetrievalConfig,
) -> tuple[RetrievalHit, ...]:
    """Fuse one-based sparse and dense ranks without comparing raw score scales."""
    by_note: dict[str, dict[str, object]] = {}
    for channel, hits in (("sparse", sparse_hits), ("dense", dense_hits)):
        for hit in hits:
            values = by_note.setdefault(hit.note_id, {})
            rank = hit.sparse_rank if channel == "sparse" else hit.dense_rank
            score = hit.sparse_score if channel == "sparse" else hit.dense_score
            if rank is None:
                raise RetrievalContractError(f"{channel} hit is missing its rank.")
            if f"{channel}_rank" in values:
                raise RetrievalContractError(f"Duplicate {channel} note ID in ranking.")
            values[f"{channel}_rank"] = rank
            values[f"{channel}_score"] = score
    combined: list[RetrievalHit] = []
    for note_id, values in by_note.items():
        sparse_rank = values.get("sparse_rank")
        dense_rank = values.get("dense_rank")
        fused = 0.0
        if isinstance(sparse_rank, int):
            fused += config.sparse_weight / (config.rrf_k + sparse_rank)
        if isinstance(dense_rank, int):
            fused += config.dense_weight / (config.rrf_k + dense_rank)
        combined.append(
            RetrievalHit(
                note_id=note_id,
                sparse_rank=sparse_rank,
                sparse_score=values.get("sparse_score"),
                dense_rank=dense_rank,
                dense_score=values.get("dense_score"),
                fused_score=fused,
            )
        )
    combined.sort(
        key=lambda hit: (
            -float(hit.fused_score or 0),
            min(_missing_last(hit.sparse_rank), _missing_last(hit.dense_rank)),
            hit.note_id,
        )
    )
    limit = min(config.top_k, len(combined))
    return tuple(
        hit.model_copy(update={"fused_rank": rank})
        for rank, hit in enumerate(combined[:limit], start=1)
    )


def _missing_last(value: int | None) -> int:
    return value if value is not None else 2**31
