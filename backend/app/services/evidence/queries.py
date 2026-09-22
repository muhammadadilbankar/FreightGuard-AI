"""Pure construction of deterministic candidate investigation queries."""

from datetime import date, timedelta
import math

import pandas as pd
from pandas.api.types import is_bool_dtype

from ...domain.evidence import CandidateEvidenceQuery
from ..analytics.contracts import CANDIDATE_METRIC_COLUMNS
from .errors import EvidenceInputError


def build_candidate_query(candidate: pd.Series) -> CandidateEvidenceQuery:
    """Build one stable query from a canonical Phase 5 candidate row."""
    week_of = pd.Timestamp(candidate["week_of"]).date()
    week_end = week_of + timedelta(days=6)
    peer = candidate["vs_similar_routes_pct"]
    peer_text = "unavailable" if pd.isna(peer) else _number(float(peer))
    own_trigger = bool(candidate["own_threshold_breached"])
    peer_trigger = bool(candidate["peer_threshold_breached"])
    trigger = "both" if own_trigger and peer_trigger else "own" if own_trigger else "peer"
    text = (
        f"Investigate an increase in freight transport cost for route {candidate['route']} "
        f"({candidate['route_type']}) during {week_of.isoformat()} to {week_end.isoformat()}.\n"
        f"Cost per tonne-km: {_number(float(candidate['cost_per_tonne_km']))}.\n"
        f"Change versus own history: {_number(float(candidate['vs_own_history_pct']))} percent.\n"
        f"Change versus similar routes: {peer_text} percent.\n"
        f"Trigger: {trigger}.\n"
        "Find operational events that explicitly increased freight transport costs or rates."
    )
    return CandidateEvidenceQuery(
        route=str(candidate["route"]),
        route_type=str(candidate["route_type"]),
        week_of=week_of,
        week_end=week_end,
        cost_per_tonne_km=float(candidate["cost_per_tonne_km"]),
        vs_own_history_pct=float(candidate["vs_own_history_pct"]),
        vs_similar_routes_pct=None if pd.isna(peer) else float(peer),
        own_threshold_breached=own_trigger,
        peer_threshold_breached=peer_trigger,
        query_text=text,
    )


def build_candidate_queries(
    candidate_metrics: pd.DataFrame,
) -> tuple[CandidateEvidenceQuery, ...]:
    """Validate Phase 5 metrics and return candidate-only queries in key order."""
    if not isinstance(candidate_metrics, pd.DataFrame):
        raise EvidenceInputError("Candidate metrics must be a Pandas DataFrame.")
    if tuple(candidate_metrics.columns) != CANDIDATE_METRIC_COLUMNS:
        raise EvidenceInputError("Candidate metrics must use the canonical Phase 5 schema.")
    decisions = candidate_metrics["candidate_anomaly"]
    if decisions.isna().any() or not is_bool_dtype(decisions.dtype):
        raise EvidenceInputError("candidate_anomaly must contain complete Booleans.")
    candidates = candidate_metrics.loc[decisions].copy(deep=True)
    if candidates.empty:
        raise EvidenceInputError("Evidence review requires at least one candidate.")
    key = ["route", "route_type", "week_of"]
    if candidates.duplicated(key).any():
        raise EvidenceInputError("Candidate keys must be unique.")
    candidates = candidates.sort_values(key, kind="mergesort").reset_index(drop=True)
    weeks = pd.to_datetime(candidates["week_of"], errors="coerce")
    if weeks.isna().any() or (weeks.dt.weekday != 0).any():
        raise EvidenceInputError("Every candidate week_of must be a valid Monday.")
    if not candidates["is_rising"].all() or not candidates["candidate_anomaly"].all():
        raise EvidenceInputError("Phase 7 cannot reinterpret non-candidate rows.")
    for column in ("own_threshold_breached", "peer_threshold_breached"):
        if candidates[column].isna().any() or not is_bool_dtype(candidates[column].dtype):
            raise EvidenceInputError(f"{column} must contain complete Booleans.")
    return tuple(build_candidate_query(row) for _, row in candidates.iterrows())


def candidate_key(candidate: CandidateEvidenceQuery) -> tuple[str, date]:
    return candidate.route, candidate.week_of


def _number(value: float) -> str:
    if not math.isfinite(value):
        raise EvidenceInputError("Candidate query values must be finite.")
    return format(value, ".17g")
