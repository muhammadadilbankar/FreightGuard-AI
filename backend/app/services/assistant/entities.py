"""Exact snapshot entity resolution without silent fuzzy execution."""

from __future__ import annotations

from difflib import get_close_matches

from ...state.models import AnalysisSnapshot
from .normalization import normalize_route, normalize_text


def resolve_route(question: str, snapshot: AnalysisSnapshot) -> tuple[str | None, tuple[str, ...]]:
    normalized = normalize_text(question)
    catalog = sorted(snapshot.route_timelines)
    matches = [route for route in catalog if normalize_route(route) in normalized]
    if len(matches) == 1:
        return matches[0], ()
    if len(matches) > 1:
        return None, tuple(matches[:3])
    words = normalized.replace("?", "").split()
    suggestions = get_close_matches(" ".join(words[-3:]), catalog, n=3, cutoff=0.45)
    return None, tuple(suggestions)


def note_ids(snapshot: AnalysisSnapshot) -> frozenset[str]:
    return frozenset(
        evidence.note_id
        for anomaly in snapshot.anomalies
        for evidence in anomaly.evidence
    )
